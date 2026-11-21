"""Library revamp: folders, archive, next free slot, swap, channel settings, auto-publish switch, one-click publish,
upload. No network: Composio, Drive and the Sheet are fakes."""
import json, shutil, subprocess

import pytest
from starlette.testclient import TestClient

import config as K
import drive
import publish_instagram
import scheduler
import sheet
from conftest import row
from studio import app as W, auth as A, publish_job as P, store as S, sync as Y, upload as U


@pytest.fixture
def moves(monkeypatch):
    calls = []
    monkeypatch.setattr(drive, "move", lambda folder, sub: calls.append((folder, sub)) or "dest")
    return calls


FOLDER = "https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOp"


def test_folders_follow_status_and_time():
    now = "2026-12-01 12:00"
    f = lambda **kw: Y.folder_of({"Instagram Status": "Ready", "YouTube Status": "No channel", "Scheduled Time (IST)": "2026-12-02 19:30", **kw}, now)
    assert f() == "queue"
    assert f(**{"Scheduled Time (IST)": "2026-11-30 19:30"}) == "due"
    assert f(**{"Instagram Status": "Failed: token"}) == "due"
    assert f(**{"Instagram Status": "Hold (voice)"}) == "drafts"
    assert f(**{"Instagram Status": "Published"}) == "published"
    assert f(**{"Instagram Status": "Archived", "YouTube Status": "Archived"}) == "archive"


def test_archive_and_unarchive_restore_status_and_move_drive(fake, moves):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Scheduled Time (IST)": "2099-01-01 19:30", "Google Drive Folder": FOLDER}),
                                row("CR-902-EN", **{"Instagram Status": "Published", "Instagram Post URL": "https://ig/p",
                                                    "Google Drive Folder": FOLDER})]
    Y.pull()
    res = Y.archive("CR-901-EN")
    assert res["status"] == "ok"
    assert fake.tabs["@craftlayer"][0]["Instagram Status"] == "Archived" == fake.tabs["@craftlayer"][0]["YouTube Status"]
    r = S.get_reel("CR-901-EN")
    assert r["prev_status"] == {"Instagram Status": "Ready", "YouTube Status": "No channel"}
    assert moves == [(FOLDER, "Archive")]
    with pytest.raises(Y.SyncError):
        Y.archive("CR-901-EN")
    Y.pull()                                                     # a pull keeps the remembered status
    assert S.get_reel("CR-901-EN")["prev_status"]["Instagram Status"] == "Ready"
    res = Y.unarchive("CR-901-EN")
    assert res["status"] == "ok" and fake.tabs["@craftlayer"][0]["Instagram Status"] == "Ready"
    assert fake.tabs["@craftlayer"][0]["YouTube Status"] == "No channel"
    assert moves[-1] == (FOLDER, "")
    # a published reel comes back Published and its folder goes to Published/; no row is ever deleted
    Y.archive("CR-902-EN")
    Y.unarchive("CR-902-EN")
    assert fake.tabs["@craftlayer"][1]["Instagram Status"] == "Published" and moves[-1] == (FOLDER, "Published")
    assert len(fake.tabs["@craftlayer"]) == 2
    acts = [a["action"] for a in S.connect().execute("SELECT action FROM audit")]
    assert acts.count("archive") == 2 and acts.count("unarchive") == 2


def test_unarchive_of_overdue_ready_comes_back_as_hold(fake, moves):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Scheduled Time (IST)": "2020-01-01 19:30"})]
    Y.pull()
    Y.archive("CR-901-EN")
    res = Y.unarchive("CR-901-EN")
    assert fake.tabs["@craftlayer"][0]["Instagram Status"] == "Hold" and "Hold" in res["note"]


def test_drive_failure_never_blocks_archive(fake, monkeypatch):
    monkeypatch.setattr(drive, "move", lambda *a: (_ for _ in ()).throw(RuntimeError("drive down")))
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Google Drive Folder": FOLDER})]
    Y.pull()
    res = Y.archive("CR-901-EN")
    assert res["status"] == "ok" and "not moved" in res["drive"]


