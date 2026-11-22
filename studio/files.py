"""Temporary file hosting: files in folders, each with an unguessable public link that expires.

  python3.11 -m studio.files sweep        # delete expired files (cron: every 5 minutes; also on studio start)

- Content lives in ~/.local/state/reels-shorts/files/<id> (the id is random hex). The name is only metadata, so no name
  can reach the filesystem: there is no path traversal to worry about.
- Metadata lives in the studio SQLite store (tables files_meta, file_folders).
- Public link: /f/<token>/<name>. The token (32+ url-safe characters) is the only key; the name in the link is cosmetic.
- Creating, changing, deleting and listing need the owner (browser session) or the API key. Only the link is public.
- Expiry: 1d, 7d, a custom time up to 90 days ahead, or never (owner session or MCP key only, not agent tokens).
- Quota: total bytes stored, default 20 GB (setting files_quota_bytes).
- Every write is audited.
"""
import datetime, hashlib, ipaddress, mimetypes, os, re, secrets, shutil, socket, sys, unicodedata, urllib.parse, urllib.request

from . import store as S
import config as K

MAX_UI = 1024 ** 3                 # 1 GB per file through the UI / REST
MAX_MCP = 25 * 1024 * 1024         # 25 MB base64 content over MCP
MAX_URL = 1024 ** 3                # fetching a URL
DEFAULT_QUOTA = 20 * 1024 ** 3
MAX_DAYS = 90
INLINE = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/avif", "application/pdf", "text/plain"}
INLINE_PREFIX = ("audio/", "video/")
SCHEMA = """
CREATE TABLE IF NOT EXISTS file_folders (
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, parent_id INTEGER, created TEXT, updated TEXT
);
CREATE TABLE IF NOT EXISTS files_meta (
  id TEXT PRIMARY KEY, token TEXT UNIQUE NOT NULL, name TEXT NOT NULL, folder_id INTEGER, size INTEGER, mime TEXT,
  sha256 TEXT, created TEXT, updated TEXT, expires_at TEXT, who TEXT
);
CREATE INDEX IF NOT EXISTS files_meta_folder ON files_meta(folder_id);
"""


class FileError(Exception):
    def __init__(self, msg, status=400):
        super().__init__(msg)
        self.status = status


def db():
    c = S.connect()
    c.executescript(SCHEMA)
    return c


def root():
    d = K.STATE / "files"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def blob(fid):
    if not re.fullmatch(r"[0-9a-f]{32}", fid or ""):
        raise FileError("bad file id", 404)
    return root() / fid


def now():
    return datetime.datetime.now(S.TZ)


# ---------- names, expiry, quota ----------

def clean_name(name, default="file"):
    """A display name: no directories, no control characters, no leading dots, at most 180 characters."""
    n = unicodedata.normalize("NFC", str(name or ""))
    n = n.replace("\\", "/").split("/")[-1]
    n = "".join(ch for ch in n if unicodedata.category(ch)[0] != "C")
    n = re.sub(r"\s+", " ", n).strip().lstrip(".").strip()
    if len(n) > 180:
        stem, ext = os.path.splitext(n)
        n = stem[:180 - len(ext[:20])] + ext[:20]
    return n or default


def parse_expiry(value, who="owner"):
    """'1d' | '7d' | 'never' | 'YYYY-MM-DD HH:MM' (IST) | ISO time -> ISO string or None (never)."""
    v = str(value or "7d").strip().lower()
    if v in ("never", "none"):
        if who.startswith("token:"):
            raise FileError("never-expiring files can only be made by the owner")
        return None
    if v in ("1d", "1 day", "day"):
        t = now() + datetime.timedelta(days=1)
    elif v in ("7d", "1w", "1 week", "week"):
        t = now() + datetime.timedelta(days=7)
    else:
        try:
            t = datetime.datetime.fromisoformat(str(value).strip().replace("T", " ").replace("Z", "+00:00"))
        except ValueError:
            raise FileError("expiry: 1d, 7d, never, or a time like 2026-12-01 18:00 (IST)")
        if t.tzinfo is None:
            t = t.replace(tzinfo=S.TZ)
    if t <= now():
        raise FileError("expiry must be in the future")
    if t > now() + datetime.timedelta(days=MAX_DAYS, minutes=5):
        raise FileError(f"expiry can be at most {MAX_DAYS} days ahead (or never, for the owner)")
    return t.isoformat(timespec="seconds")


def quota():
    return int(S.get_setting("files_quota_bytes") or DEFAULT_QUOTA)


