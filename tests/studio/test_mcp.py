"""The /mcp endpoint: JSON-RPC handshake, tool list, redaction without a key, key auth, lockout, publish confirm."""
import json, secrets

import pytest
from starlette.testclient import TestClient

import config as K
from conftest import row, seed
from studio import app as W, auth as A, mcp as M, store as S

DRIVE = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp"
MP4 = "https://drive.google.com/uc?export=download&id=1ZzYyXx"


@pytest.fixture
def mcp(isolated, fake, monkeypatch):
    W.STATE_REF.key_limiter = A.RateLimit(per_ip=10, total=10 ** 9, window=900)
    monkeypatch.setattr(W, "ROOT", isolated)
    mp4 = isolated / "out/craftlayer/CR-901-EN/cr-901-en.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"\0" * (K.MIN_MP4_BYTES + 10))
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Google Drive Folder": DRIVE, "Direct MP4 Download Link": MP4,
                                                    "YouTube Best SEO Description": f"watch {MP4} now"})]
    seed()
    key = "test-" + secrets.token_urlsafe(24)          # made up per run; no real key in tests
    A.ensure(printer=lambda *a: None)
    A.set_key(key)
    with TestClient(W.create_app()) as c:
        c.key = key
        c.submitted = []
        monkeypatch.setattr(W.STATE_REF.queue, "submit", lambda kind, params=None, who="", **kw: c.submitted.append((kind, params, who)) or 91)
        yield c


def rpc(c, method, params=None, key=None, rid=1, header="authorization"):
    h = {}
    if key:
        h = {"authorization": f"Bearer {key}"} if header == "authorization" else {"x-api-key": key}
    return c.post("/mcp", json={"jsonrpc": "2.0", "id": rid, "method": method, "params": params or {}}, headers=h)


def tool(c, name, args=None, key=None, header="authorization"):
    r = rpc(c, "tools/call", {"name": name, "arguments": args or {}}, key, header=header)
    assert r.status_code == 200, r.text
    res = r.json()["result"]
    return res["isError"], json.loads(res["content"][0]["text"])


def test_handshake_and_tools_list(mcp):
    r = rpc(mcp, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}})
    res = r.json()["result"]
    assert res["protocolVersion"] == "2025-06-18" and res["serverInfo"]["name"] == "reels-studio" and "tools" in res["capabilities"]
    assert mcp.post("/mcp", json={"jsonrpc": "2.0", "method": "notifications/initialized"}).status_code == 202
    names = {t["name"] for t in rpc(mcp, "tools/list").json()["result"]["tools"]}
    assert {"list_reels", "get_reel", "list_channels", "calendar", "insights_summary", "list_jobs", "get_job", "health",
            "edit_reel", "publish_instagram", "publish_youtube", "bulk_publish", "upload_video", "reply_comment"} <= names
    assert mcp.get("/mcp").status_code == 405
    assert rpc(mcp, "nope").json()["error"]["code"] == -32601


def test_no_key_read_hides_private_fields(mcp):
    err, d = tool(mcp, "get_reel", {"id": "CR-901-EN"})
    assert not err and d["reel"]["Video ID"] == "CR-901-EN"
    text = json.dumps(d)
    assert "drive.google.com" not in text and "/media/" not in text and "Local Path" not in text
    assert "Google Drive Folder" not in d["reel"] and "Direct MP4 Download Link" not in d["reel"]
    assert d["reel"]["YouTube Best SEO Description"] == "watch [private link] now"
    err, d = tool(mcp, "list_reels", {"channel": "craftlayer"})
    assert not err and d["count"] == 1 and "drive.google.com" not in json.dumps(d)
    err, d = tool(mcp, "health")
    assert not err and all("account" not in a for a in d["accounts"])


def test_no_key_write_is_refused(mcp):
    err, d = tool(mcp, "edit_reel", {"id": "CR-901-EN", "fields": {"Instagram Hashtags": "#x"}})
    assert err and "requires API key" in d["error"]
    err, d = tool(mcp, "publish_instagram", {"id": "CR-901-EN", "confirm": True})
    assert err and mcp.submitted == []
    assert S.get_reel("CR-901-EN")["Instagram Hashtags"] == ""
    # a browser session is not a key on /mcp (no CSRF there)
    assert mcp.post("/api/reels/CR-901-EN/hold", json={}).status_code == 401


