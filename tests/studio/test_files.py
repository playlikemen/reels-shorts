"""File hosting: upload/download, the /f/ safety headers, expiry sweep, folders, quota, traversal, auth."""
import base64, datetime, json, secrets

import pytest
from starlette.testclient import TestClient

import config as K
from studio import app as W, auth as A, files as F, store as S


@pytest.fixture
def client(isolated, monkeypatch):
    W.STATE_REF.limiter = A.RateLimit()
    W.STATE_REF.key_limiter = A.RateLimit(per_ip=10, total=10 ** 9, window=900)
    with TestClient(W.create_app()) as c:
        pw = (isolated / "config" / "initial-password.txt").read_text().strip()
        c.headers["x-csrf-token"] = c.post("/api/login", json={"password": pw}).json()["csrf"]
        c.key = "test-" + secrets.token_urlsafe(24)
        A.set_key(c.key)
        yield c


def up(c, name, data, **form):
    r = c.post("/api/files", files={"file": (name, data)}, data=form)
    assert r.status_code == 201, r.text
    return r.json()


def public(c, url):
    path = url.split("://", 1)[-1]
    path = path[path.index("/f/"):]
    anon = TestClient(W.create_app())       # a stranger: no cookie, no key
    return anon.get(path)


def test_upload_and_download_with_safe_headers(client):
    f = up(client, "notes.txt", b"hello world", expiry="1d")
    assert f["size"] == 11 and f["inline"] and len(f["url"].split("/f/")[1].split("/")[0]) >= 32
    r = public(client, f["url"])
    assert r.status_code == 200 and r.content == b"hello world"
    assert r.headers["content-type"].startswith("text/plain") and r.headers["content-disposition"].startswith("inline")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"
    assert "set-cookie" not in r.headers


@pytest.mark.parametrize("name", ["page.html", "logo.svg", "app.js", "x.exe", "noext"])
def test_active_content_never_renders_inline(client, name):
    f = up(client, name, b"<script>alert(document.cookie)</script>")
    r = public(client, f["url"])
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["content-type"] == "application/octet-stream"
    assert r.headers["content-security-policy"] == "sandbox; default-src 'none'"


def test_range_requests_for_media(client):
    data = bytes(range(256)) * 40
    f = up(client, "clip.mp4", data)
    path = f["url"][f["url"].index("/f/"):]
    r = TestClient(W.create_app()).get(path, headers={"range": "bytes=10-19"})
    assert r.status_code == 206 and r.content == data[10:20] and r.headers["content-disposition"].startswith("inline")


def test_no_cookie_read_on_public_links(client):
    f = up(client, "a.png", b"\x89PNG....")
    path = f["url"][f["url"].index("/f/"):]
    r = client.get(path)                     # the owner's cookie is sent, but nothing is set or changed
    assert r.status_code == 200 and "set-cookie" not in r.headers
    assert client.post(path).status_code == 405
    assert TestClient(W.create_app()).get("/f/" + "x" * 40 + "/a.png").status_code == 404


def test_writes_and_listing_need_login_or_key(client):
    anon = TestClient(W.create_app())
    assert anon.get("/api/files").status_code == 401
    assert anon.post("/api/files", files={"file": ("a.txt", b"x")}).status_code == 401
    assert anon.post("/api/folders", json={"name": "x"}).status_code == 401
    # the API key works without CSRF
    r = anon.post("/api/files", files={"file": ("k.txt", b"key upload")}, headers={"x-api-key": client.key})
    assert r.status_code == 201
    # anonymous MCP can not list or upload
    res = anon.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                  "params": {"name": "upload_file", "arguments": {"name": "m.txt", "content_base64": "eA=="}}}).json()["result"]
    assert res["isError"] and "requires API key" in res["content"][0]["text"]
    res = anon.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "list_files"}}).json()["result"]
    assert res["isError"]
    assert S.connect().execute("SELECT COUNT(*) n FROM audit WHERE action='file uploaded'").fetchone()["n"] == 1