def test_next_free_slot_uses_slots_and_cap(fake, monkeypatch):
    K.save_channel("craftlayer", {"slots": ["12:30", "19:30"], "cap": 2})
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Scheduled Time (IST)": "2099-01-01 12:30"}),
                                row("CR-902-EN", **{"Scheduled Time (IST)": "2099-01-02 19:30"}),
                                row("CR-903-EN", **{"Scheduled Time (IST)": "2099-01-02 12:30", "Instagram Status": "Hold"})]
    Y.pull()
    assert Y.next_free_slot("craftlayer", "2099-01-01 00:00") == "2099-01-01 19:30"
    assert Y.next_free_slot("craftlayer", "2099-01-01 00:00", taken_extra=("2099-01-01 19:30",)) == "2099-01-02 12:30"
    assert Y.next_free_slot("craftlayer", "2099-01-01 00:00", exclude=("CR-901-EN",)) == "2099-01-01 12:30"
    K.save_channel("craftlayer", {"cap": 1})                       # one a day: 01 is full, 02 is full
    assert Y.next_free_slot("craftlayer", "2099-01-01 00:00") == "2099-01-03 12:30"


def test_schedule_ready_or_hold_and_never_a_published_reel(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Hold"}),
                                row("CR-902-EN", **{"Instagram Status": "Published", "Instagram Post URL": "https://ig/p"}),
                                row("CR-903-EN", **{"Instagram Status": "Failed: x"})]
    Y.pull()
    assert Y.schedule("CR-901-EN", "2099-01-05 19:30", auto=True)["status"] == "ok"
    t = fake.tabs["@craftlayer"][0]
    assert (t["Instagram Status"], t["Scheduled Time (IST)"], t["Date"], t["YouTube Status"]) == ("Ready", "2099-01-05 19:30", "2099-01-05", "No channel")
    Y.schedule("CR-901-EN", "2099-01-06 12:30", auto=False)
    assert fake.tabs["@craftlayer"][0]["Instagram Status"] == "Hold"
    with pytest.raises(Y.SyncError):
        Y.schedule("CR-902-EN", "2099-01-05 19:30")
    Y.schedule("CR-903-EN", "2099-01-07 19:30", auto=False)
    assert fake.tabs["@craftlayer"][2]["Instagram Status"] == "Hold"


def test_archived_published_reel_can_not_be_rescheduled(fake, moves):
    fake.tabs["@craftlayer"] = [row("CR-902-EN", **{"Instagram Status": "Published", "Instagram Post URL": "https://ig/p"})]
    Y.pull()
    Y.archive("CR-902-EN")
    with pytest.raises(Y.SyncError):
        Y.schedule("CR-902-EN", "2099-01-05 19:30")


def test_swap_two_slots_two_audited_edits(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Scheduled Time (IST)": "2099-01-01 12:30"}),
                                row("CR-902-EN", **{"Scheduled Time (IST)": "2099-01-02 19:30"})]
    Y.pull()
    assert Y.swap("CR-901-EN", "CR-902-EN") == {"CR-901-EN": "ok", "CR-902-EN": "ok"}
    assert fake.tabs["@craftlayer"][0]["Scheduled Time (IST)"] == "2099-01-02 19:30"
    assert fake.tabs["@craftlayer"][1]["Scheduled Time (IST)"] == "2099-01-01 12:30"
    assert S.connect().execute("SELECT COUNT(*) c FROM audit WHERE action='edit'").fetchone()["c"] == 2


def test_fill_gives_consecutive_free_slots(fake):
    K.save_channel("craftlayer", {"slots": ["12:30", "19:30"], "cap": 2})
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Hold", "Scheduled Time (IST)": ""}),
                                row("CR-902-EN", **{"Instagram Status": "Hold", "Scheduled Time (IST)": ""})]
    Y.pull()
    out = Y.fill(["CR-901-EN", "CR-902-EN"])
    t1, t2 = (fake.tabs["@craftlayer"][i]["Scheduled Time (IST)"] for i in (0, 1))
    assert t1 != t2 and t1[-5:] in ("12:30", "19:30") and all(v.startswith("ok") for v in out.values())
    assert fake.tabs["@craftlayer"][0]["Instagram Status"] == "Ready"


