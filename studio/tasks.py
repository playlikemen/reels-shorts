"""Instagram insights, comments inbox and health checks, all through ops/composio.py.

  python3.11 -m studio.tasks insights craftlayer [--sheet]   # fetch per-reel insights into the store (and the insights tab)

Read calls only, except reply_comment (one explicit reply) and --sheet (the brand's insights tab, as ops/ig_report does).
"""
import argparse, datetime, json, re, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

from . import ROOT, HOME
from . import store as S
import composio as C
import config as K
import ig_report

EXTRA_METRICS = ["likes", "comments"]


def _account(brand_key):
    return K.brand(brand_key)["instagram"]["account"]


def fetch_insights(brand_key, write_sheet=False, db=None):
    db = db or S.connect()
    account = _account(brand_key)
    by_url = {r["Instagram Post URL"].rstrip("/"): r["Video ID"] for r in S.list_reels(db) if r["Instagram Post URL"]}
    items = ig_report.media(account)
    at, rows, sheet_rows = S.now(), [], []
    for i in items:
        v = None
        for metrics in (ig_report.METRICS + EXTRA_METRICS, ig_report.METRICS):
            try:
                ins = C.execute("INSTAGRAM_GET_IG_MEDIA_INSIGHTS", {"ig_media_id": i["id"], "metric": metrics}, account)
                v = {d["name"]: (d.get("values") or [{}])[0].get("value") or 0 for d in ins.get("data", [])}
                break
            except Exception as e:
                err = e
        if v is None:
            print("skip", i.get("permalink"), str(err)[:120]); continue
        views = v.get("views", 0)
        link = (i.get("permalink") or "").rstrip("/")
        rec = (brand_key, i["id"], i.get("permalink", ""), by_url.get(link, ""), (i.get("timestamp") or "")[:10], views,
               v.get("reach", 0), v.get("shares", 0), v.get("saved", 0), v.get("likes", 0), v.get("comments", 0),
               v.get("total_interactions", 0), round(v.get("ig_reels_avg_watch_time", 0) / 1000, 1),
               (i.get("caption") or "").replace("\n", " ")[:200], at)
        db.execute("INSERT INTO insights (brand, media_id, permalink, video_id, posted, views, reach, shares, saves, likes,"
                   " comments, interactions, avg_watch, caption, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rec)
        rows.append(rec)
        sheet_rows.append([rec[4], views, rec[6], rec[7], round(1000 * rec[7] / views, 1) if views else 0, rec[8], rec[11],
                           rec[12], rec[13][:90], rec[2]])
        print(f"{rec[4]} views {views:>6} shares {rec[7]:>4} {rec[3] or ''} {rec[2]}")
    S.set_setting(f"insights_at:{brand_key}", at, db)
    if write_sheet:
        tab = K.brand(brand_key).get("insights_tab")
        if not tab:
            print("brand.json has no insights_tab; sheet not written")
        else:
            sheet_rows.sort(key=lambda r: -r[1])
            values = [ig_report.COLUMNS] + [[str(c) for c in r] for r in sheet_rows]
            C.execute("GOOGLESHEETS_VALUES_UPDATE", {"spreadsheet_id": K.SPREADSHEET_ID, "range": f"'{tab}'!A1:J{len(values)}",
                                                     "values": values, "value_input_option": "RAW"}, K.SHEETS_ACCOUNT)
            print("written to", tab)
    print(f"{len(rows)} reels")
    return len(rows)


def latest_insights(db=None):
    """The newest fetch per media, as dicts."""
    db = db or S.connect()
    q = ("SELECT i.* FROM insights i JOIN (SELECT permalink, MAX(fetched_at) m FROM insights GROUP BY permalink) x "
         "ON i.permalink = x.permalink AND i.fetched_at = x.m ORDER BY i.posted DESC")
    return [dict(r) for r in db.execute(q)]


# ---------- comments ----------

KW_RE = re.compile(r"[Cc]omment\s+[*\"'“]*([A-Z][A-Z0-9]{1,9})\b")


def cta_keyword(caption):
    m = KW_RE.search(caption or "")
    return m.group(1) if m else ""


def fetch_comments(brand_key, reels=8, db=None):
    """Latest comments on the brand's most recent reels. Cached in the store."""
    db = db or S.connect()
    account = _account(brand_key)
    by_url = {r["Instagram Post URL"].rstrip("/"): r for r in S.list_reels(db) if r["Instagram Post URL"]}
    media = ig_report.media(account, pages=1)[:reels]

    def one(m):
        try:
            data = C.execute("INSTAGRAM_GET_IG_MEDIA_COMMENTS", {"ig_media_id": m["id"], "limit": 25,
                                                                  "fields": "id,text,username,timestamp,like_count,replies"}, account)
            return m, data.get("data") or [], ""
        except Exception as e:
            return m, [], str(e)[:300]

    with ThreadPoolExecutor(4) as ex:
        results = list(ex.map(one, media))
    out = []
    for m, comments, err in results:
        reel = by_url.get((m.get("permalink") or "").rstrip("/"))
        kw = cta_keyword((reel or {}).get("Instagram Viral Caption") or m.get("caption") or "")
        out.append({"media_id": m["id"], "permalink": m.get("permalink", ""), "posted": m.get("timestamp", ""),
                    "caption": (m.get("caption") or "")[:160], "video_id": (reel or {}).get("Video ID", ""), "keyword": kw,
                    "error": err,
                    "comments": [{"id": c.get("id"), "text": c.get("text", ""), "username": c.get("username", ""),
                                  "timestamp": c.get("timestamp", ""), "likes": c.get("like_count", 0),
                                  "replies": len(((c.get("replies") or {}).get("data")) or []),
                                  "keyword_hit": bool(kw) and kw.lower() in (c.get("text") or "").lower()} for c in comments]})
    data = {"brand": brand_key, "media": out, "fetched_at": S.now()}
    db.execute("INSERT INTO comments_cache (brand, data, fetched_at) VALUES (?,?,?) ON CONFLICT(brand) DO UPDATE SET "
               "data=excluded.data, fetched_at=excluded.fetched_at", (brand_key, json.dumps(data), data["fetched_at"]))
    return data


def cached_comments(brand_key, db=None):
    r = (db or S.connect()).execute("SELECT data FROM comments_cache WHERE brand=?", (brand_key,)).fetchone()
    return json.loads(r["data"]) if r else None


def check_reply(message):
    message = (message or "").strip()
    if not message:
        return "write a reply first"
    if len(message) > 300:
        return "Instagram replies are at most 300 characters"
    if message.count("#") > 4:
        return "at most 4 hashtags"
    if len(re.findall(r"https?://", message)) > 1:
        return "at most 1 link"
    letters = [c for c in message if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return "a reply can not be all capital letters"
    return ""


def reply_comment(brand_key, comment_id, message):
    err = check_reply(message)
    if err:
        raise ValueError(err)
    if not re.match(r"^\d{5,30}$", str(comment_id)):
        raise ValueError("bad comment id")
    return C.execute("INSTAGRAM_POST_IG_COMMENT_REPLIES", {"ig_comment_id": str(comment_id), "message": message.strip()},
                     _account(brand_key))


# ---------- health ----------

EXPIRED_HINTS = ("session has been invalidated", "Error validating access token", "status 401", "expired")


def connections():
    """Composio connection status of every brand account (read-only search call). Secrets never leave the server."""
    res = C._call("COMPOSIO_SEARCH_TOOLS", {"queries": [{"use_case": "get instagram user media"}, {"use_case": "list youtube channel videos"},
                                                        {"use_case": "read google sheet values"}], "session": {"generate_id": True}})
    statuses = {}
    for tk in ((res.get("data") or {}).get("toolkit_connection_statuses") or []):
        for acc in tk.get("accounts") or []:
            statuses[acc.get("id")] = acc.get("status", "")
    return statuses


def health_connections(db=None):
    db = db or S.connect()
    try:
        statuses, err = connections(), ""
    except Exception as e:
        statuses, err = {}, str(e)[:200]
    out = []
    accounts = [("sheet", "Google Sheets", K.SHEETS_ACCOUNT, ""), ("drive", "Google Drive", K.DRIVE_ACCOUNT, "")]
    for b in K.brands():
        accounts.append((b["key"], f"Instagram {b['instagram']['handle']}", b["instagram"]["account"], b["id_prefix"]))
        if b.get("youtube"):
            accounts.append((b["key"], f"YouTube {b['youtube']['handle']}", b["youtube"]["account"], ""))
    for key, label, acc, prefix in accounts:
        state = statuses.get(acc, "unknown" if err else "not connected")
        note = ""
        if prefix and acc.startswith("instagram"):
            last = db.execute("SELECT status, at, data FROM publish_log WHERE platform='instagram' AND video LIKE ? ORDER BY at DESC LIMIT 1",
                              (prefix + "-%",)).fetchone()
            if last and last["status"] == "failed" and any(h in last["data"] for h in EXPIRED_HINTS):
                state, note = "expired", f"last post failed {last['at'][:16]}: token invalidated; reconnect in Composio"
        out.append({"brand": key, "label": label, "account": acc, "status": state, "note": note})
    return {"accounts": out, "error": err}


def du(path):
    total = 0
    for p in path.rglob("*"):
        try:
            if p.is_file():
                total += p.stat().st_size
        except OSError:
            pass
    return total


def tunnel_status():
    try:
        ps = subprocess.run(["pgrep", "-af", "cloudflared"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        ps = ""
    running = [l for l in ps.splitlines() if "reels-studio" in l]
    cfg = HOME / ".cloudflared" / "reels-studio.yml"
    return {"configured": cfg.exists(), "running": bool(running), "hostname": _hostname(cfg)}


def _hostname(cfg):
    if not cfg.exists():
        return ""
    m = re.search(r"hostname:\s*(\S+)", cfg.read_text())
    return m.group(1) if m else ""


def health_local(db=None):
    db = db or S.connect()
    log, lock = K.STATE / "scheduler.log", K.STATE / "scheduler.lock"
    tail = ""
    if log.exists():
        with open(log, "rb") as f:
            f.seek(max(0, log.stat().st_size - 3000))
            tail = f.read().decode("utf-8", "replace").splitlines()[-12:]
    try:
        cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True, timeout=5).stdout
    except Exception:
        cron = ""
    canary = json.loads((K.STATE / "youtube_canary.json").read_text()) if (K.STATE / "youtube_canary.json").exists() else {"state": "none"}
    cache = S.get_setting("du_out")
    if not cache or time.time() - cache["t"] > 3600:
        cache = {"t": time.time(), "bytes": du(ROOT / "out")}
        S.set_setting("du_out", cache, db)
    disk = shutil.disk_usage(str(ROOT))
    pending = sum(1 for r in S.list_reels(db) if r["pending"])
    missing = sum(1 for r in S.list_reels(db) if r["missing"])
    return {
        # every scheduler run reopens (truncates) its lock file, so its mtime is the cron heartbeat; the log only
        # grows when something was due
        "scheduler": {"log_mtime": datetime.datetime.fromtimestamp(log.stat().st_mtime, S.TZ).isoformat(timespec="minutes") if log.exists() else "",
                      "last_run": datetime.datetime.fromtimestamp(lock.stat().st_mtime, S.TZ).isoformat(timespec="minutes") if lock.exists() else "",
                      "age_min": round((time.time() - lock.stat().st_mtime) / 60) if lock.exists() else None, "tail": tail,
                      "cron_lines": [l for l in cron.splitlines() if "reels-shorts" in l or "studio" in l]},
        "canary": canary, "out_bytes": cache["bytes"], "disk_free": disk.free, "disk_total": disk.total,
        "last_pull": S.get_setting("last_pull"), "last_snapshot": S.get_setting("last_snapshot"),
        "pending": pending, "missing": missing, "tunnel": tunnel_status(),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="studio.tasks")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("insights"); p.add_argument("brand"); p.add_argument("--sheet", action="store_true")
    a = ap.parse_args(argv)
    if a.cmd == "insights":
        fetch_insights(a.brand, a.sheet)


if __name__ == "__main__":
    sys.exit(main())