def set_quota(gb, who="owner", ip=""):
    try:
        b = int(float(gb) * 1024 ** 3)
    except (TypeError, ValueError):
        raise FileError("quota: a number of GB")
    if not 1024 ** 3 <= b <= 2 * 1024 ** 4:
        raise FileError("quota: between 1 and 2048 GB")
    before = quota()
    S.set_setting("files_quota_bytes", b)
    S.audit("files quota", "", {"bytes": before}, {"bytes": b}, who, ip)
    return b


def used(c=None):
    return int((c or db()).execute("SELECT COALESCE(SUM(size), 0) s FROM files_meta").fetchone()["s"])


def usage():
    c = db()
    return {"used": used(c), "quota": quota(), "files": c.execute("SELECT COUNT(*) n FROM files_meta").fetchone()["n"],
            "disk_free": shutil.disk_usage(root()).free}


def _room(extra, replacing=0):
    q = quota()
    if used() - replacing + extra > q:
        raise FileError(f"storage is full: {_fmt(used())} of {_fmt(q)} used; delete files or raise the quota in Files", 507)


def _fmt(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


# ---------- folders ----------

def _folder(c, fid):
    if fid in (None, "", 0, "0"):
        return None
    try:
        fid = int(fid)
    except (TypeError, ValueError):
        raise FileError("folder id must be a number", 404)
    r = c.execute("SELECT * FROM file_folders WHERE id=?", (fid,)).fetchone()
    if not r:
        raise FileError(f"no folder {fid}", 404)
    return dict(r)


def path_of(c, fid):
    parts, seen = [], set()
    while fid and fid not in seen:
        seen.add(fid)
        r = c.execute("SELECT id, name, parent_id FROM file_folders WHERE id=?", (fid,)).fetchone()
        if not r:
            break
        parts.append(r["name"])
        fid = r["parent_id"]
    return "/" + "/".join(reversed(parts))


def folders():
    c = db()
    out = [dict(r) for r in c.execute("SELECT * FROM file_folders ORDER BY name COLLATE NOCASE")]
    counts = {r["folder_id"]: (r["n"], r["s"]) for r in c.execute("SELECT folder_id, COUNT(*) n, SUM(size) s FROM files_meta GROUP BY folder_id")}
    for f in out:
        f["path"] = path_of(c, f["id"])
        f["files"], f["bytes"] = counts.get(f["id"], (0, 0))
    return out


def create_folder(name, parent_id=None, who="owner", ip=""):
    c = db()
    parent = _folder(c, parent_id)
    n = clean_name(name, "")
    if not n:
        raise FileError("folder name is empty")
    pid = parent["id"] if parent else None
    if c.execute("SELECT 1 FROM file_folders WHERE name=? AND parent_id IS ?", (n, pid)).fetchone():
        raise FileError(f"a folder named {n} already exists there", 409)
    cur = c.execute("INSERT INTO file_folders (name, parent_id, created, updated) VALUES (?, ?, ?, ?)", (n, pid, S.now(), S.now()))
    S.audit("folder created", str(cur.lastrowid), None, {"name": n, "parent_id": pid}, who, ip)
    return get_folder(cur.lastrowid)


def get_folder(fid):
    c = db()
    f = _folder(c, fid)
    if not f:
        raise FileError("the root is not a folder", 404)
    f["path"] = path_of(c, f["id"])
    return f


def update_folder(fid, name=None, parent_id=False, who="owner", ip=""):
    """Rename (name) and/or move (parent_id: an id, or None/0 for the top level). parent_id False = not moving."""
    c = db()
    f = _folder(c, fid)
    if not f:
        raise FileError("no folder", 404)
    new = {}
    if name is not None:
        n = clean_name(name, "")
        if not n:
            raise FileError("folder name is empty")
        new["name"] = n
    if parent_id is not False:
        p = _folder(c, parent_id)
        pid = p["id"] if p else None
        x = pid
        while x:                                    # no cycles: the new parent must not be inside this folder
            if x == f["id"]:
                raise FileError("a folder can not move into itself or its own subfolder")
            x = c.execute("SELECT parent_id FROM file_folders WHERE id=?", (x,)).fetchone()["parent_id"]
        new["parent_id"] = pid
    if not new:
        raise FileError("send name and/or parent_id")
    n, pid = new.get("name", f["name"]), new.get("parent_id", f["parent_id"])
    if c.execute("SELECT 1 FROM file_folders WHERE name=? AND parent_id IS ? AND id<>?", (n, pid, f["id"])).fetchone():
        raise FileError(f"a folder named {n} already exists there", 409)
    c.execute("UPDATE file_folders SET name=?, parent_id=?, updated=? WHERE id=?", (n, pid, S.now(), f["id"]))
    S.audit("folder changed", str(f["id"]), {"name": f["name"], "parent_id": f["parent_id"]}, new, who, ip)
    return get_folder(f["id"])


def _subtree(c, fid):
    out, todo = [], [fid]
    while todo:
        x = todo.pop()
        out.append(x)
        todo += [r["id"] for r in c.execute("SELECT id FROM file_folders WHERE parent_id=?", (x,))]
    return out


def delete_folder(fid, confirm=False, who="owner", ip=""):
    c = db()
    f = _folder(c, fid)
    if not f:
        raise FileError("no folder", 404)
    ids = _subtree(c, f["id"])
    q = ",".join("?" * len(ids))
    files = [r["id"] for r in c.execute(f"SELECT id FROM files_meta WHERE folder_id IN ({q})", ids)]
    if (files or len(ids) > 1) and not confirm:
        raise FileError(f"{f['name']} holds {len(files)} file(s) and {len(ids) - 1} folder(s); send confirm: true to delete them all", 409)
    for x in files:
        _drop(c, x)
    c.execute(f"DELETE FROM file_folders WHERE id IN ({q})", ids)
    S.audit("folder deleted", str(f["id"]), {"name": f["name"], "files": len(files), "folders": len(ids)}, None, who, ip)
    return {"deleted_files": len(files), "deleted_folders": len(ids)}


# ---------- files ----------

def mime_of(name):
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def inline(mime):
    return mime in INLINE or mime.startswith(INLINE_PREFIX)


def link(r, base=""):
    return f"{base}/f/{r['token']}/{urllib.parse.quote(r['name'])}"


def info(r, base=""):
    r = dict(r)
    r["url"] = link(r, base)
    r["inline"] = inline(r["mime"])
    c = db()
    r["folder_path"] = path_of(c, r["folder_id"]) if r["folder_id"] else "/"
    return r


def _row(c, fid):
    r = c.execute("SELECT * FROM files_meta WHERE id=?", (fid,)).fetchone()
    if not r:
        raise FileError(f"no file {fid}", 404)
    return dict(r)


def list_files(folder_id=None, search="", everywhere=False, base=""):
    c = db()
    q, a = "SELECT * FROM files_meta", []
    where = []
    if not everywhere:
        f = _folder(c, folder_id)
        where.append("folder_id IS ?"); a.append(f["id"] if f else None)
    if search:
        where.append("name LIKE ?"); a.append(f"%{search}%")
    if where:
        q += " WHERE " + " AND ".join(where)
    q += " ORDER BY created DESC"
    return [info(r, base) for r in c.execute(q, a)]


def get_file(fid, base=""):
    return info(_row(db(), fid), base)


def _store_stream(chunks, limit):
    """Write chunks to a new blob; returns (id, size, sha256). Over the limit or quota: nothing is kept."""
    fid = secrets.token_hex(16)
    dst, tmp = blob(fid), root() / f"{fid}.part"
    h, size = hashlib.sha256(), 0
    room = quota() - used()
    try:
        with open(tmp, "wb") as out:
            for chunk in chunks:
                size += len(chunk)
                if size > limit:
                    raise FileError(f"the file is over {_fmt(limit)}", 413)
                if size > room:
                    raise FileError(f"storage is full: {_fmt(used())} of {_fmt(quota())} used; delete files or raise the quota", 507)
                h.update(chunk)
                out.write(chunk)
        os.chmod(tmp, 0o600)
        os.replace(tmp, dst)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    return fid, size, h.hexdigest()


def add(name, chunks, folder_id=None, expiry="7d", who="owner", ip="", limit=MAX_UI, base=""):
    c = db()
    folder = _folder(c, folder_id)
    exp = parse_expiry(expiry, who)
    n = clean_name(name)
    fid, size, sha = _store_stream(chunks, limit)
    tok = secrets.token_urlsafe(32)                  # 43 characters
    c.execute("INSERT INTO files_meta (id, token, name, folder_id, size, mime, sha256, created, updated, expires_at, who) "
              "VALUES (?,?,?,?,?,?,?,?,?,?,?)", (fid, tok, n, folder["id"] if folder else None, size, mime_of(n), sha,
                                                   S.now(), S.now(), exp, who))
    S.audit("file uploaded", fid, None, {"name": n, "bytes": size, "folder_id": folder and folder["id"], "expires_at": exp}, who, ip)
    return get_file(fid, base)


def replace(fid, chunks, who="owner", ip="", limit=MAX_UI, name=None, base=""):
    c = db()
    old = _row(c, fid)
    new_id, size, sha = _store_stream(chunks, limit + 0)
    if used() - old["size"] + size > quota():
        blob(new_id).unlink(missing_ok=True)
        raise FileError("storage is full", 507)
    os.replace(blob(new_id), blob(fid))
    n = clean_name(name) if name else old["name"]
    c.execute("UPDATE files_meta SET size=?, sha256=?, name=?, mime=?, updated=? WHERE id=?", (size, sha, n, mime_of(n), S.now(), fid))
    S.audit("file replaced", fid, {"bytes": old["size"], "sha256": old["sha256"]}, {"bytes": size, "sha256": sha}, who, ip)
    return get_file(fid, base)


def update(fid, name=None, folder_id=False, expiry=None, new_link=False, who="owner", ip="", base=""):
    c = db()
    old = _row(c, fid)
    new = {}
    if name is not None:
        new["name"] = clean_name(name)
        new["mime"] = mime_of(new["name"])
    if folder_id is not False:
        f = _folder(c, folder_id)
        new["folder_id"] = f["id"] if f else None
    if expiry is not None:
        new["expires_at"] = parse_expiry(expiry, who)
    if new_link:
        new["token"] = secrets.token_urlsafe(32)
    if not new:
        raise FileError("send name, folder_id, expiry or new_link")
    sets = ", ".join(f"{k}=?" for k in new) + ", updated=?"
    c.execute(f"UPDATE files_meta SET {sets} WHERE id=?", (*new.values(), S.now(), fid))
    S.audit("file changed", fid, {k: old[k] for k in new if k != "token"}, {k: v for k, v in new.items() if k != "token"}
            | ({"new_link": True} if new_link else {}), who, ip)
    return get_file(fid, base)


def _drop(c, fid):
    c.execute("DELETE FROM files_meta WHERE id=?", (fid,))
    blob(fid).unlink(missing_ok=True)


def delete(fid, who="owner", ip=""):
    c = db()
    old = _row(c, fid)
    _drop(c, fid)
    S.audit("file deleted", fid, {"name": old["name"], "bytes": old["size"]}, None, who, ip)
    return {"deleted": fid}


def by_token(token):
    """The file for a public link, or None (unknown or expired; an expired one is deleted on the spot)."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token or ""):
        return None
    c = db()
    r = c.execute("SELECT * FROM files_meta WHERE token=?", (token,)).fetchone()
    if not r:
        return None
    r = dict(r)
    if r["expires_at"] and datetime.datetime.fromisoformat(r["expires_at"]) <= now():
        _drop(c, r["id"])
        S.audit("file expired", r["id"], {"name": r["name"]}, None, "sweeper", "")
        return None
    p = blob(r["id"])
    return (r, p) if p.is_file() else None


def sweep():
    c = db()
    t = now()
    gone = []
    for r in c.execute("SELECT id, name, expires_at FROM files_meta WHERE expires_at IS NOT NULL").fetchall():
        if datetime.datetime.fromisoformat(r["expires_at"]) <= t:
            _drop(c, r["id"])
            gone.append(r["id"])
            S.audit("file expired", r["id"], {"name": r["name"]}, None, "sweeper", "")
    known = {r["id"] for r in c.execute("SELECT id FROM files_meta")}
    for p in root().iterdir():                      # blobs without metadata (a crash mid-upload)
        if p.name.endswith(".part") and (t.timestamp() - p.stat().st_mtime) > 6 * 3600:
            p.unlink(missing_ok=True)
        elif re.fullmatch(r"[0-9a-f]{32}", p.name) and p.name not in known and (t.timestamp() - p.stat().st_mtime) > 3600:
            p.unlink(missing_ok=True)
    return gone


# ---------- fetching a URL (MCP) ----------

def _public_host(host):
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise FileError(f"can not resolve {host}")
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FileError("only public http(s) URLs can be fetched")


def url_chunks(url):
    u = urllib.parse.urlparse(url)
    if u.scheme not in ("http", "https") or not u.hostname:
        raise FileError("url must be http or https")
    _public_host(u.hostname)

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            _public_host(urllib.parse.urlparse(newurl).hostname or "")
            return super().redirect_request(req, fp, code, msg, headers, newurl)

    opener = urllib.request.build_opener(NoRedirect)
    resp = opener.open(urllib.request.Request(url, headers={"User-Agent": "reels-studio"}), timeout=60)

    def gen():
        with resp:
            while True:
                b = resp.read(1024 * 1024)
                if not b:
                    return
                yield b
    name = os.path.basename(u.path) or "download"
    return name, gen()


if __name__ == "__main__":
    if sys.argv[1:] == ["sweep"]:
        g = sweep()
        if g:
            print(f"deleted {len(g)} expired file(s)")
    else:
        sys.exit(__doc__)