def test_channel_settings_validate_and_overlay_brand():
    with pytest.raises(ValueError):
        K.save_channel("campusloop", {"slots": ["25:00"]})
    with pytest.raises(ValueError):
        K.save_channel("campusloop", {"auto_publish": "no"})
    with pytest.raises(ValueError):
        K.save_channel("campusloop", {"color": "red"})
    K.save_channel("campusloop", {"auto_publish": False, "slots": ["19:30", "12:30"], "cap": 2})
    b = K.brand("campusloop")
    assert b["auto_publish"] is False and b["slots_ist"] == ["12:30", "19:30"] and b["max_reels_per_day"] == 2
    assert K.brand("craftlayer")["auto_publish"] is True


def test_auto_publish_off_skips_brand_except_forced(fake, monkeypatch, capsys):
    posted = []
    monkeypatch.setattr(publish_instagram, "publish", lambda key, mp4, cap: posted.append(key) or {"permalink": "https://ig/x", "media_id": "1"})
    fake.tabs["@campusloop"] = [row("CL-901", **{"Scheduled Time (IST)": "2020-01-01 19:30"})]
    K.save_channel("campusloop", {"auto_publish": False})
    scheduler.run(publish=False)
    out = capsys.readouterr().out
    assert "auto-publish is off" in out and "would post CL-901" not in out
    scheduler.run(publish=False, force={"CL-901"})
    assert "would post CL-901" in capsys.readouterr().out
    K.save_channel("campusloop", {"auto_publish": True})
    scheduler.run(publish=False)
    assert "would post CL-901" in capsys.readouterr().out
    assert posted == []


def test_instagram_post_moves_drive_folder_best_effort(fake, monkeypatch, isolated, moves):
    mp4 = isolated / "v.mp4"
    mp4.write_bytes(b"\0" * 10)
    monkeypatch.setattr(publish_instagram, "publish", lambda key, mp4, cap: {"permalink": "https://ig/x", "media_id": "1"})
    fake.tabs["@campusloop"] = [row("CL-901", **{"Scheduled Time (IST)": "2020-01-01 19:30", "Local Path": str(mp4),
                                                 "Google Drive Folder": FOLDER})]
    scheduler.run(publish=True, force={"CL-901"})
    assert fake.tabs["@campusloop"][0]["Instagram Status"] == "Published"
    assert moves == [(FOLDER, "Published")]


def test_forced_publish_posts_a_hold_row_but_never_a_published_one(fake, monkeypatch, isolated):
    monkeypatch.setattr(K, "brands", K.brands)
    monkeypatch.setattr(sheet, "rows", sheet.rows)
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Hold"}),
                                row("CR-902-EN", **{"Instagram Status": "Published"})]
    seen = []
    monkeypatch.setattr(scheduler, "run", lambda publish, force=(): seen.append([r["Instagram Status"] for r in sheet.rows("@craftlayer")]))
    assert P.main(["CR-901-EN", "CR-902-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 2
    assert seen == [["Ready"], ["Published"]]                    # in memory only; the scheduler would skip the second
    assert fake.writes == []
    assert K.brands().__len__() == 4                              # narrowing is undone after each reel
    assert P.pushable("Hold") and P.pushable("Failed: x") and P.pushable("Ready")
    assert not any(P.pushable(s) for s in ("Published", "Publishing", "Archived", "No channel", ""))


@pytest.fixture
def client(isolated, fake, monkeypatch, moves):
    W.STATE_REF.limiter = A.RateLimit()
    monkeypatch.setattr(W, "ROOT", isolated)
    for vid in ("CR-901-EN", "CR-902-EN", "CR-903-EN", "CR-904-EN"):
        mp4 = isolated / f"out/craftlayer/{vid}/{vid.lower()}.mp4"
        mp4.parent.mkdir(parents=True)
        mp4.write_bytes(b"\0" * (K.MIN_MP4_BYTES + 10))
    fake.tabs["@craftlayer"] = [row("CR-901-EN"), row("CR-902-EN", **{"Instagram Status": "Hold"}),
                                row("CR-903-EN", **{"Instagram Status": "Published", "Instagram Post URL": "https://ig/p"}),
                                row("CR-904-EN", **{"Instagram Status": "Archived"})]
    Y.pull()
    with TestClient(W.create_app()) as c:
        pw = (isolated / "config" / "initial-password.txt").read_text().strip()
        c.headers["x-csrf-token"] = c.post("/api/login", json={"password": pw}).json()["csrf"]
        c.submitted = []
        monkeypatch.setattr(W.STATE_REF.queue, "submit", lambda kind, params=None, who="", **kw: c.submitted.append((kind, params)) or 78)
        yield c


def fill_cap():
    b = K.brand("craftlayer")
    scheduler.LOG.write_text("".join(json.dumps({"video": f"CR-8{i:02d}-EN", "platform": "instagram", "status": "published",
                                                 "at": scheduler.now().isoformat()}) + "\n" for i in range(b["max_reels_per_day"])))


def test_one_click_publish_route_accepts_override_and_hold(client):
    fill_cap()
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True})
    assert r.status_code == 409 and r.json()["need_override"]
    r = client.post("/api/publish", json={"id": "CR-901-EN", "platform": "instagram", "confirm": True, "override_cap": True})
    assert r.status_code == 202
    r = client.post("/api/publish", json={"id": "CR-902-EN", "platform": "instagram", "confirm": True, "override_cap": True})
    assert r.status_code == 202                                  # Hold: allowed, the publish job flips it
    assert [p["id"] for k, p in client.submitted] == ["CR-901-EN", "CR-902-EN"]