def test_keyed_write_works_and_is_audited(mcp):
    err, d = tool(mcp, "edit_reel", {"id": "CR-901-EN", "fields": {"Instagram Hashtags": "#mcp"}}, mcp.key)
    assert not err and d["status"] == "ok"
    assert S.get_reel("CR-901-EN")["Instagram Hashtags"] == "#mcp"
    who = [r["who"] for r in S.connect().execute("SELECT who FROM audit WHERE target='CR-901-EN'")]
    assert who.count("mcp-key") >= 2                                  # the edit itself and the mcp call
    err, d = tool(mcp, "get_reel", {"id": "CR-901-EN"}, mcp.key, header="x-api-key")
    assert d["reel"]["Google Drive Folder"] == DRIVE                  # private fields with the key


def test_key_works_on_rest_without_csrf_but_not_settings(mcp):
    h = {"x-api-key": mcp.key}
    r = mcp.post("/api/reels/CR-901-EN/hold", json={"hold": True}, headers=h)
    assert r.status_code == 200 and S.get_reel("CR-901-EN")["Instagram Status"] == "Hold"
    assert mcp.post("/api/settings/password", json={"password": "x" * 20}, headers=h).status_code == 403
    assert mcp.post("/api/settings/mcp-key/rotate", json={}, headers=h).status_code == 403


def test_bad_keys_lock_the_ip_out(mcp):
    for _ in range(10):
        err, d = tool(mcp, "edit_reel", {"id": "CR-901-EN", "fields": {"Instagram Hashtags": "#x"}}, "wrong-" + "x" * 30)
        assert err and "wrong" in d["error"]                          # /mcp never answers 401: clients must still list tools
    assert mcp.get("/api/reels", headers={"x-api-key": "wrong-" + "y" * 30}).status_code == 429
    err, d = tool(mcp, "edit_reel", {"id": "CR-901-EN", "fields": {"Instagram Hashtags": "#x"}}, mcp.key)
    assert err and "locked out" in d["error"]                         # even the right key, for 15 minutes
    assert mcp.get("/api/reels", headers={"x-api-key": mcp.key}).status_code == 429
    assert S.get_reel("CR-901-EN")["Instagram Hashtags"] == ""


def test_remote_client_transport_details(mcp):
    h = {"accept": "application/json, text/event-stream"}
    r = mcp.post("/mcp/", json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26"}}, headers=h)
    assert r.status_code == 200 and r.json()["result"]["protocolVersion"] == "2025-03-26" and r.headers["mcp-session-id"]
    r = mcp.post("/mcp", json={"jsonrpc": "2.0", "id": 2, "method": "ping"}, headers={"accept": "text/event-stream"})
    assert r.headers["content-type"].startswith("text/event-stream") and r.headers["x-accel-buffering"] == "no"
    assert r.text.startswith("event: message\ndata: ") and json.loads(r.text.split("data: ", 1)[1])["result"] == {}
    for p in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-protected-resource/mcp",
              "/.well-known/oauth-authorization-server", "/.well-known/openid-configuration"):
        r = mcp.get(p, follow_redirects=False)
        assert r.status_code == 404 and r.json() == {"error": "not found"}
    r = mcp.post("/mcp?api_key=" + mcp.key, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                                 "params": {"name": "hold_reel", "arguments": {"id": "CR-901-EN"}}}, follow_redirects=False)
    assert r.status_code == 200 and not r.json()["result"]["isError"]
    assert mcp.delete("/mcp").status_code == 200


def test_publish_needs_confirm(mcp):
    err, d = tool(mcp, "publish_instagram", {"id": "CR-901-EN"}, mcp.key)
    assert err and "confirm" in d["error"] and mcp.submitted == []
    err, d = tool(mcp, "publish_instagram", {"id": "CR-901-EN", "dry_run": True}, mcp.key)
    assert not err and mcp.submitted[-1][:2] == ("publish", {"id": "CR-901-EN", "platform": "instagram", "dry_run": True})
    err, d = tool(mcp, "publish_instagram", {"id": "CR-901-EN", "confirm": True}, mcp.key)
    assert not err and d["job"] == 91 and mcp.submitted[-1][2] == "mcp-key"
    err, d = tool(mcp, "bulk_publish", {"ids": ["CR-901-EN"]}, mcp.key)
    assert err and "confirm" in d["error"]


def test_key_rotate_and_revoke(mcp):
    old = mcp.key
    assert old not in A._paths()[0].read_text()                      # only the scrypt hash is stored
    A.revoke_key()
    err, d = tool(mcp, "hold_reel", {"id": "CR-901-EN"}, old)
    assert err and "wrong or was revoked" in d["error"]
    assert A.key_info(A.load())["set"] is False and old not in A._paths()[0].read_text()
