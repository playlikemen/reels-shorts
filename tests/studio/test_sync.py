"""The store is the source of truth; the Sheet is a one-way mirror (pushed, retried, never read back on its own)."""
import json

import pytest

from conftest import row, seed
from studio import store as S, sync as Y


def test_import_loads_sheet_once_and_reports_diff(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN"), row("CR-902-EN")]
    fake.tabs["@StackShade"] = [row("SS-901", **{"YouTube Status": "Ready"})]
    assert seed() == {"cells": 0, "rows": 3}
    r = S.get_reel("CR-901-EN")
    assert r["brand"] == "craftlayer" and r["tab"] == "@craftlayer" and r["sheet_row"] == 2 and r["pending"] == {}
    d = Y.import_diff(["@craftlayer"])["@craftlayer"]
    assert d["changed"] == {} and d["new"] == [] and d["sheet_rows"] == d["studio_rows"] == 2


def test_sheet_edits_never_overwrite_the_store_unless_ticked(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] = "edited in the sheet"
    fake.tabs["@craftlayer"].append(row("CR-903-EN"))
    assert Y.push() == {}                                            # nothing to mirror, nothing read back
    assert S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "caption" and S.get_reel("CR-903-EN") is None
    d = Y.import_diff(["@craftlayer"])["@craftlayer"]
    assert d["changed"]["CR-901-EN"]["Instagram Viral Caption"] == {"studio": "caption", "sheet": "edited in the sheet"}
    assert [x["Video ID"] for x in d["new"]] == ["CR-903-EN"]
    Y.import_apply({"CR-901-EN": ["Instagram Viral Caption"]}, [], ["@craftlayer"])
    assert S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "edited in the sheet" and S.get_reel("CR-903-EN") is None


def test_edit_writes_store_then_mirror_and_audits(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "better caption"})
    assert res["status"] == "ok"
    assert S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "better caption"
    assert fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] == "better caption"
    assert S.get_reel("CR-901-EN")["pending"] == {}
    a = S.connect().execute("SELECT * FROM audit WHERE action='edit'").fetchone()
    assert a["target"] == "CR-901-EN" and "caption" in a["before"] and "better caption" in a["after"]


def test_sheet_failure_never_blocks_an_edit_and_push_retries(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    fake.fail_write = True
    res = Y.edit("CR-901-EN", {"Scheduled Time (IST)": "2026-12-05 19:30"})
    assert res["status"] == "ok"
    r = S.get_reel("CR-901-EN")
    assert r["Scheduled Time (IST)"] == "2026-12-05 19:30" and "Scheduled Time (IST)" in r["pending"]
    assert "error" in r["pending"]["Scheduled Time (IST)"]
    assert fake.tabs["@craftlayer"][0]["Scheduled Time (IST)"] == "2026-12-01 19:30"
    fake.fail_read = True
    assert "error" in Y.push()["@craftlayer"]                         # still down: stays queued
    fake.fail_write = fake.fail_read = False
    assert Y.push()["@craftlayer"] == {"mirrored": 1, "failed": 0}
    assert fake.tabs["@craftlayer"][0]["Scheduled Time (IST)"] == "2026-12-05 19:30"
    assert S.get_reel("CR-901-EN")["pending"] == {}


def test_new_rows_are_appended_to_the_mirror(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    Y.upsert_local("@craftlayer", row("CR-950-EN", **{"Instagram Status": "Hold"}))
    assert [r["Video ID"] for r in fake.tabs["@craftlayer"]] == ["CR-901-EN", "CR-950-EN"]
    assert S.get_reel("CR-950-EN")["sheet_row"] == 3 and S.get_reel("CR-950-EN")["pending"] == {}


def test_conflict_when_store_changed_since_load(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    Y.edit("CR-901-EN", {"Instagram Viral Caption": "someone else"})
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "mine"}, base={"Instagram Viral Caption": "caption"})
    assert res["status"] == "conflict" and res["conflicts"]["Instagram Viral Caption"]["current"] == "someone else"
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "mine"}, base={"Instagram Viral Caption": "caption"}, force=True)
    assert res["status"] == "ok" and S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "mine"


