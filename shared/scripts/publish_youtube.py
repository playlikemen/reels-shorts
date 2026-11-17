#!/usr/bin/env python3.11
"""publish_youtube.py: Upload/publish YouTube Shorts for @StackShade via Composio MCP.

Target Account: youtube_run-retin (alias: https://www.youtube.com/@StackShade)
Input: <reel_folder>
"""

import sys
import os
import json
import re
import subprocess
import argparse
from datetime import datetime

ACCOUNT_ID = "youtube_run-retin"

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

def prepare_youtube_short(reel_folder):
    meta_path = os.path.join(reel_folder, "out", "metadata.json")
    if not os.path.exists(meta_path):
        raise FileNotFoundError(f"Missing metadata file: {meta_path}")
    with open(meta_path) as f:
        meta = json.load(f)

    caption_path = os.path.join(reel_folder, "out", "caption.txt")
    caption = ""
    if os.path.exists(caption_path):
        with open(caption_path) as f:
            caption = f.read().strip()

    title = meta.get("title", "StackShade Engineering Breakdown")
    if "#shorts" not in title.lower():
        title = f"{title} #shorts"

    tags = ["shorts", "coding", "softwareengineering", "systemdesign", "developer", "programming"]
    
    return {
        "title": title[:100],
        "description": caption,
        "tags": tags,
        "categoryId": "28", # Science & Technology
        "privacyStatus": "public"
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Publish YouTube Short")
    parser.add_argument("reel_folder", help="Path to reel folder")
    args = parser.parse_args()
    data = prepare_youtube_short(args.reel_folder)
    print(json.dumps(data, indent=2))
