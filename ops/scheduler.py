#!/usr/bin/env python3.11
"""Publish every sheet row whose scheduled time has passed. Meant to run from cron every 15 minutes.

  python3.11 ops/scheduler.py --dry-run     # list what would be posted, post nothing
  python3.11 ops/scheduler.py --publish     # post

Rules
- Rows are read from the Reels Studio store (the source of truth, ops/reelrows.py); every status mark is written there
  first and then mirrored to the Google Sheet (best effort).
- A row is due when its status is exactly "Ready" and "Scheduled Time (IST)" (YYYY-MM-DD HH:MM) is not in the future.
- The status is set to "Publishing" before the API call and to "Published" or "Failed: ..." after it, so a crash
  can never post the same video twice. To retry a failed row, set its status back to "Ready" by hand.
- YouTube canary: YouTube has deleted Composio uploads to StackShade before. The first upload is checked again after
  30 minutes. Until that check passes no other video is uploaded. If the video is gone, every waiting row is set to
  "Manual upload needed" and YouTube uploads stop (delete the canary state file to try again).
- Auto-publish switch (Studio > Settings > Channels, stored in channels.json): a brand whose auto-publish is off is
  skipped, and one whose YouTube auto-upload is off gets no YouTube uploads; ids in --now (force) still go out.
- After an Instagram post the reel's Drive folder is moved into Published/ (best effort: a failure is only printed).
"""
import argparse, datetime, fcntl, json, os, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(__file__))
import config as K

CANARY = K.STATE / "youtube_canary.json"
LOG = K.STATE / "publish-log.jsonl"
TZ = ZoneInfo(K.TIMEZONE)


def now():
    return datetime.datetime.now(TZ)


def due(row):
    try:
        t = datetime.datetime.strptime(row["Scheduled Time (IST)"].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=TZ)
    except ValueError:
        return False
    return t <= now()


def log(**entry):
    entry["at"] = now().isoformat(timespec="seconds")
    with open(LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps(entry))


def posted_today(prefix):
    """Instagram posts already published today (IST) for video ids with this prefix, from the publish log."""
    if not LOG.exists():
        return 0
    today, n = now().date().isoformat(), 0
    for line in open(LOG):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if (e.get("platform") == "instagram" and e.get("status") == "published"
                and str(e.get("video", "")).startswith(prefix + "-") and str(e.get("at", "")).startswith(today)):
            n += 1
    return n


def canary_state():
    return json.load(open(CANARY)) if CANARY.exists() else {"state": "none"}


def file_published(folder_link):
    """Move a posted reel's Drive folder into Published/. Never raises: posting must not depend on Drive."""
    if not folder_link:
        return
    try:
        import drive
        drive.move(folder_link, "Published")
        print(f"Drive folder moved to Published/: {folder_link}")
    except Exception as e:
        print(f"Drive folder not moved to Published/ ({str(e)[:160]}); the post itself is fine")


