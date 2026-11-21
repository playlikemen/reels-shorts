import time

import pytest
from starlette.testclient import TestClient

from studio import app as W, auth as A


@pytest.fixture
def client(isolated):
    W.STATE_REF.limiter = A.RateLimit()
    W.STATE_REF.conn_cache = None
    with TestClient(W.create_app()) as c:
        c.password = (isolated / "config" / "initial-password.txt").read_text().strip()
        yield c


def login(c, pw=None, **kw):
    return c.post("/api/login", json={"password": pw or c.password}, **kw)


def test_first_start_writes_private_password_and_hash_only(client, isolated):
    cfg = isolated / "config"
    assert oct((cfg / "initial-password.txt").stat().st_mode & 0o777) == "0o600"
    assert oct((cfg / "auth.json").stat().st_mode & 0o777) == "0o600"
    assert client.password not in (cfg / "auth.json").read_text()


def test_unauthenticated_requests(client):
    assert client.get("/api/reels").status_code == 401
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert client.get("/editor/", follow_redirects=False).status_code == 303
    assert client.get("/login").status_code == 200
    assert client.get("/healthz").text == "ok"


def test_wrong_password_and_rate_limit(client):
    for _ in range(5):
        assert login(client, "nope").status_code == 401
    r = login(client)                   # right password, but this IP is locked out now
    assert r.status_code == 429
    W.STATE_REF.limiter = A.RateLimit()
    assert login(client).status_code == 200


def test_login_cookie_and_csrf(client):
    r = login(client)
    assert r.status_code == 200
    csrf = r.json()["csrf"]
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc and "secure" not in sc      # plain http on 127.0.0.1
    assert client.get("/api/reels").status_code == 200
    assert client.get("/api/session").json()["csrf"] == csrf
    assert client.post("/api/sync", json={}).status_code == 403                 # no CSRF header
    assert client.post("/api/sync", json={}, headers={"x-csrf-token": "bad"}).status_code == 403
    assert client.post("/api/jobs", json={"kind": "nope"}, headers={"x-csrf-token": csrf}).status_code == 400


def test_secure_cookie_behind_https_proxy(client):
    r = login(client, headers={"x-forwarded-proto": "https"})
    assert "secure" in r.headers["set-cookie"].lower()


def test_cross_site_login_refused(client):
    assert login(client, headers={"origin": "https://evil.example"}).status_code == 403


def test_tampered_or_expired_session(client):
    secret = W.STATE_REF.auth["secret"]
    good = A.make_session(secret)
    body, sig = good.rsplit(".", 1)
    client.cookies.set(A.COOKIE, body + "x." + sig)
    assert client.get("/api/reels").status_code == 401
    client.cookies.set(A.COOKIE, A.make_session(secret, now=time.time() - 30 * 86400))
    assert client.get("/api/reels").status_code == 401
    client.cookies.set(A.COOKIE, good)
    assert client.get("/api/reels").status_code == 200


def test_bearer_token_needs_no_csrf(client):
    tok = A.create_token("agent")
    W.STATE_REF.auth = A.load()
    h = {"authorization": f"Bearer {tok}"}
    assert client.get("/api/reels", headers=h).status_code == 200
    assert client.post("/api/jobs", json={"kind": "nope"}, headers=h).status_code == 400   # past auth + CSRF
    assert client.get("/api/reels", headers={"authorization": "Bearer rst_wrong"}).status_code == 401


def test_password_change_signs_sessions_out(client):
    csrf = login(client).json()["csrf"]
    r = client.post("/api/settings/password", json={"current": client.password, "new": "a-new-password-123"}, headers={"x-csrf-token": csrf})
    assert r.status_code == 200
    assert client.get("/api/reels").status_code == 401
    assert login(client, "a-new-password-123").status_code == 200


def test_scrypt_roundtrip():
    rec = A.hash_password("correct horse")
    assert A.check_password("correct horse", rec) and not A.check_password("wrong", rec)
