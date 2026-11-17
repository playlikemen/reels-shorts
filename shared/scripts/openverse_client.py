#!/usr/bin/env python3
"""
Openverse Client for Reels & Shorts
Fetches Creative Commons CC0 / CC-BY audio effects and music from Openverse API.
"""

import os
import sys
import json
import ssl
import urllib.request
import argparse

OPENVERSE_API = "https://api.openverse.org/v1/audio/"

def get_ssl_context():
    return ssl._create_unverified_context()

def search_openverse_audio(query, page_size=5, license_type="cc0,by"):
    """Search Openverse audio catalog."""
    url = f"{OPENVERSE_API}?q={urllib.parse.quote(query)}&page_size={page_size}&license_type={license_type}"
    req = urllib.request.Request(url, headers={"User-Agent": "AntigravityReelKit/1.0"})
    try:
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("results", [])
    except Exception as e:
        print(f"[openverse] search error: {e}", file=sys.stderr)
        return []

def download_audio(url, output_path):
    """Download audio preview file from Openverse."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "AntigravityReelKit/1.0"})
    try:
        with urllib.request.urlopen(req, context=get_ssl_context(), timeout=15) as resp, open(output_path, "wb") as f:
            f.write(resp.read())
        print(f"[openverse] Downloaded: {output_path} ({os.path.getsize(output_path)} bytes)")
        return True
    except Exception as e:
        print(f"[openverse] download error: {e}", file=sys.stderr)
        return False

def get_or_download_sfx(name, query, dest_dir="shared/assets/audio"):
    """Ensure a specific SFX exists; if not, query Openverse and download it."""
    dest_path = os.path.join(dest_dir, f"{name}.mp3")
    if os.path.exists(dest_path) and os.path.getsize(dest_path) > 1000:
        return dest_path
    
    results = search_openverse_audio(query, page_size=3)
    for r in results:
        audio_url = r.get("url")
        if audio_url and download_audio(audio_url, dest_path):
            return dest_path
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query Openverse Audio")
    parser.add_argument("--query", "-q", required=True, help="Search query")
    parser.add_argument("--download", "-d", help="Download best match to target path")
    args = parser.parse_args()

    results = search_openverse_audio(args.query, page_size=5)
    print(f"Found {len(results)} matches for '{args.query}':")
    for idx, r in enumerate(results, 1):
        print(f"{idx}. {r.get('title')} | License: {r.get('license')} | {r.get('duration')}ms")
        print(f"   URL: {r.get('url')}")
    
    if args.download and results:
        best_url = results[0].get("url")
        download_audio(best_url, args.download)