def test_publish_refuses_published_and_archived(client):
    for vid in ("CR-903-EN", "CR-904-EN"):
        r = client.post("/api/publish", json={"id": vid, "platform": "instagram", "confirm": True, "override_cap": True})
        assert r.status_code == 409 and "never posted" in r.json()["error"]
    r = client.post("/api/reels/bulk", json={"ids": ["CR-901-EN", "CR-903-EN"], "action": "publish", "confirm": True})
    assert r.status_code == 409 and "CR-903-EN" in r.json()["problems"]
    assert client.submitted == []


def test_bulk_publish_is_one_sequential_job_with_one_confirm(client):
    assert client.post("/api/reels/bulk", json={"ids": ["CR-901-EN", "CR-902-EN"], "action": "publish"}).status_code == 400
    r = client.post("/api/reels/bulk", json={"ids": ["CR-901-EN", "CR-902-EN"], "action": "publish", "confirm": True})
    assert r.status_code == 202
    assert client.submitted == [("publish", {"ids": ["CR-901-EN", "CR-902-EN"], "platform": "instagram", "dry_run": False})]
    from studio import jobs as J
    argv, _, target = J.build("publish", client.submitted[0][1])
    assert argv[argv.index("studio.publish_job") + 1:][:2] == ["CR-901-EN", "CR-902-EN"] and target == "CR-901-EN,CR-902-EN"


def test_archive_schedule_slot_and_channels_routes(client, fake):
    r = client.post("/api/reels/CR-901-EN/archive", json={"archive": True})
    assert r.status_code == 200 and fake.tabs["@craftlayer"][0]["Instagram Status"] == "Archived"
    reels = client.get("/api/reels").json()
    assert reels["counts"]["craftlayer"]["archive"] == 2 and reels["counts"]["craftlayer"]["published"] == 1
    r = client.post("/api/reels/CR-901-EN/archive", json={"archive": False})
    assert r.status_code == 200 and fake.tabs["@craftlayer"][0]["Instagram Status"] in ("Ready", "Hold")
    r = client.post("/api/reels/CR-902-EN/schedule", json={"when": "next", "auto": True})
    assert r.status_code == 200 and r.json()["when"][-5:] in K.brand("craftlayer")["slots_ist"]
    assert client.post("/api/reels/CR-903-EN/schedule", json={"when": "2099-01-01 19:30"}).status_code == 409
    s = client.get("/api/slots/next?brand=craftlayer&n=3").json()
    assert len(set(s["slots"])) == 3
    r = client.post("/api/channels", json={"brand": "campusloop", "auto_publish": False})
    assert r.status_code == 200 and not next(c for c in r.json()["channels"] if c["key"] == "campusloop")["auto_publish"]
    assert client.post("/api/channels", json={"brand": "campusloop", "cap": 99}).status_code == 400
    assert S.connect().execute("SELECT COUNT(*) c FROM audit WHERE action='channel settings'").fetchone()["c"] == 1


