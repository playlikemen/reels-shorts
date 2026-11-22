"""Publish reels now, as the owner asked: a direct call, not a scheduler run.

  python3.11 -m studio.publish_job CR-110-EN [CR-111-EN ...] --platform instagram [--dry-run] [--mirror]
  python3.11 -m studio.publish_job --reconcile [--id CR-110-EN]     # settle rows stuck at "Publishing"

- Takes the scheduler's lock (~/.local/state/reels-shorts/scheduler.lock), so this and cron never post together. If
  cron holds it, waits up to 60 s, then gives up with a clear message (nothing posted).
- Per reel: the row is set to Publishing (store first, then the Sheet mirror), the channel's posting backend
  (ops/publish_backends.py) is called directly, then Published + URL or "Failed: reason" is written, the publish log
  gets a line and the row is mirrored. Schedule time, slots, the daily cap and the auto-publish switch are not used
  and not changed: a manual Publish ignores them.
- Hold, Failed, Manual upload needed and drafts can be posted; Published, Publishing, Archived and "No channel" never.
- Progress: one line per step ("uploading video to Composio…", "Instagram container <id> created, processing…",
  "publishing…", "published <permalink>"); the studio shows the latest line on the card's spinner.
- Cancel safety: from the moment the upload starts until the result is written, SIGTERM (Cancel) is ignored, so a
  post that Instagram accepted is never lost. The container id is written to the publish log as soon as it exists.
  If the job still dies, the reconciler (cron tick, studio start, "Check Instagram") finds the post by caption.
"""
import argparse, datetime, fcntl, json, re, signal, sys, time

from . import store as S  # noqa: F401  (sets up sys.path for ops/)
from . import sync as Y
import config as K
import scheduler
import publish_backends as PB

NEVER = ("Published", "Publishing", "Archived", "No channel")
LOCK_WAIT = 60
STALE_MIN = 10
COL = {"instagram": "Instagram Status", "youtube": "YouTube Status"}
URL = {"instagram": "Instagram Post URL", "youtube": "YouTube Shorts URL"}


def pushable(status):
    """Can an owner's Publish now post a row with this status? Ready, Hold, Failed, Manual and drafts: yes."""
    s = (status or "").strip()
    return bool(s) and not s.startswith(NEVER)


def say(line):
    print(line, flush=True)


def wait_lock(path, timeout=LOCK_WAIT, sleep=time.sleep):
    f = open(path, "w")
    waited = 0.0
    while True:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except BlockingIOError:
            if waited == 0:
                say("the scheduler (cron) is running; waiting for it to finish…")
            if waited >= timeout:
                f.close()
                return None
            sleep(1)
            waited += 1


class NoCancel:
    """Ignore SIGTERM (the studio's Cancel) while a post is in flight."""

    def __enter__(self):
        try:
            self.old = signal.signal(signal.SIGTERM, self._note)
        except ValueError:          # not the main thread (tests)
            self.old = None
        return self

    cancelled = False

    @classmethod
    def _note(cls, *_):
        cls.cancelled = True
        say("cancel noted: the post is already on its way to the platform; waiting for its result, then stopping")

    def __exit__(self, *exc):
        if self.old is not None:
            signal.signal(signal.SIGTERM, self.old)


def _mark(r, fields):
    Y.set_cells(r["tab"], r["Video ID"], fields, who="publish-now")


def one(vid, platform, dry_run=False):
    """Post one reel. 0 posted, 1 failed, 2 nothing posted."""
    r = S.get_reel(vid)
    if not r:
        say(f"{vid}: no such reel"); return 2
    b = K.brand(r["brand"])
    acc = b.get(platform)
    col = COL[platform]
    if not acc:
        say(f"{vid}: {b['name']} has no {platform} channel"); return 2
    if not pushable(r[col]):
        say(f"{vid}: {col} is '{r[col] or 'empty'}'; Published, Publishing, Archived and channel-less rows are never posted"); return 2
    mp4 = K.ROOT / r["Local Path"] if r["Local Path"] else None
    if not mp4 or not mp4.exists() or mp4.stat().st_size < K.MIN_MP4_BYTES:
        say(f"{vid}: the local MP4 is missing or under 100 KB"); return 2
    canary = scheduler.canary_state() if platform == "youtube" else {}
    if platform == "youtube" and canary.get("state") in ("pending", "blocked"):
        say(f"{vid}: YouTube canary is {canary['state']}; not uploading"); return 2
    backend = PB.for_brand(b["key"])
    say(f"{'[dry-run] ' if dry_run else ''}{vid} -> {platform} {acc['handle']} (direct, via {backend.name})"
        + ("" if r[col] == "Ready" else f"; status was '{r[col]}'"))
    if dry_run:
        say(f"[dry-run] would post {mp4.name} now; nothing was sent"); return 0

    with NoCancel():
        _mark(r, {col: "Publishing"})
        S.set_setting(f"publishing:{vid}:{platform}", {"at": S.now(), "backend": backend.name})
        try:
            if platform == "instagram":
                caption = r["Instagram Viral Caption"].rstrip() + "\n\n" + r["Instagram Hashtags"]
                res = backend.instagram(b["key"], mp4, caption, progress=say,
                                        on_container=lambda cid: scheduler.log(video=vid, platform=platform, status="container",
                                                                               creation_id=cid, via="publish-now"))
                url = res.get("permalink") or ""
            else:
                tags = [t.strip() for t in r["YouTube SEO Tags (Separated)"].split(",") if t.strip()]
                res = backend.youtube(b["key"], mp4, r["YouTube Title"], r["YouTube Best SEO Description"], tags, progress=say)
                url = res.get("url") or ""
        except Exception as e:
            _mark(r, {col: f"Failed: {str(e)[:120]}"})
            scheduler.log(video=vid, platform=platform, status="failed", error=str(e)[:400], via="publish-now")
            say(f"FAILED {vid}: {str(e)[:300]}")
            return 1
        finally:
            S.set_setting(f"publishing:{vid}:{platform}", None)
        _mark(r, {col: "Published", URL[platform]: url})
        scheduler.log(video=vid, platform=platform, status="published", via="publish-now",
                      **{k: v for k, v in res.items() if k in ("media_id", "permalink", "creation_id", "video_id", "url")})
    if platform == "youtube" and canary.get("state") == "none":
        json.dump({"state": "pending", "video": vid, "brand": b["key"], "video_id": res.get("video_id"),
                   "at": scheduler.now().isoformat()}, open(scheduler.CANARY, "w"))
    scheduler.file_published(r.get("Google Drive Folder", ""))
    say(f"POSTED {vid} {url}")
    return 0