def test_drop_pending_stops_mirroring_a_cell(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    fake.fail_write = True
    Y.edit("CR-901-EN", {"Instagram Hashtags": "#a"})
    Y.drop_pending("CR-901-EN", "Instagram Hashtags")
    assert S.get_reel("CR-901-EN")["pending"] == {} and S.get_reel("CR-901-EN")["Instagram Hashtags"] == "#a"


def test_edit_guards(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Published"}), row("CR-902-EN", **{"Instagram Status": "Publishing"})]
    seed()
    with pytest.raises(Y.SyncError) as e:
        Y.edit("CR-901-EN", {"Instagram Status": "Ready"})
    assert e.value.status == 409
    assert Y.edit("CR-901-EN", {"Instagram Status": "Ready"}, allow_repost=True)["status"] == "ok"
    with pytest.raises(Y.SyncError):
        Y.edit("CR-902-EN", {"Category / Topic": "x"})
    with pytest.raises(Y.SyncError):
        Y.edit("CR-901-EN", {"Video ID": "X"})
    with pytest.raises(Y.SyncError):
        Y.edit("CR-901-EN", {"Scheduled Time (IST)": "tomorrow"})


def test_snapshot_and_restore_never_rolls_back_status(fake, isolated):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    seed()
    snap = Y.snapshot(base=isolated / "backup")
    assert any(f.endswith("craftlayer.csv") for f in snap["files"])
    day = Y.list_snapshots(isolated / "backup")[0]
    Y.edit("CR-901-EN", {"Instagram Viral Caption": "broken", "Instagram Status": "Published", "Instagram Post URL": "https://x"})
    dry = Y.restore_row("CR-901-EN", day, dry_run=True, base=isolated / "backup")
    assert dry["diff"] == {"Instagram Viral Caption": "caption"}
    Y.restore_row("CR-901-EN", day, dry_run=False, base=isolated / "backup")
    r = S.get_reel("CR-901-EN")
    assert r["Instagram Viral Caption"] == "caption" and r["Instagram Status"] == "Published"
    assert fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] == "caption"


def test_scheduler_reads_the_store_not_the_sheet(fake, monkeypatch, isolated, capsys):
    import publish_instagram, scheduler
    mp4 = isolated / "v.mp4"
    mp4.write_bytes(b"\0" * 10)
    fake.tabs["@campusloop"] = [row("CL-901", **{"Scheduled Time (IST)": "2020-01-01 19:30", "Local Path": str(mp4)})]
    seed()
    fake.tabs["@campusloop"][0]["Instagram Status"] = "Hold"            # a Sheet edit does not stop the post
    posted = []
    monkeypatch.setattr(publish_instagram, "publish", lambda key, p, cap, **k: posted.append(key) or {"permalink": "https://ig/x", "media_id": "1"})
    scheduler.run(publish=True, force={"CL-901"})
    assert posted == ["campusloop"]
    r = S.get_reel("CL-901")
    assert r["Instagram Status"] == "Published" and r["Instagram Post URL"] == "https://ig/x"
    assert fake.tabs["@campusloop"][0]["Instagram Status"] == "Published"   # mirrored afterwards
    acts = [a["action"] for a in S.connect().execute("SELECT action FROM audit WHERE target='CL-901'")]
    assert acts.count("status") == 2                                  # Publishing, then Published


def test_scheduler_marks_store_even_when_the_sheet_is_down(fake, monkeypatch, isolated):
    import publish_instagram, scheduler
    mp4 = isolated / "v.mp4"
    mp4.write_bytes(b"\0" * 10)
    fake.tabs["@campusloop"] = [row("CL-901", **{"Scheduled Time (IST)": "2020-01-01 19:30", "Local Path": str(mp4)})]
    seed()
    fake.fail_write = fake.fail_read = True
    monkeypatch.setattr(publish_instagram, "publish", lambda key, p, cap, **k: {"permalink": "https://ig/x", "media_id": "1"})
    scheduler.run(publish=True, force={"CL-901"})
    r = S.get_reel("CL-901")
    assert r["Instagram Status"] == "Published" and r["pending"]


def test_import_publish_log_is_idempotent(fake):
    Y.LOG.write_text(json.dumps({"video": "CR-901-EN", "platform": "instagram", "status": "published", "at": "2026-11-20T19:30:00+05:30"}) + "\n")
    assert Y.import_publish_log() == 1
    assert Y.import_publish_log() == 0
