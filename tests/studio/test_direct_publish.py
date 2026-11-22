"""Manual Publish now is a direct call (no scheduler.run), with progress lines, cancel safety and a reconciler."""
import datetime, fcntl, json

import pytest

import config as K
import scheduler
from studio import publish_job as P, store as S


def log_lines():
    return [json.loads(x) for x in scheduler.LOG.read_text().splitlines()] if scheduler.LOG.exists() else []


def test_direct_path_never_calls_scheduler_run(direct, isolated, monkeypatch, capsys):
    monkeypatch.setattr(scheduler, "run", lambda *a, **k: pytest.fail("scheduler.run must not be used for Publish now"))
    assert P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 0
    r = S.get_reel("CR-901-EN")
    assert r["Instagram Status"] == "Published" and r["Instagram Post URL"] == "https://www.instagram.com/reel/TEST/"
    assert r["Scheduled Time (IST)"] == "2026-12-01 19:30"                    # schedule untouched
    kind, brand, mp4, caption = direct.calls[0]
    assert kind == "instagram" and brand == "craftlayer" and caption.startswith("caption")
    statuses = [e["status"] for e in log_lines() if e["video"] == "CR-901-EN"]
    assert statuses == ["container", "published"]                            # container id logged before the result
    acts = [a["after"] for a in S.connect().execute("SELECT after FROM audit WHERE target='CR-901-EN' AND action='status'")]
    assert "Publishing" in acts[0] and "Published" in acts[1]


def test_progress_lines(direct, isolated, capsys):
    P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock")
    out = capsys.readouterr().out
    steps = ["uploading video to Composio…", "Instagram container C123 created, processing…", "publishing…",
             "published https://www.instagram.com/reel/TEST/", "POSTED CR-901-EN https://www.instagram.com/reel/TEST/"]
    pos = [out.index(s) for s in steps]
    assert pos == sorted(pos)


def test_ignores_cap_and_auto_publish_posts_hold_refuses_published_and_archived(direct, isolated):
    K.save_channel("craftlayer", {"auto_publish": False, "cap": 1})
    scheduler.LOG.write_text(json.dumps({"video": "CR-800-EN", "platform": "instagram", "status": "published",
                                         "at": scheduler.now().isoformat()}) + "\n")
    assert P.main(["CR-902-EN", "CR-903-EN", "CR-904-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 0
    assert [c[0] for c in direct.calls] == ["instagram"]                   # only the Hold row
    assert S.get_reel("CR-902-EN")["Instagram Status"] == "Published"
    assert S.get_reel("CR-903-EN")["Instagram Status"] == "Published" and S.get_reel("CR-904-EN")["Instagram Status"] == "Archived"


def test_dry_run_posts_nothing(direct, isolated):
    assert P.main(["CR-901-EN", "--platform", "instagram", "--dry-run"], lock_path=isolated / "lock") == 0
    assert direct.calls == [] and S.get_reel("CR-901-EN")["Instagram Status"] == "Ready"


def test_waits_for_the_lock_then_posts(direct, isolated):
    holder = open(isolated / "lock", "w")
    fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
    waits = []

    def sleep(s):
        waits.append(s)
        if len(waits) == 3:
            holder.close()                                                  # cron finished
    assert P.main(["CR-901-EN", "--platform", "instagram"], lock_path=isolated / "lock", sleep=sleep) == 0
    assert len(waits) == 3 and S.get_reel("CR-901-EN")["Instagram Status"] == "Published"


def test_cancel_during_the_post_is_noted_and_skips_the_rest(direct, isolated, monkeypatch):
    real = direct.instagram

    def cancelled_midway(*a, **k):
        P.NoCancel._note()                                                  # SIGTERM arrives while posting
        return real(*a, **k)
    monkeypatch.setattr(direct, "instagram", cancelled_midway)
    monkeypatch.setattr(P.NoCancel, "cancelled", False)
    assert P.main(["CR-901-EN", "CR-902-EN", "--platform", "instagram"], lock_path=isolated / "lock") == 0
    assert S.get_reel("CR-901-EN")["Instagram Status"] == "Published"     # the post in flight is not lost
    assert S.get_reel("CR-902-EN")["Instagram Status"] == "Hold"          # the next one is skipped


def stuck(vid, minutes):
    at = (datetime.datetime.now(S.TZ) - datetime.timedelta(minutes=minutes)).isoformat(timespec="seconds")
    S.save_reel({"Video ID": vid, "Instagram Status": "Publishing", "Instagram Hashtags": "#craft  #layer"})
    S.set_setting(f"publishing:{vid}:instagram", {"at": at})


def test_reconciler_matches_by_caption(direct, isolated):
    stuck("CR-901-EN", 15)
    direct.media = [{"id": "9", "permalink": "https://www.instagram.com/reel/OTHER/", "caption": "something else"},
                    {"id": "8", "permalink": "https://www.instagram.com/reel/DgCC/", "caption": "caption\n\n%23craft %23layer"}]
    res = P.reconcile(lock_path=isolated / "lock")
    assert res["CR-901-EN"].startswith("published")
    r = S.get_reel("CR-901-EN")
    assert r["Instagram Status"] == "Published" and r["Instagram Post URL"] == "https://www.instagram.com/reel/DgCC/"
    assert log_lines()[-1]["via"] == "reconcile"


def test_reconciler_no_match_marks_failed_and_leaves_young_rows(direct, isolated):
    stuck("CR-901-EN", 15)
    stuck("CR-902-EN", 3)
    direct.media = [{"id": "9", "permalink": "https://x", "caption": "nope"}]
    res = P.reconcile(lock_path=isolated / "lock")
    assert S.get_reel("CR-901-EN")["Instagram Status"] == "Failed: interrupted, not found on Instagram"
    assert S.get_reel("CR-902-EN")["Instagram Status"] == "Publishing" and "under 10 minutes" in res["CR-902-EN"]
    # "Check Instagram" forces it regardless of age
    P.reconcile("CR-902-EN", force=True, lock_path=isolated / "lock")
    assert S.get_reel("CR-902-EN")["Instagram Status"].startswith("Failed: interrupted")


def test_reconciler_skips_rows_with_a_running_job(direct, isolated):
    stuck("CR-901-EN", 30)
    S.connect().execute("INSERT INTO jobs (kind, title, status, target) VALUES ('publish', 't', 'running', 'CR-901-EN')")
    assert "still running" in P.reconcile(lock_path=isolated / "lock")["CR-901-EN"]
    assert S.get_reel("CR-901-EN")["Instagram Status"] == "Publishing" and direct.calls == []


def test_metricool_backend_is_a_stub():
    import publish_backends as PB
    with pytest.raises(NotImplementedError):
        PB.BACKENDS["metricool"].instagram("craftlayer", "x.mp4", "c")
    with pytest.raises(ValueError):
        K.save_channel("craftlayer", {"publish_backend": "carrier-pigeon"})
    K.save_channel("craftlayer", {"publish_backend": "metricool"})
    assert PB.for_brand("craftlayer").name == "metricool"