# ---------- reconcile rows stuck at "Publishing" ----------

def norm(caption):
    return re.sub(r"\s+", " ", (caption or "").replace("%23", "#")).strip()[:60]


def _since(r, platform):
    mark = S.get_setting(f"publishing:{r['Video ID']}:{platform}") or {}
    t = mark.get("at") or r.get("updated_at") or ""
    try:
        return datetime.datetime.fromisoformat(t)
    except ValueError:
        return None


def _job_running(vid):
    q = "SELECT id FROM jobs WHERE status IN ('queued','running') AND kind='publish' AND (target=? OR ','||target||',' LIKE ?)"
    return bool(S.connect().execute(q, (vid, f"%,{vid},%")).fetchall())


def reconcile(only=None, force=False, now=None, lock_path=None):
    """Settle Instagram rows stuck at Publishing (over 10 minutes, or any age with force) with no running job:
    the newest media of the channel are matched by caption. Returns {vid: result}."""
    out = {}
    lock = open(lock_path or (K.STATE / "scheduler.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return {"_": "the scheduler is running; try again in a minute"}
    try:
        now = now or datetime.datetime.now(S.TZ)
        rows = [r for r in S.list_reels() if r["Instagram Status"] == "Publishing" and (not only or r["Video ID"] == only)]
        media_cache = {}
        for r in rows:
            vid = r["Video ID"]
            since = _since(r, "instagram")
            if _job_running(vid):
                out[vid] = "a publish job is still running"; continue
            if not force and since and (now - since).total_seconds() < STALE_MIN * 60:
                out[vid] = "publishing for under 10 minutes; left alone"; continue
            if r["brand"] not in media_cache:
                try:
                    media_cache[r["brand"]] = PB.for_brand(r["brand"]).recent_instagram(r["brand"], 10)
                except Exception as e:
                    out[vid] = f"could not read Instagram: {str(e)[:200]}"; continue
            want = norm(r["Instagram Viral Caption"].rstrip() + "\n\n" + r["Instagram Hashtags"])   # as it was posted
            hit = next((m for m in media_cache[r["brand"]] if want and norm(m.get("caption")) == want), None)
            if hit:
                Y.set_cells(r["tab"], vid, {"Instagram Status": "Published", "Instagram Post URL": hit.get("permalink", "")}, who="reconcile")
                scheduler.log(video=vid, platform="instagram", status="published", media_id=hit.get("id"),
                              permalink=hit.get("permalink", ""), via="reconcile")
                scheduler.file_published(r.get("Google Drive Folder", ""))
                out[vid] = f"published {hit.get('permalink', '')}"
            else:
                Y.set_cells(r["tab"], vid, {"Instagram Status": "Failed: interrupted, not found on Instagram"}, who="reconcile")
                scheduler.log(video=vid, platform="instagram", status="failed", error="interrupted, not found on Instagram", via="reconcile")
                out[vid] = "not found on Instagram: marked Failed"
            S.set_setting(f"publishing:{vid}:instagram", None)
    finally:
        lock.close()
    return out


def main(argv=None, lock_path=None, sleep=time.sleep):
    ap = argparse.ArgumentParser(prog="studio.publish_job")
    ap.add_argument("video_id", nargs="*"); ap.add_argument("--platform", choices=["instagram", "youtube"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mirror", "--pull", dest="mirror", action="store_true", help="push the Sheet mirror afterwards")
    ap.add_argument("--reconcile", action="store_true"); ap.add_argument("--id", default="")
    a = ap.parse_args(argv)
    if a.reconcile:
        res = reconcile(a.id or None, force=bool(a.id), lock_path=lock_path)
        for k, v in res.items():
            say(f"{k}: {v}")
        return 0
    if not a.video_id or not a.platform:
        ap.error("video ids and --platform are needed")
    lock = wait_lock(lock_path or (K.STATE / "scheduler.lock"), sleep=sleep)
    if not lock:
        say(f"the scheduler has been running for over {LOCK_WAIT} s; nothing was posted. Try again in a minute.")
        return 3
    codes = []
    try:
        for vid in a.video_id:
            if NoCancel.cancelled:
                say(f"{vid}: skipped (cancelled)"); codes.append(2); continue
            codes.append(one(vid, a.platform, a.dry_run))
            if len(a.video_id) > 1:
                say(f"{vid}: {['posted', 'FAILED', 'not posted'][codes[-1]]}")
    finally:
        lock.close()
    if a.mirror and not a.dry_run:
        try:
            Y.push()
        except Exception as e:
            say(f"Sheet mirror after publish failed ({str(e)[:200]}); the next push retries")
    if len(codes) == 1:
        return codes[0]
    return 1 if 1 in codes else (2 if all(c == 2 for c in codes) else 0)


if __name__ == "__main__":
    sys.exit(main())
