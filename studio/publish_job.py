"""Publish one reel now, through ops/scheduler.run, the same code path as cron.

  python3.11 -m studio.publish_job CR-110-EN --platform instagram [--dry-run]

- Takes the scheduler's own lock (~/.local/state/reels-shorts/scheduler.lock), so this and cron can never run together.
- Calls scheduler.run(publish=True, force={id}): the row is set to "Publishing" before the API call and to
  "Published"/"Failed: ..." after it, and the publish log is written, exactly as for a cron post.
- Only this reel and this platform are touched: the brand list and the sheet rows the scheduler sees are narrowed to the
  one row, and the other platform's status is hidden from it in memory (the Sheet is not changed for that).
"""
import argparse, fcntl, json, sys

from . import store as S  # noqa: F401  (sets up sys.path for ops/)
import config as K
import scheduler
import sheet

HIDDEN = "(not this run)"


def narrow(vid, platform):
    """Patch config.brands and sheet.rows so scheduler.run only sees this one row and platform."""
    real_brands, real_rows = K.brands, sheet.rows
    prefix = vid.split("-")[0]
    target = [b for b in real_brands() if b["id_prefix"] == prefix]
    if not target:
        raise SystemExit(f"no brand has the id prefix {prefix}")

    def rows(tab):
        out = []
        for r in real_rows(tab):
            if r["Video ID"].strip() != vid:
                continue
            r = dict(r)
            other = "YouTube Status" if platform == "instagram" else "Instagram Status"
            r[other] = HIDDEN
            out.append(r)
        return out

    K.brands = lambda: target
    sheet.rows = rows
    return target[0]


def main(argv=None, lock_path=None):
    ap = argparse.ArgumentParser(prog="studio.publish_job")
    ap.add_argument("video_id"); ap.add_argument("--platform", choices=["instagram", "youtube"], required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    lock = open(lock_path or (K.STATE / "scheduler.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("the scheduler is running right now (cron); nothing was posted. Try again in a minute.")
        return 3
    b = narrow(a.video_id, a.platform)
    print(f"{'[dry-run] ' if a.dry_run else ''}{a.video_id} -> {a.platform} {b[a.platform]['handle'] if b.get(a.platform) else '(no channel)'}")
    log = scheduler.LOG
    start = log.stat().st_size if log.exists() else 0
    scheduler.run(publish=not a.dry_run, force={a.video_id})
    if a.dry_run:
        return 0
    entries = []
    if log.exists():
        with open(log) as f:
            f.seek(start)
            entries = [json.loads(x) for x in f if x.strip()]
    mine = [e for e in entries if e.get("video") == a.video_id and e.get("platform") == a.platform]
    if not mine:
        print(f"nothing was posted: {a.video_id} is not 'Ready' for {a.platform}, or the channel is waiting (see above)")
        return 2
    return 1 if any(e.get("status") == "failed" for e in mine) else 0


if __name__ == "__main__":
    sys.exit(main())
