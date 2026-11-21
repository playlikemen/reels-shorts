"""Sheet <-> local store sync, snapshots and row restore.

  python3.11 -m studio.sync pull [--tab @craftlayer]   # Sheet -> local (cron: every 5 minutes)
  python3.11 -m studio.sync snapshot                   # dated JSON + CSV of every tab (cron: nightly), keeps 30 days
  python3.11 -m studio.sync import-log                 # copy new publish-log.jsonl lines into the store

Rules
- Pull upserts by Video ID. A row that disappeared from the Sheet is kept and flagged `missing`; it is never deleted.
- An edit writes the Sheet first (ops/sheet.set_cells), then the store. If the Sheet write fails, the edit is kept as
  `pending` and retried by the next pull.
- Before writing, the row is read again. If an edited cell changed in the Sheet since the editor loaded it, nothing is
  written and the caller gets both values (conflict) to choose from.
"""
import argparse, csv, datetime, hashlib, json, re, shutil, sys

from . import ROOT, BACKUP_DIR
from . import store as S
import config as K
import sheet

EDITABLE = [h for h in K.HEADERS if h != "Video ID"]
STATUS_COLS = ["Instagram Status", "YouTube Status"]
POST_COLS = STATUS_COLS + ["Instagram Post URL", "YouTube Shorts URL"]
TIME_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
LOG = K.STATE / "publish-log.jsonl"


class SyncError(Exception):
    status = 400

    def __init__(self, msg, status=400, **data):
        super().__init__(msg)
        self.status, self.data = status, data


def brands_by_tab():
    return {b["sheet_tab"]: b for b in K.brands()}


def spec_for(brand, vid):
    """(spec path relative to the repo, language) for a Video ID; CR-101-EN -> specs/craftlayer/CR-101.json, 'en'."""
    d = ROOT / "specs" / brand
    if (d / f"{vid}.json").exists():
        return f"specs/{brand}/{vid}.json", ""
    m = re.match(r"^(.+)-([A-Z]{2})$", vid)
    if m and (d / f"{m[1]}.json").exists():
        return f"specs/{brand}/{m[1]}.json", m[2].lower()
    return "", ""


def out_dir(brand, vid, local_path=""):
    if local_path:
        p = (ROOT / local_path).parent
        if p.is_dir():
            return p
    return ROOT / "out" / brand / vid


def thumb_for(brand, vid, local_path=""):
    t = out_dir(brand, vid, local_path) / "thumb.jpg"
    return str(t.relative_to(ROOT)) if t.exists() else ""


def _retry_pending(tab, row_number, values, pending):
    """Try queued edits again. Returns the pending edits still open; `values` is updated with what was written."""
    left = {}
    for h, p in pending.items():
        cur = values.get(h, "")
        if cur == p["value"]:
            continue
        if cur != p.get("base", cur):
            left[h] = {**p, "conflict": cur}       # someone changed it in the Sheet meanwhile: the owner decides
            continue
        try:
            sheet.set_cells(tab, row_number, {h: p["value"]})
            values[h] = p["value"]
            S.audit("edit synced", "", None, {h: p["value"]}, who="sync")
        except Exception as e:
            left[h] = {**p, "error": str(e)[:200]}
    return left