def test_upload_route_validates_and_limits_size(client, monkeypatch):
    form = {"brand": "craftlayer", "topic": "Test upload", "caption": "", "after": "draft"}
    r = client.post("/api/upload", data=form, files={"file": ("x.txt", b"x" * 2000, "text/plain")})
    assert r.status_code == 400 and "MP4" in r.json()["error"]
    r = client.post("/api/upload", data={**form, "after": "now", "caption": "c"}, files={"file": ("x.mp4", b"x" * 2000, "video/mp4")})
    assert r.status_code == 400 and "confirm" in r.json()["error"]
    r = client.post("/api/upload", data={**form, "after": "schedule"}, files={"file": ("x.mp4", b"x" * 2000, "video/mp4")})
    assert r.status_code == 400
    r = client.post("/api/upload", data=form, files={"file": ("x.mp4", b"x" * 2000, "video/mp4")})
    assert r.status_code == 202 and client.submitted[-1][0] == "upload"
    name = r.json()["file"]
    monkeypatch.setattr(W, "UPLOAD_LIMIT", 1500)
    r = client.post("/api/upload", data=form, files={"file": ("y.mp4", b"x" * 3000, "video/mp4")})
    assert r.status_code == 413
    assert name.endswith(".mp4") and len(name) == 20


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_upload_job_normalises_and_writes_a_hold_row(fake, isolated, monkeypatch):
    monkeypatch.setattr(U, "ROOT", isolated)
    monkeypatch.setattr(U, "STATE", isolated / "state")
    monkeypatch.setattr(Y, "ROOT", isolated)
    src = isolated / "state" / "uploads" / "0123456789abcdef.mp4"
    src.parent.mkdir(parents=True)
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=360x640:rate=25:duration=3", "-f", "lavfi",
                    "-i", "sine=frequency=440:duration=3", "-shortest", "-c:v", "mpeg4", "-q:v", "2", str(src)], check=True)
    rows = []
    vid, code = U.run({"file": src.name, "brand": "craftlayer", "lang": "en", "topic": "Test", "caption": "", "after": "draft"},
                      archive=lambda name, mp4: {"folder_link": FOLDER, "direct_link": "https://d/x"},
                      upsert=lambda tab, rec: rows.append((tab, rec)) or fake.upsert(tab, rec))
    assert vid == "CR-U001-EN" and code == 0
    mp4 = isolated / "out/craftlayer/CR-U001-EN/cr-u001-en.mp4"
    p = U.probe(mp4)
    assert (p["w"], p["h"], p["vcodec"], p["acodec"], p["fps"]) == (1080, 1920, "h264", "aac", "30/1")
    assert (mp4.parent / "thumb.jpg").exists() and not src.exists()
    tab, rec = rows[0]
    assert tab == "@craftlayer" and rec["Instagram Status"] == "Hold" and rec["Google Drive Folder"] == FOLDER
    assert S.get_reel("CR-U001-EN")["Instagram Status"] == "Hold"
    assert U.next_id("craftlayer", "EN") == "CR-U002-EN"
    with pytest.raises(U.UploadError):
        U.validate({"brand": "craftlayer", "topic": "x", "after": "draft"})


def test_ui_is_served_from_a_versioned_path(client):
    html = client.get("/").text
    path = html.split('src="')[1].split('"')[0]
    assert path.startswith("/static/v") and path.endswith("/app.js")
    r = client.get(path)
    assert r.status_code == 200 and "immutable" in r.headers["cache-control"]
    assert client.get(path.replace("app.js", "../../auth.py")).status_code == 404
    assert client.get("/static/style.css").headers["cache-control"] == "no-cache"


def test_backfill_moves_only_published_folders(fake, moves):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Published", "Google Drive Folder": FOLDER}),
                                row("CR-902-EN", **{"Google Drive Folder": FOLDER})]
    Y.pull()
    res = Y.backfill_published()
    assert res["moved"] == ["CR-901-EN"] and moves == [(FOLDER, "Published")]
