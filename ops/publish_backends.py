"""How a channel posts: one backend per method, chosen by the channel setting `publish_backend`.

  composio  (default) Instagram Graph API and YouTube through Composio (ops/publish_instagram.py, publish_youtube.py)
  metricool not enabled yet: a stub, so the setting and the interface exist

A backend has:
  instagram(brand_key, mp4, caption, progress, on_container) -> {media_id, permalink}
  youtube(brand_key, mp4, title, description, tags, progress) -> {video_id, url}
  recent_instagram(brand_key, limit) -> [{id, permalink, timestamp, caption}]   (used to reconcile interrupted posts)
"""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
import config as K

NAMES = ("composio", "metricool")


class Composio:
    name = "composio"

    def instagram(self, brand_key, mp4, caption, progress=None, on_container=None):
        import publish_instagram
        return publish_instagram.publish(brand_key, mp4, caption, progress=progress, on_container=on_container)

    def youtube(self, brand_key, mp4, title, description, tags, progress=None):
        import publish_youtube
        (progress or (lambda s: None))("uploading video to YouTube through Composio…")
        r = publish_youtube.upload(brand_key, mp4, title, description, tags)
        (progress or (lambda s: None))(f"published {r['url']}")
        return r

    def recent_instagram(self, brand_key, limit=10):
        import publish_instagram
        return publish_instagram.recent_media(brand_key, limit)


class Metricool:
    """Placeholder. Posting through the Metricool connector is not enabled; say so instead of guessing its API."""
    name = "metricool"

    def _no(self, *a, **k):
        raise NotImplementedError("the metricool posting method is not enabled yet; set the channel back to composio")

    instagram = youtube = recent_instagram = _no


BACKENDS = {"composio": Composio(), "metricool": Metricool()}


def for_brand(brand_key):
    name = K.brand(brand_key).get("publish_backend", "composio")
    return BACKENDS.get(name) or BACKENDS["composio"]
