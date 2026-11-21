import asyncio, sys

import pytest

from studio import jobs as J


def run(coro):
    return asyncio.run(coro)


async def wait(q, jid, timeout=20):
    for _ in range(int(timeout / 0.05)):
        j = q.get(jid)
        if j["status"] in J.FINAL:
            return j
        await asyncio.sleep(0.05)
    raise AssertionError("job did not finish")


def test_queue_runs_logs_and_reports_exit_codes():
    async def main():
        done = []
        q = J.JobQueue(workers=2, on_done=done.append)
        await q.start()
        ok = q.submit("t", argv=[sys.executable, "-c", "print('hello from job')"], title="ok")
        bad = q.submit("t", argv=[sys.executable, "-c", "import sys; sys.exit(4)"], title="bad")
        a, b = await wait(q, ok), await wait(q, bad)
        assert a["status"] == "done" and a["exit_code"] == 0
        assert b["status"] == "failed" and b["exit_code"] == 4
        assert "hello from job" in J.read_log(ok)[0]
        assert {j["id"] for j in done} == {ok, bad}
        await q.stop()
    run(main())


def test_cancel_running_and_queued():
    async def main():
        q = J.JobQueue(workers=1)
        await q.start()
        slow = q.submit("t", argv=[sys.executable, "-c", "import time; print('start', flush=True); time.sleep(30)"], title="slow")
        queued = q.submit("t", argv=[sys.executable, "-c", "print(1)"], title="queued")
        for _ in range(100):
            if q.get(slow)["status"] == "running":
                break
            await asyncio.sleep(0.05)
        assert q.cancel(queued) and q.get(queued)["status"] == "cancelled"
        assert q.cancel(slow)
        j = await wait(q, slow)
        assert j["status"] == "cancelled"
        assert q.active() == []
        await q.stop()
    run(main())


def test_restart_marks_running_jobs_interrupted():
    async def main():
        q = J.JobQueue(workers=1)
        await q.start()
        await q.stop()
        jid = q.submit("t", argv=[sys.executable, "-c", "pass"], title="x")
        q2 = J.JobQueue(workers=1)
        await q2.start()
        assert q2.get(jid)["status"] == "interrupted"
        await q2.stop()
    run(main())


def test_build_validates_parameters():
    argv, title, target = J.build("render", {"spec": "specs/craftlayer/CR-110.json", "lang": "en", "mode": "stills", "stills": "0.3,7"})
    assert argv[-4:] == ["--lang", "en", "--stills", "0.3,7"]
    argv, _, _ = J.build("publish", {"id": "CR-110-EN", "platform": "instagram"})
    assert argv[1:4] == ["-m", "studio.publish_job", "CR-110-EN"]
    for kind, p in [("render", {"spec": "../../etc/passwd"}), ("render", {"spec": "specs/craftlayer/CR-110.json", "mode": "x"}),
                    ("render", {"spec": "specs/craftlayer/CR-110.json", "mode": "stills", "stills": "1;rm"}),
                    ("publish", {"id": "CR-110-EN; rm", "platform": "instagram"}), ("generate", {"files": ["/etc/passwd"]}),
                    ("insights", {"brand": "nope"}), ("whatever", {})]:
        with pytest.raises(J.JobError):
            J.build(kind, p)
