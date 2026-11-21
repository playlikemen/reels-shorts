import fcntl, json

import pytest
from starlette.testclient import TestClient

import config as K
import scheduler
import sheet
from conftest import row
from studio import app as W, auth as A, publish_job as P, store as S, sync as Y


@pytest.fixture
def client(isolated, fake, monkeypatch):
    W.STATE_REF.limiter = A.RateLimit()
    monkeypatch.setattr(W, "ROOT", isolated)
    mp4 = isolated / "out/craftlayer/CR-901-EN/cr-901-en.mp4"
    mp4.parent.mkdir(parents=True)
    mp4.write_bytes(b"\0" * (K.MIN_MP4_BYTES + 10))
    fake.tabs["@craftlayer"] = [row("CR-901-EN"), row("CR-902-EN", **{"Instagram Status": "Hold"})]
    Y.pull()
    with TestClient(W.create_app()) as c:
        pw = (isolated / "config" / "initial-password.txt").read_text().strip()
        c.headers["x-csrf-token"] = c.post("/api/login", json={"password": pw}).json()["csrf"]
        c.submitted = []
        monkeypatch.setattr(W.STATE_REF.queue, "submit", lambda kind, params=None, who="", **kw: c.submitted.append((kind, params)) or 77)
        yield c


def test_publish_needs_confirm_and_queues_one_job(client):
    assert client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram"}).status_code == 400
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True})
    assert r.status_code == 202 and r.json()["job"] == 77
    assert client.submitted == [("publish", {"id": "CR-901-EN", "platform": "instagram", "dry_run": False})]


def test_publish_refuses_rows_that_are_published_or_have_no_channel(client):
    S.save_reel({"Video ID": "CR-902-EN", "Instagram Status": "Published"})
    r = client.post("/api/publish", json={"id": "CR-902-EN", "platform": "instagram", "confirm": True})
    assert r.status_code == 409 and "never posted" in r.json()["error"]
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "youtube", "confirm": True})
    assert r.status_code == 400
    assert client.submitted == []


def test_publish_respects_scheduler_lock(client):
    with open(K.STATE / "scheduler.lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True})
        assert r.status_code == 409 and r.json()["lock_busy"]
        assert client.get("/api/publish/preview?id=CR-901-EN&platform=instagram").json()["lock_busy"] is True
    assert client.submitted == []


def test_daily_cap_needs_override(client):
    cap = K.brand("craftlayer")["max_reels_per_day"]
    scheduler.LOG.write_text("".join(json.dumps({"video": f"CR-8{i:02d}-EN", "platform": "instagram", "status": "published",
                                                 "at": scheduler.now().isoformat()}) + "\n" for i in range(cap)))
    p = client.get("/api/publish/preview?id=CR-901-EN&platform=instagram").json()
    assert p["over_cap"] and p["cap"] == cap and p["posted_today"] == cap and p["handle"] == "@craftlayer.studio"
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True})
    assert r.status_code == 409 and r.json()["need_override"]
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True, "override_cap": True})
    assert r.status_code == 202


def test_publish_job_calls_scheduler_run_with_force_on_one_row(fake, isolated, monkeypatch):
    monkeypatch.setattr(K, "brands", K.brands)          # registered so monkeypatch restores what narrow() replaces
    monkeypatch.setattr(sheet, "rows", sheet.rows)
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"YouTube Status": "Ready"}), row("CR-902-EN")]
    fake.tabs["@StackShade"] = [row("SS-901")]
    seen = {}

    def run(publish, force=()):
        seen["args"] = (publish, set(force))
        seen["brands"] = [b["key"] for b in K.brands()]
        seen["rows"] = sheet.rows("@craftlayer")
        scheduler.log(video="CR-901-EN", platform="instagram", status="published", permalink="https://ig/x")
    monkeypatch.setattr(scheduler, "run", run)
    code = P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock")
    assert code == 0
    assert seen["args"] == (True, {"CR-901-EN"})
    assert seen["brands"] == ["craftlayer"]
    assert [r["Video ID"] for r in seen["rows"]] == ["CR-901-EN"]
    assert seen["rows"][0]["YouTube Status"] == P.HIDDEN and seen["rows"][0]["Instagram Status"] == "Ready"
    assert fake.writes == []                              # narrowing never writes the Sheet


def test_publish_job_reports_failure_and_lock(fake, isolated, monkeypatch):
    monkeypatch.setattr(K, "brands", K.brands)
    monkeypatch.setattr(sheet, "rows", sheet.rows)
    calls = []
    monkeypatch.setattr(scheduler, "run", lambda publish, force=(): calls.append(1) or scheduler.log(
        video="CR-901-EN", platform="instagram", status="failed", error="x"))
    assert P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 1
    with open(isolated / "lock", "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 3
    assert len(calls) == 1


def test_edit_route_and_conflict_status(client, fake):
    r = client.patch("/api/reels/CR-901-EN", json={"fields": {"Scheduled Time (IST)": "2026-12-09 19:30"}})
    assert r.status_code == 200 and fake.tabs["@craftlayer"][0]["Date"] == "2026-12-09"
    fake.tabs["@craftlayer"][0]["Instagram Hashtags"] = "#changed"
    r = client.patch("/api/reels/CR-901-EN", json={"fields": {"Instagram Hashtags": "#mine"}, "base": {"Instagram Hashtags": ""}})
    assert r.status_code == 409 and r.json()["status"] == "conflict"
    assert S.connect().execute("SELECT COUNT(*) c FROM audit WHERE action='edit'").fetchone()["c"] == 1
