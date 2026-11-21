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
    """Hold, unhold or reschedule several rows, one Sheet edit each. Schedule: `start`, then one row every `every_days`."""
    db = db or S.connect()
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


def main(argv=None):
    ap = argparse.ArgumentParser(prog="studio.sync")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull"); p.add_argument("--tab", action="append")
    sub.add_parser("snapshot"); sub.add_parser("import-log")
    p = sub.add_parser("bulk"); p.add_argument("params"); p.add_argument("--who", default="owner")
    a = ap.parse_args(argv)
    if a.cmd == "pull":
        print(json.dumps(pull(a.tab), indent=1))
    elif a.cmd == "snapshot":
        print(json.dumps(snapshot(), indent=1))
    elif a.cmd == "bulk":
        res = bulk(json.loads(a.params), a.who)
        return 1 if any(v.startswith(("error", "conflict")) for v in res.values()) else 0
    else:
        print("imported", import_publish_log(), "lines")


if __name__ == "__main__":
    sys.exit(main())