def pull(tabs=None, db=None):
    """Sheet -> store for every brand tab (or only `tabs`, by tab name or brand key). Returns a per-tab summary."""
    db = db or S.connect()
    import_publish_log(db)
    summary = {}
    for b in K.brands():
        tab = b["sheet_tab"]
        if tabs and tab not in tabs and b["key"] not in tabs:
            continue
        try:
            rows = sheet.rows(tab)
        except Exception as e:
            summary[tab] = {"error": str(e)[:300]}
            continue
        seen, changed = set(), 0
        for r in rows:
            vid = str(r["Video ID"]).strip()
            seen.add(vid)
            values = {h: str(r.get(h, "")) for h in K.HEADERS}
            values["Video ID"] = vid
            local = S.get_reel(vid, db)
            pending = (local or {}).get("pending") or {}
            if pending:
                pending = _retry_pending(tab, r["_row"], values, pending)
            h = row_hash(values)
            display = dict(values)
            for k, p in pending.items():
                display[k] = p["value"]
            same = local and local["sheet_hash"] == h and not local["missing"]
            changed += not same
            spec, _ = spec_for(b["key"], vid)
            S.save_reel(display, db, tab=tab, brand=b["key"], sheet_row=r["_row"], sheet_hash=h, missing=0,
                        pending=pending, loaded_at=S.now(), spec_path=spec,
                        thumb=thumb_for(b["key"], vid, values["Local Path"]),
                        updated_at=(local["updated_at"] if same else S.now()))
        gone = [x["video_id"] for x in db.execute("SELECT video_id FROM reels WHERE tab=? AND missing=0", (tab,)) if x["video_id"] not in seen]
        for vid in gone:
            db.execute("UPDATE reels SET missing=1 WHERE video_id=?", (vid,))
            S.audit("missing in sheet", vid, who="sync", db=db)
        summary[tab] = {"rows": len(rows), "changed": changed, "missing": len(gone)}
    S.set_setting("last_pull", {"at": S.now(), "summary": summary}, db)
    return summary


def row_hash(values):
    return S.row_hash(values)


def _fresh_row(tab, vid):
    for r in sheet.rows(tab):
        if str(r["Video ID"]).strip() == vid:
            return r
    return None


def _queue(db, local, changes, base, err, who, ip):
    pending = dict(local["pending"] or {})
    for h, v in changes.items():
        pending[h] = {"value": v, "base": base.get(h, local[h]), "queued_at": S.now(), "error": err[:200]}
    display = {h: local[h] for h in K.HEADERS}
    display.update(changes)
    S.save_reel(display, db, pending=pending)
    S.audit("edit queued", local["Video ID"], {h: base.get(h, local[h]) for h in changes}, changes, who, ip, db)
    return {"status": "pending", "error": err[:300], "reel": S.get_reel(local["Video ID"], db)}


def edit(vid, fields, base=None, force=False, who="owner", ip="", allow_repost=False, db=None):
    """Write cells for one row: Sheet first, then the store.

    base: {header: value the editor loaded}; defaults to the stored values. A cell whose Sheet value differs from its
    base is a conflict (unless force). Returns {status: ok|pending|conflict|unchanged, ...}.
    """
    db = db or S.connect()
    local = S.get_reel(vid, db)
    if not local:
        raise SyncError(f"no reel {vid}", 404)
    bad = [k for k in fields if k not in EDITABLE]
    if bad:
        raise SyncError(f"not editable: {', '.join(bad)}")
    fields = {k: "" if v is None else str(v) for k, v in fields.items()}
    t = fields.get("Scheduled Time (IST)")
    if t and not TIME_RE.match(t):
        raise SyncError("Scheduled Time (IST) must look like YYYY-MM-DD HH:MM")
    if any(local[c] == "Publishing" for c in STATUS_COLS):
        raise SyncError(f"{vid} is being published right now; edit it after the post finishes", 409)
    for c in STATUS_COLS:
        if fields.get(c) == "Ready" and local[c].startswith("Published") and not allow_repost:
            raise SyncError(f"{vid} is already {c.split()[0]} Published; setting it to Ready would post it again "
                            "(send allow_repost to do it anyway)", 409)
    base = {h: (base or {}).get(h, local[h]) for h in fields}
    tab = local["tab"]
    try:
        cur = _fresh_row(tab, vid)
    except Exception as e:
        return _queue(db, local, fields, base, f"sheet read failed: {e}", who, ip)
    if cur is None:
        raise SyncError(f"{vid} is not in the Sheet tab {tab} any more; restore it from a snapshot first", 409)
    cur_values = {h: str(cur.get(h, "")) for h in K.HEADERS}
    conflicts = {h: {"loaded": base[h], "sheet": cur_values[h], "yours": v} for h, v in fields.items()
                 if cur_values[h] != base[h] and cur_values[h] != v}
    if conflicts and not force:
        return {"status": "conflict", "conflicts": conflicts, "sheet_hash": row_hash(cur_values)}
    changes = {h: v for h, v in fields.items() if cur_values[h] != v}
    pending = {k: p for k, p in (local["pending"] or {}).items() if k not in fields}
    if not changes:
        S.save_reel(cur_values, db, sheet_hash=row_hash(cur_values), sheet_row=cur["_row"], pending=pending, missing=0)
        return {"status": "unchanged", "reel": S.get_reel(vid, db)}
    try:
        sheet.set_cells(tab, cur["_row"], changes)
    except Exception as e:
        return _queue(db, local, changes, {h: cur_values[h] for h in changes}, f"sheet write failed: {e}", who, ip)
    new = dict(cur_values)
    new.update(changes)
    display = dict(new)
    for k, p in pending.items():
        display[k] = p["value"]
    S.save_reel(display, db, sheet_hash=row_hash(new), sheet_row=cur["_row"], pending=pending, missing=0, loaded_at=S.now())
    S.audit("edit", vid, {h: cur_values[h] for h in changes}, changes, who, ip, db)
    return {"status": "ok", "changed": list(changes), "reel": S.get_reel(vid, db)}


