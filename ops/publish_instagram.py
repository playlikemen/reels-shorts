"""Publish one MP4 as an Instagram Reel on a brand's account. Returns {media_id, permalink}.

  python3.11 ops/publish_instagram.py <brand> <mp4> "<caption>"
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K


def publish(brand_key, mp4, caption):
    ig = K.brand(brand_key)["instagram"]
    if os.path.getsize(mp4) < K.MIN_MP4_BYTES:
        raise ValueError(f"{mp4} is under 100 KB")
    box = C.execute("INSTAGRAM_POST_IG_USER_MEDIA", {
        "ig_user_id": ig["ig_user_id"], "media_type": "REELS", "video_file": C.file_arg(mp4),
        "caption": caption.replace("#", "%23"),   # the API wants hashtags URL-encoded
        "share_to_feed": True, "thumb_offset": 1600}, ig["account"], timeout=600)
    creation_id = box.get("id")
    if not creation_id:
        raise RuntimeError(f"no container id: {str(box)[:300]}")
    pub = C.execute("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {"ig_user_id": ig["ig_user_id"], "creation_id": creation_id,
                                                             "max_wait_seconds": 300}, ig["account"], timeout=420)
    media_id = pub.get("id")
    if not media_id:
        raise RuntimeError(f"publish returned no media id: {str(pub)[:300]}")
    permalink = ""
    try:
        permalink = C.execute("INSTAGRAM_GET_IG_MEDIA", {"ig_media_id": media_id, "fields": "id,permalink"}, ig["account"]).get("permalink", "")
    except Exception as e:
        print("warning: published, but permalink lookup failed:", e)
    return {"media_id": media_id, "permalink": permalink}


if __name__ == "__main__":
    print(publish(sys.argv[1], sys.argv[2], sys.argv[3]))
