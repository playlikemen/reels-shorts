"""Publish one MP4 as an Instagram Reel on a brand's account. Returns {media_id, permalink}.

  python3.11 ops/publish_instagram.py <brand> <mp4> "<caption>"

The steps are separate functions so a caller can report progress and keep the container id:
  create_container (uploads the video through Composio) -> publish_container -> get_permalink.
publish() runs all three; `progress(line)` gets one line per step and `on_container(id)` the container id as soon as
Instagram has it (after that point a post may go live even if the caller dies).
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K


def _ig(brand_key):
    return K.brand(brand_key)["instagram"]


def create_container(brand_key, mp4, caption):
    ig = _ig(brand_key)
    if os.path.getsize(mp4) < K.MIN_MP4_BYTES:
        raise ValueError(f"{mp4} is under 100 KB")
    box = C.execute("INSTAGRAM_POST_IG_USER_MEDIA", {
        "ig_user_id": ig["ig_user_id"], "media_type": "REELS", "video_file": C.file_arg(mp4),
        "caption": caption.replace("#", "%23"),   # the API wants hashtags URL-encoded
        "share_to_feed": True, "thumb_offset": 1600}, ig["account"], timeout=600)
    creation_id = box.get("id")
    if not creation_id:
        raise RuntimeError(f"no container id: {str(box)[:300]}")
    return creation_id


def publish_container(brand_key, creation_id):
    ig = _ig(brand_key)
    pub = C.execute("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"ig_user_id": ig["ig_user_id"], "creation_id": creation_id,
                                                             "max_wait_seconds": 300}, ig["account"], timeout=420)
    media_id = pub.get("id")
    if not media_id:
        raise RuntimeError(f"publish returned no media id: {str(pub)[:300]}")
    return media_id


def get_permalink(brand_key, media_id):
    try:
        return C.execute("INSTAGRAM_GET_IG_MEDIA", {"ig_media_id": media_id, "fields": "id,permalink"}, _ig(brand_key)["account"]).get("permalink", "")
    except Exception as e:
        print("warning: published, but permalink lookup failed:", e)
        return ""


def recent_media(brand_key, limit=10):
    """The account's newest media: [{id, permalink, timestamp, caption}]."""
    m = C.execute("INSTAGRAM_GET_IG_USER_MEDIA", {"ig_user_id": "me", "limit": limit, "fields": "id,permalink,timestamp,caption"},
                  _ig(brand_key)["account"])
    return m.get("data") or []


def publish(brand_key, mp4, caption, progress=None, on_container=None):
    say = progress or (lambda line: None)
    say("uploading video to Composio…")
    creation_id = create_container(brand_key, mp4, caption)
    if on_container:
        on_container(creation_id)
    say(f"Instagram container {creation_id} created, processing…")
    say("publishing…")
    media_id = publish_container(brand_key, creation_id)
    permalink = get_permalink(brand_key, media_id)
    say(f"published {permalink or media_id}")
    return {"media_id": media_id, "permalink": permalink, "creation_id": creation_id}


if __name__ == "__main__":
    print(publish(sys.argv[1], sys.argv[2], sys.argv[3], progress=print))