def drop_pending(vid, header, who="owner", ip="", db=None):
    """Forget one queued edit (the owner chose the Sheet's value)."""
    db = db or S.connect()
    local = S.get_reel(vid, db)
    if not local or header not in (local["pending"] or {}):
        raise SyncError("nothing pending for that cell", 404)
    pending = dict(local["pending"])
    p = pending.pop(header)
    S.save_reel({"Video ID": vid, header: p.get("conflict", p.get("base", ""))}, db, pending=pending)
    S.audit("pending dropped", vid, {header: p["value"]}, None, who, ip, db)
    return S.get_reel(vid, db)


def import_publish_log(db=None):
    db = db or S.connect()
    if not LOG.exists():
        return 0
    n = 0
    for line in open(LOG, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            continue
        hsh = hashlib.sha256(line.encode()).hexdigest()[:24]
        cur = db.execute("INSERT OR IGNORE INTO publish_log (line_hash, video, platform, status, at, data) VALUES (?,?,?,?,?,?)",
                         (hsh, e.get("video", ""), e.get("platform", ""), e.get("status", ""), e.get("at", ""), line))
        n += cur.rowcount
    return n


def unsynced_renders(db=None):
    """Rendered reels (out/<brand>/<ID>/<id>.mp4) that have no sheet row."""
    db = db or S.connect()
    known = {r["video_id"] for r in db.execute("SELECT video_id FROM reels")}
    out = []
    for b in K.brands():
        d = ROOT / "out" / b["key"]
        if not d.is_dir():
            continue
        for sub in sorted(d.iterdir()):
            mp4 = sub / f"{sub.name.lower()}.mp4"
            if sub.name in known or not mp4.exists():
                continue
            spec, lang = spec_for(b["key"], sub.name)
            st = mp4.stat()
            out.append({"Video ID": sub.name, "brand": b["key"], "tab": b["sheet_tab"], "local_path": str(mp4.relative_to(ROOT)),
                        "thumb": thumb_for(b["key"], sub.name), "spec_path": spec, "lang": lang, "size": st.st_size,
                        "mtime": datetime.datetime.fromtimestamp(st.st_mtime, S.TZ).isoformat(timespec="minutes")})
    return out


# ---------- snapshots ----------

DATE_DIR = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def snapshot(keep_days=30, db=None, base=None):
    db = db or S.connect()
    base = base or BACKUP_DIR
    day = datetime.datetime.now(S.TZ).date()
    d = base / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    files = []
    for b in K.brands():
        tab = b["sheet_tab"]
        rows = [{h: r[h] for h in K.HEADERS} for r in S.list_reels(db) if r["tab"] == tab and not r["missing"]]
        name = tab.lstrip("@")
        (d / f"{name}.json").write_text(json.dumps({"tab": tab, "at": S.now(), "rows": rows}, indent=1, ensure_ascii=False))
        with open(d / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=K.HEADERS)
            w.writeheader()
            w.writerows(rows)
        files += [f"{name}.json", f"{name}.csv"]
    if LOG.exists():
        shutil.copy2(LOG, d / "publish-log.jsonl")
        files.append("publish-log.jsonl")
    cutoff = day - datetime.timedelta(days=keep_days)
    pruned = []
    for old in base.iterdir():
        if old.is_dir() and DATE_DIR.match(old.name) and datetime.date.fromisoformat(old.name) < cutoff:
            shutil.rmtree(old)
            pruned.append(old.name)
    S.set_setting("last_snapshot", {"at": S.now(), "dir": str(d)}, db)
    return {"dir": str(d), "files": files, "pruned": pruned}


def list_snapshots(base=None):
    base = base or BACKUP_DIR
    if not base.exists():
        return []
    return sorted((p.name for p in base.iterdir() if p.is_dir() and DATE_DIR.match(p.name)), reverse=True)


def snapshot_row(date, vid, base=None):
    base = base or BACKUP_DIR
    if not DATE_DIR.match(date or ""):
        raise SyncError("bad snapshot date")
    for f in sorted((base / date).glob("*.json")):
        data = json.loads(f.read_text())
        for r in data.get("rows", []):
            if r.get("Video ID") == vid:
                return data["tab"], r
    raise SyncError(f"{vid} is not in the {date} snapshot", 404)


def restore_row(vid, date, dry_run=True, who="owner", ip="", db=None, base=None):
    """Rewrite one row from a snapshot. Status and post-URL cells that already hold a value are never rolled back,
    so a restore can not make a published reel 'Ready' (and post it) again."""
    db = db or S.connect()
    tab, snap = snapshot_row(date, vid, base)
    local = S.get_reel(vid, db)
    if local and not local["missing"]:
        diff = {h: snap.get(h, "") for h in EDITABLE
                if snap.get(h, "") != local[h] and not (h in POST_COLS and local[h])}
        if dry_run or not diff:
            return {"status": "dry-run" if dry_run else "unchanged", "tab": tab, "diff": diff,
                    "current": {h: local[h] for h in diff}}
        res = edit(vid, diff, force=True, who=who, ip=ip, db=db)
        S.audit("restore row", vid, {h: local[h] for h in diff}, {"from": date, **diff}, who, ip, db)
        return {**res, "diff": diff}
    if dry_run:
        return {"status": "dry-run", "tab": tab, "diff": snap, "current": {}, "append": True}
    sheet.upsert(tab, snap)
    S.audit("restore row", vid, None, {"from": date, **snap}, who, ip, db)
    pull([tab], db)
    return {"status": "ok", "tab": tab, "appended": True, "reel": S.get_reel(vid, db)}


def bulk(params, who="owner", db=None):
    """Hold, unhold or reschedule several rows, one Sheet edit each. Schedule: `start`, then one row every `every_days`.
    Also: archive, unarchive, fill (next free slots), swap (exactly two ids)."""
    db = db or S.connect()
    act = params.get("action")
    if act == "fill":
        return fill(params["ids"], auto=params.get("auto", True) is not False, who=who, db=db)
    if act == "swap":
        res = swap(*params["ids"][:2], who=who, db=db)
        print(json.dumps(res), flush=True)
        return res
    if act in ("archive", "unarchive"):
        results = {}
        for vid in params["ids"]:
            try:
                res = (archive if act == "archive" else unarchive)(vid, who=who, db=db)
                results[vid] = res["status"] + (f" · {res['drive']}" if res.get("drive") else "")
            except SyncError as e:
                results[vid] = f"error: {e}"
            print(vid, results[vid], flush=True)
        return results
    t0 = datetime.datetime.strptime(params["start"], "%Y-%m-%d %H:%M") if params.get("action") == "schedule" else None
    results = {}
    for i, vid in enumerate(params["ids"]):
        r = S.get_reel(vid, db)
        if not r:
            results[vid] = "no such reel"; continue
        if params["action"] == "schedule":
            when = (t0 + datetime.timedelta(days=i * int(params.get("every_days") or 1))).strftime("%Y-%m-%d %H:%M")
            fields = {"Scheduled Time (IST)": when, "Date": when[:10]}
        else:
            hold = params["action"] == "hold"
            fields = {c: ("Hold" if hold else "Ready") for c in STATUS_COLS if r[c] == ("Ready" if hold else "Hold")}
        if not fields:
            results[vid] = "nothing to change"; continue
        try:
            res = edit(vid, fields, who=who, db=db)
            results[vid] = res["status"] + (f" {res.get('conflicts')}" if res["status"] == "conflict" else "")
        except SyncError as e:
            results[vid] = f"error: {e}"
        print(vid, results[vid], flush=True)
    return results


# ---------- folders, archive, scheduling ----------

ARCHIVED = "Archived"
FOLDERS = ["queue", "due", "drafts", "published", "archive"]


def ist_now():
    return datetime.datetime.now(S.TZ).strftime("%Y-%m-%d %H:%M")


def folder_of(r, now=None):
    """Library folder of a row, from its Instagram status and time (the Sheet stays the source of truth)."""
    now = now or ist_now()
    ig = (r.get("Instagram Status") or "").strip()
    low = ig.lower()
    if ARCHIVED in (ig, r.get("YouTube Status")):
        return "archive"
    if low.startswith("published"):
        return "published"
    if ig == "Ready":
        t = r.get("Scheduled Time (IST)") or ""
        return "queue" if TIME_RE.match(t) and t > now else "due"
    if low.startswith(("failed", "manual")) or ig == "Publishing":
        return "due"
    return "drafts"


def _move_drive(link, sub):
    """Best effort: move the reel's Drive folder. Returns a short note for the caller; never raises."""
    if not link:
        return "no Drive folder"
    try:
        import drive
        drive.move(link, sub)
        return f"Drive folder moved to {sub or 'the reels folder'}"
    except Exception as e:
        return f"Drive folder not moved: {str(e)[:160]}"


def archive(vid, who="owner", ip="", db=None, move_drive=True):
    """Set both status cells to Archived (Sheet first), remember the previous values locally, move the Drive folder
    into Archive/. Nothing is deleted: the row, the local files and the Drive files all stay."""
    db = db or S.connect()
    r = S.get_reel(vid, db)
    if not r:
        raise SyncError(f"no reel {vid}", 404)
    if ARCHIVED in (r["Instagram Status"], r["YouTube Status"]):
        raise SyncError(f"{vid} is already archived", 409)
    prev = {c: r[c] for c in STATUS_COLS}
    res = edit(vid, {c: ARCHIVED for c in STATUS_COLS}, who=who, ip=ip, db=db)
    if res["status"] in ("ok", "pending", "unchanged"):
        S.save_reel({"Video ID": vid}, db, prev_status=prev)
        S.audit("archive", vid, prev, {c: ARCHIVED for c in STATUS_COLS}, who, ip, db)
        res["drive"] = _move_drive(r["Google Drive Folder"], "Archive") if move_drive else "skipped"
        res["reel"] = S.get_reel(vid, db)
    return res


def unarchive(vid, who="owner", ip="", db=None, move_drive=True):
    """Put back the statuses the row had before Archive. A Ready reel whose slot has already passed comes back as
    Hold, so unarchiving never makes cron post it at once."""
    db = db or S.connect()
    r = S.get_reel(vid, db)
    if not r:
        raise SyncError(f"no reel {vid}", 404)
    if ARCHIVED not in (r["Instagram Status"], r["YouTube Status"]):
        raise SyncError(f"{vid} is not archived", 409)
    prev = dict(r.get("prev_status") or {})
    if not prev:      # the local memory was lost: published if it has a post link, otherwise a draft
        prev = {"Instagram Status": "Published" if r["Instagram Post URL"] else "Hold",
                "YouTube Status": "Published" if r["YouTube Shorts URL"] else
                ("Hold" if (K.brand(r["brand"]).get("youtube")) else "No channel")}
    t = r["Scheduled Time (IST)"]
    note = ""
    for c in STATUS_COLS:
        if prev.get(c) == "Ready" and not (TIME_RE.match(t or "") and t > ist_now()):
            prev[c] = "Hold"
            note = "its slot has passed, so it comes back as Hold; schedule it again"
    fields = {c: prev.get(c, "") for c in STATUS_COLS if r[c] == ARCHIVED}
    res = edit(vid, fields, who=who, ip=ip, db=db, allow_repost=True)
    if res["status"] in ("ok", "pending", "unchanged"):
        S.save_reel({"Video ID": vid}, db, prev_status={})
        S.audit("unarchive", vid, {c: ARCHIVED for c in fields}, fields, who, ip, db)
        sub = "Published" if fields.get("Instagram Status", r["Instagram Status"]).startswith("Published") else ""
        res["drive"] = _move_drive(r["Google Drive Folder"], sub) if move_drive else "skipped"
        res["note"] = note
        res["reel"] = S.get_reel(vid, db)
    return res


def brand_slots(brand_key):
    b = K.brand(brand_key)
    slots = sorted(b.get("slots_ist") or ["19:30"])
    cap = b.get("max_reels_per_day") or len(slots)
    return b, slots, cap


def next_free_slot(brand_key, after=None, exclude=(), taken_extra=(), db=None):
    """First slot (YYYY-MM-DD HH:MM, IST) after `after` that no Ready row of the brand holds, on a day that still has
    room under the daily cap. Ready, Publishing and Published rows count towards a day; `exclude` ids do not."""
    db = db or S.connect()
    _, slots, cap = brand_slots(brand_key)
    after = after or ist_now()
    taken, per_day = set(taken_extra), {}
    for t in taken_extra:
        per_day[t[:10]] = per_day.get(t[:10], 0) + 1
    for r in S.list_reels(db):
        if r["brand"] != brand_key or r["Video ID"] in exclude or r["missing"]:
            continue
        st, t = r["Instagram Status"], r["Scheduled Time (IST)"]
        if not TIME_RE.match(t or ""):
            continue
        if st in ("Ready", "Publishing"):
            taken.add(t)
        if st in ("Ready", "Publishing") or st.startswith("Published"):
            per_day[t[:10]] = per_day.get(t[:10], 0) + 1
    day = datetime.date.fromisoformat(after[:10])
    for _ in range(400):
        d = day.isoformat()
        for s_ in slots:
            t = f"{d} {s_}"
            if t > after and t not in taken and per_day.get(d, 0) < cap:
                return t
        day += datetime.timedelta(days=1)
    raise SyncError("no free slot in the next 400 days")


def schedule(vid, when, auto=True, who="owner", ip="", db=None):
    """Set a reel's time. auto: the reel is Ready (cron posts it then); otherwise Hold (just planned).
    A Published reel can not be rescheduled."""
    db = db or S.connect()
    r = S.get_reel(vid, db)
    if not r:
        raise SyncError(f"no reel {vid}", 404)
    if not TIME_RE.match(when or ""):
        raise SyncError("time must look like YYYY-MM-DD HH:MM")
    if r["Instagram Status"].startswith("Published"):
        raise SyncError(f"{vid} is already published; it can not be rescheduled", 409)
    if r["Instagram Status"] == ARCHIVED and (r["Instagram Post URL"] or
                                              (r.get("prev_status") or {}).get("Instagram Status", "").startswith("Published")):
        raise SyncError(f"{vid} was published before it was archived; unarchive it instead of rescheduling", 409)
    has_yt = bool(K.brand(r["brand"]).get("youtube"))
    fields = {"Scheduled Time (IST)": when, "Date": when[:10]}
    target = "Ready" if auto else "Hold"
    for c in STATUS_COLS:
        cur = r[c]
        if c == "YouTube Status":
            if not has_yt:
                if cur == ARCHIVED:
                    fields[c] = "No channel"
                continue
            if cur.startswith("Published"):
                continue
            if cur == ARCHIVED and r["YouTube Shorts URL"]:
                fields[c] = "Published"
                continue
        if auto or cur in ("Ready", ARCHIVED) or cur.startswith(("Failed", "Manual")):
            if cur != target:
                fields[c] = target
    res = edit(vid, fields, who=who, ip=ip, db=db)
    if res["status"] in ("ok", "pending") and r.get("prev_status"):
        S.save_reel({"Video ID": vid}, db, prev_status={})
    return res


def swap(a, b, who="owner", ip="", db=None):
    """Swap the scheduled times of two reels (two Sheet edits, each audited)."""
    db = db or S.connect()
    ra, rb = S.get_reel(a, db), S.get_reel(b, db)
    if not ra or not rb:
        raise SyncError("both reels must exist", 404)
    for r in (ra, rb):
        if r["Instagram Status"].startswith("Published") or r["Instagram Status"] == "Publishing":
            raise SyncError(f"{r['Video ID']} is {r['Instagram Status']}; only unpublished reels can swap slots", 409)
    ta, tb = ra["Scheduled Time (IST)"], rb["Scheduled Time (IST)"]
    out = {}
    for vid, t in ((a, tb), (b, ta)):
        fields = {"Scheduled Time (IST)": t}
        if TIME_RE.match(t or ""):
            fields["Date"] = t[:10]
        out[vid] = edit(vid, fields, who=who, ip=ip, db=db)["status"]
    return out


def fill(ids, brand_key=None, after=None, auto=True, who="owner", db=None):
    """Give each reel the next free slot of its brand, in order."""
    db = db or S.connect()
    out, used = {}, {}
    for vid in ids:
        r = S.get_reel(vid, db)
        if not r:
            out[vid] = "no such reel"; continue
        try:
            t = next_free_slot(r["brand"], after, exclude=(vid,), taken_extra=used.get(r["brand"], ()), db=db)
            res = schedule(vid, t, auto, who=who, db=db)
            used.setdefault(r["brand"], []).append(t)
            out[vid] = f"{res['status']} {t}"
        except SyncError as e:
            out[vid] = f"error: {e}"
        print(vid, out[vid], flush=True)
    return out


def backfill_published(dry_run=False, db=None):
    """One-off: move the Drive folder of every Instagram-published reel into Published/ (moves only)."""
    db = db or S.connect()
    import drive
    rows = [r for r in S.list_reels(db) if r["Instagram Status"].startswith("Published") and drive.folder_id(r["Google Drive Folder"])]
    moved, failed = [], {}
    for r in rows:
        if dry_run:
            print("[dry-run] would move", r["Video ID"], flush=True); continue
        try:
            drive.move(r["Google Drive Folder"], "Published")
            moved.append(r["Video ID"])
            print("moved", r["Video ID"], flush=True)
        except Exception as e:
            failed[r["Video ID"]] = str(e)[:160]
            print("FAILED", r["Video ID"], failed[r["Video ID"]], flush=True)
    S.audit("drive backfill", "Published/", None, {"moved": len(moved), "failed": failed}, "studio", "", db)
    if dry_run:
        print(f"{len(rows)} published Drive folders would be moved into Published/")
    else:
        print(f"moved {len(moved)} of {len(rows)} published Drive folders into Published/" + (f"; {len(failed)} failed" if failed else ""))
    return {"moved": moved, "failed": failed, "total": len(rows)}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="studio.sync")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull"); p.add_argument("--tab", action="append")
    sub.add_parser("snapshot"); sub.add_parser("import-log")
    p = sub.add_parser("backfill-published"); p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("bulk"); p.add_argument("params"); p.add_argument("--who", default="owner")
    a = ap.parse_args(argv)
    if a.cmd == "pull":
        print(json.dumps(pull(a.tab), indent=1))
    elif a.cmd == "backfill-published":
        return 1 if backfill_published(a.dry_run)["failed"] else 0
    elif a.cmd == "snapshot":
        print(json.dumps(snapshot(), indent=1))
    elif a.cmd == "bulk":
        res = bulk(json.loads(a.params), a.who)
        return 1 if any(v.startswith(("error", "conflict")) for v in res.values()) else 0
    else:
        print("imported", import_publish_log(), "lines")


if __name__ == "__main__":
    sys.exit(main())
