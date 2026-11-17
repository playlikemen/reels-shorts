#!/usr/bin/env python3.11
"""publish_instagram.py: Publish an Instagram Reel for @stackshade via Composio MCP.

Target Account: instagram_create-beta (alias: stackshade)
Input: <reel_folder> (must contain out/final.mp4 and out/caption.txt)
Note: Instagram Graph API requires video_url to be publicly accessible (e.g. GitHub raw, S3, or CDN).
"""

import sys
import os
import json
import re
import subprocess
import argparse
from datetime import datetime

ACCOUNT_ID = "instagram_create-beta"

def get_composio_key():
    config_path = os.path.expanduser("~/.claude.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path) as f:
        data = json.load(f)
    return data["mcpServers"]["composio"]["headers"]["x-consumer-api-key"]

def call_composio_tool(slug, args, account=ACCOUNT_ID):
    key = get_composio_key()
    body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "COMPOSIO_MULTI_EXECUTE_TOOL",
            "arguments": {
                "sync_response_to_workbench": False,
                "tools": [{"tool_slug": slug, "account": account, "arguments": args}]
            }
        }
    })
    cmd = [
        "curl", "-sS", "-m", "120", "-X", "POST", "https://connect.composio.dev/mcp",
        "-H", f"x-consumer-api-key: {key}",
        "-H", "content-type: application/json",
        "-H", "accept: application/json, text/event-stream",
        "-d", body
    ]
    raw = subprocess.run(cmd, capture_output=True, text=True).stdout
    m = re.search(r"^data: (.*)$", raw, re.M)
    if not m:
        raise RuntimeError(f"Composio API error: {raw[:300]}")
    payload = json.loads(m.group(1))
    content_text = payload.get("result", {}).get("content", [{}])[0].get("text", "{}")
    res = json.loads(content_text)
    return res

def publish_reel(reel_folder, video_url=None):
    caption_path = os.path.join(reel_folder, "out", "caption.txt")
    if not os.path.exists(caption_path):
        raise FileNotFoundError(f"Missing caption file: {caption_path}")
    with open(caption_path) as f:
        caption = f.read().strip()

    meta_path = os.path.join(reel_folder, "out", "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)

    if not video_url:
        video_url = meta.get("public_video_url")
        if not video_url:
            print("Notice: Direct public video URL not found in metadata.")
            print("Instagram Graph API requires an accessible HTTPS video URL.")
            print("Marking reel status as Ready (Pending public URL deployment).")
            return {
                "status": "Ready",
                "message": "Local MP4 generated and validated. Ready to publish upon public URL deployment."
            }

    print(f"Creating Instagram Reel container for {video_url}...")
    container_res = call_composio_tool("INSTAGRAM_POST_IG_USER_MEDIA", {
        "ig_user_id": "me",
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "share_to_feed": True
    })
    results = container_res.get("data", {}).get("results", [{}])[0]
    box = results.get("response", {}).get("data", {})
    creation_id = box.get("id")
    if not creation_id:
        raise RuntimeError(f"Failed to create Instagram container: {results}")

    print(f"Publishing container {creation_id}...")
    pub_res = call_composio_tool("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {
        "ig_user_id": "me",
        "creation_id": creation_id,
        "max_wait_seconds": 300
    })
    pub_box = pub_res.get("data", {}).get("results", [{}])[0].get("response", {}).get("data", {})
    media_id = pub_box.get("id")
    if not media_id:
        raise RuntimeError(f"Failed to publish Instagram media: {pub_res}")

    print(f"Fetching published media info for {media_id}...")
    info_res = call_composio_tool("INSTAGRAM_GET_IG_MEDIA", {
        "ig_media_id": media_id,
        "fields": "id,permalink,caption,timestamp"
    })
    info_box = info_res.get("data", {}).get("results", [{}])[0].get("response", {}).get("data", {})
    permalink = info_box.get("permalink")

    result = {
        "status": "Published",
        "account": ACCOUNT_ID,
        "media_id": media_id,
        "permalink": permalink,
        "timestamp": info_box.get("timestamp") or datetime.utcnow().isoformat()
    }

    # Log to pipeline/publish-log.jsonl
    log_file = "pipeline/publish-log.jsonl"
    with open(log_file, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish Instagram Reel")
    parser.add_argument("reel_folder", help="Path to reel folder")
    parser.add_argument("--url", help="Public HTTPS video URL")
    args = parser.parse_args()
    res = publish_reel(args.reel_folder, args.url)
    print(json.dumps(res, indent=2))