def test_mcp_upload_list_update_delete(client):
    h = {"authorization": f"Bearer {client.key}"}

    def call(name, args):
        r = client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, headers=h)
        assert r.status_code == 200, r.text[:2000]
        res = r.json()["result"]
        try:
            return res["isError"], json.loads(res["content"][0]["text"])
        except ValueError:
            raise AssertionError(res["content"][0]["text"][:500])
    err, folder = call("create_folder", {"name": "Briefs"})
    assert not err
    err, f = call("upload_file", {"name": "brief.pdf", "content_base64": base64.b64encode(b"%PDF-1.4 x").decode(), "folder_id": folder["id"]})
    assert not err and f["folder_path"] == "/Briefs" and f["mime"] == "application/pdf"
    err, lst = call("list_files", {"folder_id": folder["id"]})
    assert [x["id"] for x in lst["files"]] == [f["id"]]
    err, g = call("update_file", {"id": f["id"], "name": "brief-v2.pdf", "folder_id": None, "new_link": True})
    assert not err and g["name"] == "brief-v2.pdf" and g["folder_path"] == "/" and g["token"] != f["token"]
    assert public(client, f["url"]).status_code == 404            # the old link is dead
    err, d = call("delete_file", {"id": f["id"]})
    assert not err and public(client, g["url"]).status_code == 404
    err, d = call("upload_file", {"name": "big.bin", "content_base64": "A" * (F.MAX_MCP * 4 // 3 + 100)})
    assert err and "25 MB" in d["error"]
    audit = S.connect().execute("SELECT after FROM audit WHERE action='mcp upload_file'").fetchall()
    assert audit and all("AAAAAAAA" not in (a["after"] or "") and "JVBERi0" not in (a["after"] or "") for a in audit)


def test_expiry_and_sweep(client, monkeypatch):
    f = up(client, "soon.txt", b"bye", expiry="1d")
    never = up(client, "keep.txt", b"stay", expiry="never")
    assert never["expires_at"] is None
    later = datetime.datetime.now(S.TZ) + datetime.timedelta(days=2)
    monkeypatch.setattr(F, "now", lambda: later)
    assert F.sweep() == [f["id"]]
    assert not F.blob(f["id"]).exists() and F.blob(never["id"]).exists()
    assert public(client, f["url"]).status_code == 404
    with pytest.raises(F.FileError):
        F.parse_expiry((later + datetime.timedelta(days=91)).strftime("%Y-%m-%d %H:%M"))
    with pytest.raises(F.FileError):
        F.parse_expiry("never", who="token:bot")
    with pytest.raises(F.FileError):
        F.parse_expiry("2001-01-01 10:00")


def test_folders_move_rename_delete_with_confirm(client):
    a = client.post("/api/folders", json={"name": "A"}).json()
    b = client.post("/api/folders", json={"name": "B", "parent_id": a["id"]}).json()
    assert b["path"] == "/A/B"
    assert client.patch(f"/api/folders/{a['id']}", json={"parent_id": b["id"]}).status_code == 400   # no cycles
    assert client.patch(f"/api/folders/{b['id']}", json={"name": "Bee", "parent_id": None}).json()["path"] == "/Bee"
    up(client, "in-a.txt", b"x", folder_id=str(a["id"]))
    r = client.delete(f"/api/folders/{a['id']}")
    assert r.status_code == 409 and "confirm" in r.json()["error"]
    r = client.delete(f"/api/folders/{a['id']}?confirm=true")
    assert r.status_code == 200 and r.json() == {"deleted_files": 1, "deleted_folders": 1}
    assert client.delete(f"/api/folders/{b['id']}").status_code == 200      # empty: no confirm needed


def test_quota(client):
    S.set_setting("files_quota_bytes", 100)
    up(client, "a.bin", b"x" * 60)
    r = client.post("/api/files", files={"file": ("b.bin", b"x" * 60)})
    assert r.status_code == 507 and "storage is full" in r.json()["error"]
    assert F.usage()["used"] == 60 and len(list(F.root().iterdir())) == 1      # nothing half-written is kept


def test_names_can_not_traverse(client):
    for bad in ["../../etc/passwd", "..\\..\\x.txt", "/abs/path.txt", ".hidden", "a\x00b\nc.txt"]:
        f = up(client, bad, b"x")
        assert "/" not in f["name"] and "\\" not in f["name"] and not f["name"].startswith(".") and "\x00" not in f["name"]
        assert F.blob(f["id"]).parent == F.root()
    assert F.clean_name("../../etc/passwd") == "passwd"
    with pytest.raises(F.FileError):
        F.blob("../../etc/passwd")
    assert client.get("/api/files/..%2F..%2Fetc").status_code == 404
    anon = TestClient(W.create_app())
    assert anon.get("/f/%2e%2e/%2e%2e/etc/passwd").status_code == 404
    r = anon.get("/f/../../etc/passwd", follow_redirects=False)      # the client folds this to /etc/passwd: the login redirect
    assert r.status_code in (303, 404) and "root:" not in r.text
