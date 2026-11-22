"""Upload one MP4 as a YouTube Short on a brand's channel, and check that an upload is still there.

  python3.11 ops/publish_youtube.py <brand> <mp4> "<title>" "<description>" "tag1,tag2"

YouTube has removed Composio uploads to StackShade before (Oct 2026). The scheduler therefore treats the
first upload as a canary: see ops/scheduler.py.
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K


def upload(brand_key, mp4, title, description, tags):
    yt = K.brand(brand_key)["youtube"]
    if not yt:
        raise ValueError(f"{brand_key} has no YouTube channel connected")
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"
    args = {"title": title[:100], "description": description, "tags": tags[:15], "categoryId": "28", "privacyStatus": "public"}
    try:
        data = C.execute("YOUTUBE_UPLOAD_VIDEO", {**args, "videoFilePath": C.file_arg(mp4)}, yt["account"], timeout=900)
    except RuntimeError as first:
        # the shared upload quota sometimes rejects this route; the multipart tool is the documented retry
        try:
            data = C.execute("YOUTUBE_MULTIPART_UPLOAD_VIDEO", {**args, "videoFile": C.file_arg(mp4)}, yt["account"], timeout=900)
        except RuntimeError as second:
            raise RuntimeError(f"both upload routes failed: {first} | {second}")
    vid = data.get("id") or (data.get("response_data") or {}).get("id") or (data.get("video") or {}).get("id")
    if not vid:
        raise RuntimeError(f"upload returned no video id: {str(data)[:300]}")
    return {"video_id": vid, "url": f"https://youtube.com/shorts/{vid}"}


def still_up(brand_key, video_id):
    """True if the channel still lists the video."""
    yt = K.brand(brand_key)["youtube"]
    try:
        data = C.execute("YOUTUBE_LIST_CHANNEL_VIDEOS", {"channelId": yt["channel_id"], "part": "id", "maxResults": 50}, yt["account"])
        if video_id in str(data):
            return True
    except Exception as e:
        print(f"warning: YOUTUBE_LIST_CHANNEL_VIDEOS check failed ({e}); falling back to HTTP check")
    
    # Fallback to direct HTTP check on YouTube
    try:
        import urllib.request
        req = urllib.request.Request(
            f"https://www.youtube.com/shorts/{video_id}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        html = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
        return "This video is unavailable" not in html and '"status":"ERROR"' not in html
    except Exception:
        return False


if __name__ == "__main__":
    print(upload(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5].split(",")))
