from conftest import row
from studio import store as S, sync as Y


def test_pull_upserts_by_id_and_counts_changes(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN"), row("CR-902-EN")]
    fake.tabs["@StackShade"] = [row("SS-901", **{"YouTube Status": "Ready"})]
    s = Y.pull()
    assert s["@craftlayer"] == {"rows": 2, "changed": 2, "missing": 0}
    r = S.get_reel("CR-901-EN")
    assert r["brand"] == "craftlayer" and r["tab"] == "@craftlayer" and r["sheet_row"] == 2 and r["sheet_hash"]
    assert S.get_reel("SS-901")["YouTube Status"] == "Ready"
    assert Y.pull()["@craftlayer"]["changed"] == 0
    fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] = "new"
    assert Y.pull()["@craftlayer"]["changed"] == 1
    assert S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "new"


def test_row_gone_from_sheet_is_flagged_not_deleted(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN"), row("CR-902-EN")]
    Y.pull()
    fake.tabs["@craftlayer"] = [row("CR-902-EN")]
    s = Y.pull()
    assert s["@craftlayer"]["missing"] == 1
    r = S.get_reel("CR-901-EN")
    assert r is not None and r["missing"] is True
    assert S.connect().execute("SELECT COUNT(*) c FROM audit WHERE action='missing in sheet'").fetchone()["c"] == 1
    fake.tabs["@craftlayer"].append(row("CR-901-EN"))
    Y.pull()
    assert S.get_reel("CR-901-EN")["missing"] is False


def test_failed_tab_read_does_not_flag_rows_missing(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    Y.pull()
    fake.fail_read = True
    s = Y.pull()
    assert "error" in s["@craftlayer"]
    assert S.get_reel("CR-901-EN")["missing"] is False


def test_edit_writes_sheet_then_store_and_audits(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    Y.pull()
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "better caption"})
    assert res["status"] == "ok"
    assert fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] == "better caption"
    assert S.get_reel("CR-901-EN")["Instagram Viral Caption"] == "better caption"
    a = S.connect().execute("SELECT * FROM audit WHERE action='edit'").fetchone()
    assert a["target"] == "CR-901-EN" and "caption" in a["before"] and "better caption" in a["after"]


def test_conflict_when_sheet_changed_since_load(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    Y.pull()
    fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] = "edited in the sheet"
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "mine"}, base={"Instagram Viral Caption": "caption"})
    assert res["status"] == "conflict"
    c = res["conflicts"]["Instagram Viral Caption"]
    assert c == {"loaded": "caption", "sheet": "edited in the sheet", "yours": "mine"}
    assert fake.writes == []
    # a different cell changed in the sheet: not a conflict for this edit
    res = Y.edit("CR-901-EN", {"Category / Topic": "t2"}, base={"Category / Topic": "topic CR-901-EN"})
    assert res["status"] == "ok"
    # the owner keeps theirs
    res = Y.edit("CR-901-EN", {"Instagram Viral Caption": "mine"}, base={"Instagram Viral Caption": "caption"}, force=True)
    assert res["status"] == "ok" and fake.tabs["@craftlayer"][0]["Instagram Viral Caption"] == "mine"


def test_failed_write_is_queued_and_retried_by_next_pull(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    Y.pull()
    fake.fail_write = True
    res = Y.edit("CR-901-EN", {"Scheduled Time (IST)": "2026-12-05 19:30"})
    assert res["status"] == "pending"
    r = S.get_reel("CR-901-EN")
    assert r["pending"]["Scheduled Time (IST)"]["value"] == "2026-12-05 19:30"
    assert r["Scheduled Time (IST)"] == "2026-12-05 19:30"           # shown locally as pending
    assert fake.tabs["@craftlayer"][0]["Scheduled Time (IST)"] == "2026-12-01 19:30"
    Y.pull()                                                          # still failing: stays pending
    assert S.get_reel("CR-901-EN")["pending"]
    fake.fail_write = False
    Y.pull()
    assert fake.tabs["@craftlayer"][0]["Scheduled Time (IST)"] == "2026-12-05 19:30"
    assert S.get_reel("CR-901-EN")["pending"] == {}


def test_pending_edit_conflicts_if_sheet_moved(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN")]
    Y.pull()
    fake.fail_read = True
    assert Y.edit("CR-901-EN", {"Instagram Hashtags": "#a"})["status"] == "pending"
    fake.fail_read = False
    fake.tabs["@craftlayer"][0]["Instagram Hashtags"] = "#sheet"
    Y.pull()
    p = S.get_reel("CR-901-EN")["pending"]["Instagram Hashtags"]
    assert p["conflict"] == "#sheet" and fake.tabs["@craftlayer"][0]["Instagram Hashtags"] == "#sheet"
    Y.drop_pending("CR-901-EN", "Instagram Hashtags")
    assert S.get_reel("CR-901-EN")["pending"] == {}


def test_edit_guards(fake):
    fake.tabs["@craftlayer"] = [row("CR-901-EN", **{"Instagram Status": "Published"}), row("CR-902-EN", **{"Instagram Status": "Publishing"})]
    Y.pull()
    import pytest
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
    Y.pull()
    snap = Y.snapshot(base=isolated / "backup")
    assert any(f.endswith("craftlayer.csv") for f in snap["files"])
    day = Y.list_snapshots(isolated / "backup")[0]
    fake.tabs["@craftlayer"][0].update({"Instagram Viral Caption": "broken", "Instagram Status": "Published", "Instagram Post URL": "https://x"})
    Y.pull()
    dry = Y.restore_row("CR-901-EN", day, dry_run=True, base=isolated / "backup")
    assert dry["diff"] == {"Instagram Viral Caption": "caption"}
    assert fake.writes == []
    Y.restore_row("CR-901-EN", day, dry_run=False, base=isolated / "backup")
    r = fake.tabs["@craftlayer"][0]
    assert r["Instagram Viral Caption"] == "caption" and r["Instagram Status"] == "Published"


def test_import_publish_log_is_idempotent(fake):
    import json
    Y.LOG.write_text(json.dumps({"video": "CR-901-EN", "platform": "instagram", "status": "published", "at": "2026-11-20T19:30:00+05:30"}) + "\n")
    assert Y.import_publish_log() == 1
    assert Y.import_publish_log() == 0
