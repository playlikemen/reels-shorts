"""Local SQLite store: the studio's copy (and backup) of every sheet row, publish-log entry, insight, job and audit event.

Rows are kept by Video ID. The 18 sheet columns are stored under short column names (COLS) and exposed by the API
under the sheet's own header names, so agents see the same keys as in the Sheet.
"""
import datetime, hashlib, json, sqlite3, threading
from zoneinfo import ZoneInfo

from . import DB_PATH
import config as K

TZ = ZoneInfo(K.TIMEZONE)

COLS = {
    "Video ID": "video_id", "Date": "date", "Category / Topic": "topic", "Format": "format", "Duration": "duration",
    "Local Path": "local_path", "Google Drive Folder": "drive_folder", "Direct MP4 Download Link": "mp4_link",
    "YouTube Title": "yt_title", "YouTube SEO Tags (Separated)": "yt_tags", "YouTube Best SEO Description": "yt_description",
    "Instagram Viral Caption": "ig_caption", "Instagram Hashtags": "ig_hashtags", "Instagram Status": "ig_status",
    "Instagram Post URL": "ig_url", "YouTube Status": "yt_status", "YouTube Shorts URL": "yt_url",
    "Scheduled Time (IST)": "scheduled",
}
assert list(COLS) == K.HEADERS, "studio COLS must follow ops/config.py HEADERS"
EXTRA = ["tab", "brand", "sheet_row", "spec_path", "thumb", "updated_at", "sheet_hash", "missing", "pending", "loaded_at",
         "prev_status"]
JSON_EXTRA = {"pending", "prev_status"}   # stored as JSON text
# columns added after the first release: (name, SQL type), added by connect() to older databases
MIGRATIONS = [("prev_status", "TEXT DEFAULT '{}'")]

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS reels (
  {", ".join(f"{c} TEXT DEFAULT ''" if c != "video_id" else "video_id TEXT PRIMARY KEY" for c in COLS.values())},
  tab TEXT, brand TEXT, sheet_row INTEGER, spec_path TEXT DEFAULT '', thumb TEXT DEFAULT '', updated_at TEXT,
  sheet_hash TEXT DEFAULT '', missing INTEGER DEFAULT 0, pending TEXT DEFAULT '{{}}', loaded_at TEXT
);
CREATE TABLE IF NOT EXISTS publish_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, line_hash TEXT UNIQUE, video TEXT, platform TEXT, status TEXT, at TEXT, data TEXT
);
CREATE TABLE IF NOT EXISTS insights (
  id INTEGER PRIMARY KEY AUTOINCREMENT, brand TEXT, media_id TEXT, permalink TEXT, video_id TEXT, posted TEXT,
  views INTEGER, reach INTEGER, shares INTEGER, saves INTEGER, likes INTEGER, comments INTEGER, interactions INTEGER,
  avg_watch REAL, caption TEXT, fetched_at TEXT
);
CREATE INDEX IF NOT EXISTS insights_media ON insights(permalink, fetched_at);
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, title TEXT, args TEXT, status TEXT, created TEXT, started TEXT,
  ended TEXT, exit_code INTEGER, log TEXT, who TEXT, target TEXT
);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, who TEXT, action TEXT, target TEXT, before TEXT, after TEXT, ip TEXT
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS comments_cache (brand TEXT PRIMARY KEY, data TEXT, fetched_at TEXT);
"""

_local = threading.local()


def now():
    return datetime.datetime.now(TZ).isoformat(timespec="seconds")


def connect(path=None):
    path = str(path or DB_PATH)
    cache = getattr(_local, "conns", None)
    if cache is None:
        cache = _local.conns = {}
    if path not in cache:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        c = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
        c.executescript(SCHEMA)
        have = {r["name"] for r in c.execute("PRAGMA table_info(reels)")}
        for name, typ in MIGRATIONS:
            if name not in have:
                c.execute(f"ALTER TABLE reels ADD COLUMN {name} {typ}")
        cache[path] = c
    return cache[path]


def reset_connections():
    for c in (getattr(_local, "conns", None) or {}).values():
        c.close()
    _local.conns = {}


def row_hash(values):
    """Hash of the 18 sheet values (by header), used to notice that the sheet changed since a row was loaded."""
    return hashlib.sha256(json.dumps([str(values.get(h, "")) for h in K.HEADERS]).encode()).hexdigest()[:16]


def to_api(r):
    """A DB row as an API dict: sheet header names plus lower-case extras."""
    if r is None:
        return None
    d = {h: r[c] or "" for h, c in COLS.items()}
    for e in EXTRA:
        d[e] = r[e]
    d["pending"] = json.loads(r["pending"] or "{}")
    d["prev_status"] = json.loads(r["prev_status"] or "{}")
    d["missing"] = bool(r["missing"])
    return d


def get_reel(vid, db=None):
    db = db or connect()
    return to_api(db.execute("SELECT * FROM reels WHERE video_id=?", (vid,)).fetchone())


def list_reels(db=None):
    db = db or connect()
    return [to_api(r) for r in db.execute("SELECT * FROM reels ORDER BY scheduled, video_id")]


def save_reel(values, db=None, **extra):
    """Insert or update one row. `values` maps sheet headers to values; `extra` sets EXTRA columns."""
    db = db or connect()
    vid = values["Video ID"]
    cols = {COLS[h]: str(v) for h, v in values.items() if h in COLS}
    for k, v in extra.items():
        if k not in EXTRA:
            raise KeyError(k)
        cols[k] = json.dumps(v) if k in JSON_EXTRA else v
    cols["updated_at"] = cols.get("updated_at") or now()
    cols["video_id"] = vid
    names = list(cols)
    db.execute(f"INSERT INTO reels ({','.join(names)}) VALUES ({','.join('?' * len(names))}) "
               f"ON CONFLICT(video_id) DO UPDATE SET {','.join(f'{n}=excluded.{n}' for n in names if n != 'video_id')}",
               [cols[n] for n in names])


def audit(action, target="", before=None, after=None, who="owner", ip="", db=None):
    db = db or connect()
    db.execute("INSERT INTO audit (at, who, action, target, before, after, ip) VALUES (?,?,?,?,?,?,?)",
               (now(), who, action, target, json.dumps(before, ensure_ascii=False) if before is not None else "",
                json.dumps(after, ensure_ascii=False) if after is not None else "", ip))


def get_setting(key, default=None, db=None):
    r = (db or connect()).execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default


def set_setting(key, value, db=None):
    (db or connect()).execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                              (key, json.dumps(value)))