def run(publish, force=()):
    """force: video ids to post now, ignoring their scheduled time, the daily cap and the auto-publish switch
    (an owner's explicit request)."""
    import reelrows as sheet, publish_backends as PB, publish_youtube   # rows come from the studio store; the Sheet is a mirror
    for b in K.brands():
        tab = b["sheet_tab"]
        auto = b.get("auto_publish", True)
        if not auto and not force:
            print(f"{b['name']}: auto-publish is off; skipping (Publish now in the studio still works)")
            continue
        # A backlog must never flood the feed: brands may cap Instagram posts per day.
        cap = b.get("max_reels_per_day")
        sent = posted_today(b["id_prefix"]) if cap else 0
        for row in sorted(sheet.rows(tab), key=lambda r: r["Scheduled Time (IST)"]):
            vid, n = row["Video ID"], row["_row"]
            mp4 = K.ROOT / row["Local Path"]
            if not auto and vid not in force:
                continue
            is_due = due(row) or vid in force

            if row["Instagram Status"] == "Ready" and is_due and cap and sent >= cap and vid not in force:
                print(f"{vid}: daily limit of {cap} reached for {b['name']}; it goes out on the next free day")
            elif row["Instagram Status"] == "Ready" and is_due:
                sent += 1
                if not publish:
                    print(f"[dry-run] would post {vid} to Instagram {b['instagram']['handle']}")
                elif not mp4.exists():
                    sheet.set_cells(tab, n, {"Instagram Status": "Failed: local MP4 missing"})
                    log(video=vid, platform="instagram", status="failed", error="local MP4 missing")
                else:
                    sheet.set_cells(tab, n, {"Instagram Status": "Publishing"})
                    try:
                        caption = row["Instagram Viral Caption"].rstrip() + "\n\n" + row["Instagram Hashtags"]
                        r = PB.for_brand(b["key"]).instagram(b["key"], mp4, caption, progress=print)
                        sheet.set_cells(tab, n, {"Instagram Status": "Published", "Instagram Post URL": r["permalink"]})
                        log(video=vid, platform="instagram", status="published", **r)
                        file_published(row.get("Google Drive Folder", ""))
                    except Exception as e:
                        sheet.set_cells(tab, n, {"Instagram Status": f"Failed: {str(e)[:120]}"})
                        log(video=vid, platform="instagram", status="failed", error=str(e)[:400])

            if not b.get("youtube") or row["YouTube Status"] != "Ready" or not is_due:
                continue
            if not b.get("youtube_auto", True) and vid not in force:
                print(f"{vid}: YouTube auto-upload is off for {b['name']}; not uploaded")
                continue
            c = canary_state()
            if c["state"] == "pending":
                age = (now() - datetime.datetime.fromisoformat(c["at"])).total_seconds()
                if age < 1800:
                    print(f"YouTube canary {c['video_id']} is {int(age // 60)} min old; waiting before uploading {vid}")
                    continue
                if not publish:
                    print(f"[dry-run] would check YouTube canary {c['video_id']}")
                    continue
                c["state"] = "ok" if publish_youtube.still_up(c["brand"], c["video_id"]) else "blocked"
                json.dump(c, open(CANARY, "w"))
                log(video=c["video"], platform="youtube", status=f"canary {c['state']}", video_id=c["video_id"])
            if c["state"] == "blocked":
                if publish:
                    sheet.set_cells(tab, n, {"YouTube Status": "Manual upload needed"})
                continue
            if not publish:
                print(f"[dry-run] would upload {vid} to YouTube {b['youtube']['handle']}" + (" (canary)" if c["state"] == "none" else ""))
                continue
            if not mp4.exists():
                sheet.set_cells(tab, n, {"YouTube Status": "Failed: local MP4 missing"})
                continue
            sheet.set_cells(tab, n, {"YouTube Status": "Publishing"})
            try:
                tags = [t.strip() for t in row["YouTube SEO Tags (Separated)"].split(",") if t.strip()]
                r = PB.for_brand(b["key"]).youtube(b["key"], mp4, row["YouTube Title"], row["YouTube Best SEO Description"], tags, progress=print)
                sheet.set_cells(tab, n, {"YouTube Status": "Published", "YouTube Shorts URL": r["url"]})
                log(video=vid, platform="youtube", status="published", **r)
                if c["state"] == "none":
                    json.dump({"state": "pending", "video": vid, "brand": b["key"], "video_id": r["video_id"], "at": now().isoformat()}, open(CANARY, "w"))
            except Exception as e:
                sheet.set_cells(tab, n, {"YouTube Status": f"Failed: {str(e)[:120]}"})
                log(video=vid, platform="youtube", status="failed", error=str(e)[:400])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true"); g.add_argument("--publish", action="store_true")
    ap.add_argument("--now", default="", help="comma list of video ids to post now (skips schedule time and daily cap)")
    a = ap.parse_args()
    lock = open(K.STATE / "scheduler.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        sys.exit("another scheduler run is still going")
    run(a.publish, {x.strip() for x in a.now.split(',') if x.strip()})
