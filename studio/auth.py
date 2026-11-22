"""Password login, signed session cookies, CSRF tokens, login rate limit and API tokens.

auth.json (mode 600) holds only the scrypt hash of the password, the cookie signing secret, hashed API tokens and the
scrypt hash of the MCP/API key (set with `python3.11 -m studio mcp-key`, rotated or revoked in Settings).
On first start a password is generated, printed once and written to initial-password.txt (mode 600).
"""
import base64, hashlib, hmac, json, os, secrets, time

from . import CONFIG_DIR

COOKIE = "rs_session"
SESSION_DAYS = 14
SCRYPT = {"n": 2 ** 14, "r": 8, "p": 1, "dklen": 32}


def _paths():
    return CONFIG_DIR / "auth.json", CONFIG_DIR / "initial-password.txt"


def _write_private(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(path.parent, 0o700)
    fd = os.open(str(path) + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(str(path) + ".tmp", path)
    os.chmod(path, 0o600)


def hash_password(pw, salt=None):
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, n=SCRYPT["n"], r=SCRYPT["r"], p=SCRYPT["p"], dklen=SCRYPT["dklen"])
    return {"salt": base64.b64encode(salt).decode(), "hash": base64.b64encode(dk).decode(), **SCRYPT}


def check_password(pw, rec):
    try:
        dk = hashlib.scrypt(pw.encode(), salt=base64.b64decode(rec["salt"]), n=rec["n"], r=rec["r"], p=rec["p"], dklen=rec["dklen"])
    except (ValueError, KeyError, TypeError):
        return False
    return hmac.compare_digest(dk, base64.b64decode(rec["hash"]))


def load():
    path, _ = _paths()
    return json.loads(path.read_text()) if path.exists() else None


def save(data):
    path, _ = _paths()
    _write_private(path, json.dumps(data, indent=1))


def ensure(printer=print):
    """Create auth.json with a generated password if it does not exist. Returns the auth record."""
    data = load()
    if data:
        return data
    pw = secrets.token_urlsafe(15)
    data = {"password": hash_password(pw), "secret": secrets.token_hex(32), "tokens": {}, "created": int(time.time())}
    save(data)
    _, initial = _paths()
    _write_private(initial, pw + "\n")
    printer("=" * 64)
    printer(f"Reels Studio first start. Password: {pw}")
    printer(f"(also saved to {initial}, mode 600; delete that file once you have it)")
    printer("=" * 64)
    return data


def set_password(new):
    if len(new) < 8:
        raise ValueError("use at least 8 characters")
    data = load()
    data["password"] = hash_password(new)
    data["secret"] = secrets.token_hex(32)          # rotating the secret signs every old session out
    save(data)
    _, initial = _paths()
    if initial.exists():
        initial.unlink()
    return data


# ---------- sessions ----------

def _b64(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(secret, msg):
    return _b64(hmac.new(bytes.fromhex(secret), msg.encode(), hashlib.sha256).digest())


def make_session(secret, user="owner", now=None):
    now = int(now or time.time())
    body = _b64(json.dumps({"u": user, "sid": secrets.token_hex(12), "iat": now, "exp": now + SESSION_DAYS * 86400}).encode())
    return f"{body}.{_sign(secret, 's:' + body)}"


def read_session(secret, cookie, now=None):
    if not cookie or "." not in cookie:
        return None
    body, sig = cookie.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(secret, "s:" + body)):
        return None
    try:
        data = json.loads(_unb64(body))
    except (ValueError, TypeError):
        return None
    if data.get("exp", 0) < (now or time.time()):
        return None
    return data


def csrf_token(secret, sess):
    return _sign(secret, "csrf:" + sess["sid"])


def check_csrf(secret, sess, token):
    return bool(token) and hmac.compare_digest(token, csrf_token(secret, sess))


# ---------- API tokens (for agents; sent as Authorization: Bearer <token>, no CSRF needed) ----------

def create_token(name):
    data = load()
    tok = "rst_" + secrets.token_urlsafe(24)
    data.setdefault("tokens", {})[name] = {"sha256": hashlib.sha256(tok.encode()).hexdigest(), "created": int(time.time())}
    save(data)
    return tok


def revoke_token(name):
    data = load()
    data.get("tokens", {}).pop(name, None)
    save(data)


def check_token(data, tok):
    if not tok:
        return None
    h = hashlib.sha256(tok.encode()).hexdigest()
    for name, rec in (data.get("tokens") or {}).items():
        if hmac.compare_digest(h, rec["sha256"]):
            return name
    return None


# ---------- login rate limit ----------

class RateLimit:
    """At most `per_ip` failed logins per IP and `total` overall in `window` seconds."""

    def __init__(self, per_ip=5, total=30, window=900):
        self.per_ip, self.total, self.window = per_ip, total, window
        self.fails = {}

    def _recent(self, key, now):
        self.fails[key] = [t for t in self.fails.get(key, []) if now - t < self.window]
        return self.fails[key]

    def blocked(self, ip, now=None):
        now = now or time.time()
        return len(self._recent(ip, now)) >= self.per_ip or len(self._recent("*", now)) >= self.total

    def fail(self, ip, now=None):
        now = now or time.time()
        for k in (ip, "*"):
            self._recent(k, now).append(now)

    def ok(self, ip):
        self.fails.pop(ip, None)


# ---------- the MCP / API key (one owner key; only its scrypt hash is stored) ----------

KEY_MIN = 8           # the owner chose a short key; 10 wrong keys from one IP lock it out
_verified = {}          # sha256(key) -> the stored hash it matched, so scrypt runs once per key, not per request


def set_key(key):
    """Store the scrypt hash of a new key (replaces the old one). The key itself is never written anywhere."""
    if not key or len(key) < KEY_MIN or any(c.isspace() for c in key):
        raise ValueError(f"the key must be at least {KEY_MIN} characters with no spaces")
    data = ensure(printer=lambda *a: None)
    data["mcp_key"] = {**hash_password(key), "created": int(time.time())}
    save(data)
    _verified.clear()
    return data["mcp_key"]["created"]


def new_key():
    key = "rsk_" + secrets.token_urlsafe(32)
    set_key(key)
    return key


def revoke_key():
    data = load() or {}
    had = data.pop("mcp_key", None) is not None
    save(data)
    _verified.clear()
    return had


def key_info(data):
    rec = (data or {}).get("mcp_key")
    return {"set": bool(rec), "created": rec.get("created") if rec else None}


def check_key(data, key):
    rec = (data or {}).get("mcp_key")
    if not key or not rec:
        return False
    d = hashlib.sha256(key.encode()).hexdigest()
    if _verified.get(d) == rec["hash"]:
        return True
    if check_password(key, rec):
        _verified[d] = rec["hash"]
        return True
    return False


_mtime = [0.0]


def reload_if_changed(current):
    """auth.json changed on disk (the CLI set or revoked the key, or a token was made) -> the new record."""
    path, _ = _paths()
    try:
        m = path.stat().st_mtime
    except OSError:
        return current
    if current is not None and m == _mtime[0]:
        return current
    _mtime[0] = m
    return load() or current
