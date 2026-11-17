#!/usr/bin/env python3.11
"""publish_instagram.py: Publish Instagram Reels for @stackshade and @indexfast via Composio MCP.

Supported Brands:
- stackshade: Composio account `instagram_create-beta` (Instagram: @stackshade)
- indexfast: Composio account `instagram_dam-hinder` (Instagram: @indexfast)

Input: <reel_folder> (e.g., brands/stackshade/reels/... or brands/indexfast/reels/...)
"""

import sys
import os
import json
import re
import subprocess
import argparse
from datetime import datetime

BRAND_ACCOUNTS = {
    "stackshade": "instagram_create-beta",
    "indexfast": "instagram_dam-hinder"
}

BRAND_TABS = {
    "stackshade": "@StackShade",
    "indexfast": "@indexfast"
}

def get_composio_key():
    config_path = os.path.expanduser("~/.claude.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path) as f:
        data = json.load(f)
    return data["mcpServers"]["composio"]["headers"]["x-consumer-api-key"]

def call_composio_tool(slug, args, account):
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

def detect_brand(reel_folder):
    norm = os.path.abspath(reel_folder)
    if "indexfast" in norm:
        return "indexfast"
    return "stackshade"

def publish_reel(reel_folder, video_url=None, account=None):
    brand = detect_brand(reel_folder)
    account_id = account or BRAND_ACCOUNTS.get(brand, "instagram_create-beta")
    tab_name = BRAND_TABS.get(brand, "@StackShade")

    caption_path = os.path.join(reel_folder, "out", "caption.txt")
    meta_path = os.path.join(reel_folder, "out", "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)

    if os.path.exists(caption_path):
        with open(caption_path) as f:
            caption = f.read().strip()
    elif meta:
        caption = meta.get("instagram_viral_caption") or meta.get("caption", "")
        if meta.get("instagram_hashtags"):
            caption += "\n\n" + meta.get("instagram_hashtags")
    else:
        raise FileNotFoundError(f"Missing caption file: {caption_path} or metadata.json")

    # Resolve public video URL
    target_url = video_url or meta.get("public_video_url")
    if not target_url:
        target_url = meta.get("direct_download_link")

    if not target_url:
        raise ValueError("No video URL provided or found in metadata. Run sync_drive.py or deploy public URL first.")

    print(f"[{brand.upper()}] Initiating Instagram Reel publish via account '{account_id}'...")
    print(f"Video URL: {target_url}")
    print(f"Caption snippet: {caption[:80]}...")

    # 1. Create Media Container
    container_res = call_composio_tool("INSTAGRAM_POST_IG_USER_MEDIA", {
        "ig_user_id": "me",
        "media_type": "REELS",
        "video_url": target_url,
        "caption": caption,
        "share_to_feed": True
    }, account=account_id)
    
    results = container_res.get("data", {}).get("results", [{}])[0]
    box = results.get("response", {}).get("data", {})
    creation_id = box.get("id")
    if not creation_id:
        error_msg = results.get("error") or box.get("message") or str(results)
        raise RuntimeError(f"Failed to create Instagram container: {error_msg}")

    print(f"Created container: {creation_id}. Publishing Reel...")

    # 2. Publish Container
    pub_res = call_composio_tool("INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH", {
        "ig_user_id": "me",
        "creation_id": creation_id,
        "max_wait_seconds": 300
    }, account=account_id)
    pub_box = pub_res.get("data", {}).get("results", [{}])[0].get("response", {}).get("data", {})
    media_id = pub_box.get("id")
    if not media_id:
        error_msg = pub_res.get("data", {}).get("results", [{}])[0].get("error") or str(pub_res)
        raise RuntimeError(f"Failed to publish Instagram media: {error_msg}")

    print(f"Published Reel media ID: {media_id}. Fetching permalink...")

    # 3. Retrieve Permalink
    permalink = ""
    try:
        info_res = call_composio_tool("INSTAGRAM_GET_IG_MEDIA", {
            "ig_media_id": media_id,
            "fields": "id,permalink,caption,timestamp"
        }, account=account_id)
        info_box = info_res.get("data", {}).get("results", [{}])[0].get("response", {}).get("data", {})
        permalink = info_box.get("permalink", "")
    except Exception as e:
        print(f"Warning: Could not fetch permalink: {e}")

    result = {
        "status": "Published",
        "brand": brand,
        "account": account_id,
        "media_id": media_id,
        "permalink": permalink,
        "timestamp": datetime.utcnow().isoformat()
    }

    # 4. Update metadata.json
    meta["instagram_status"] = "Published"
    meta["instagram_permalink"] = permalink
    meta["instagram_media_id"] = media_id
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    # 5. Sync to Google Sheet
    try:
        from sync_sheet import append_or_update_video_row
        append_or_update_video_row(meta, sheet_tab=tab_name)
    except Exception as e:
        print(f"Warning: Could not auto-sync sheet: {e}")

    # 6. Log to publish-log.jsonl
    log_file = "pipeline/publish-log.jsonl"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "a") as f:
        f.write(json.dumps(result) + "\n")

    return result

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish Instagram Reel")
    parser.add_argument("reel_folder", help="Path to reel folder")
    parser.add_argument("--url", help="Public HTTPS video URL")
    parser.add_argument("--account", help="Composio account ID override")
    args = parser.parse_args()
    res = publish_reel(args.reel_folder, args.url, args.account)
    print(json.dumps(res, indent=2))
