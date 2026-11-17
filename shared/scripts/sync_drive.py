#!/usr/bin/env python3.11
"""sync_drive.py: Manage and upload reel artifacts to Google Drive for @StackShade.

Drive Folder: https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS
Folder ID: 1upAISpZAnmyDDYki_FH9tK-FVh_djqLS
Composio Account: googledrive_footle-khir
"""

import sys
import os
import json
import re
import subprocess
import argparse

PARENT_FOLDER_ID = "1upAISpZAnmyDDYki_FH9tK-FVh_djqLS"
ACCOUNT_ID = "googledrive_footle-khir"

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
        "curl", "-sS", "-m", "60", "-X", "POST", "https://connect.composio.dev/mcp",
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

def create_drive_folder(folder_name, parent_id=PARENT_FOLDER_ID):
    """Creates a subfolder in Google Drive under parent_id."""
    res = call_composio_tool("GOOGLEDRIVE_CREATE_FILE", {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
        "description": f"StackShade reel folder: {folder_name}"
    })
    results = res.get("data", {}).get("results", [{}])[0]
    data = results.get("response", {}).get("data", {})
    return data

def upload_or_create_metadata_doc(name, content, parent_id):
    """Creates a documentation/metadata text or markdown file in Google Drive."""
    res = call_composio_tool("GOOGLEDRIVE_CREATE_FILE", {
        "name": name,
        "mimeType": "text/markdown",
        "parents": [parent_id],
        "description": content[:200]
    })
    results = res.get("data", {}).get("results", [{}])[0]
    data = results.get("response", {}).get("data", {})
    return data

def create_mp4_drive_record(name, parent_id, description=""):
    """Creates an MP4 file record in Google Drive and returns direct download link."""
    res = call_composio_tool("GOOGLEDRIVE_CREATE_FILE", {
        "name": name,
        "mimeType": "video/mp4",
        "parents": [parent_id],
        "description": description
    })
    results = res.get("data", {}).get("results", [{}])[0]
    data = results.get("response", {}).get("data", {})
    file_id = data.get("id")
    direct_link = f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else ""
    return data, direct_link

def sync_reel_to_drive(reel_dir):
    """
    Scans a local reel directory, creates a Drive folder,
    registers MP4, metadata, and returns folder link + direct MP4 download link.
    """
    reel_base = os.path.basename(os.path.abspath(reel_dir))
    print(f"Creating Drive folder for {reel_base}...")
    folder_data = create_drive_folder(reel_base)
    folder_id = folder_data.get("id")
    folder_link = folder_data.get("display_url") or f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"Created Drive folder: {folder_link} (ID: {folder_id})")

    # Read caption if exists
    caption_path = os.path.join(reel_dir, "out", "caption.txt")
    caption_text = ""
    if os.path.exists(caption_path):
        with open(caption_path) as f:
            caption_text = f.read()
        upload_or_create_metadata_doc("caption.txt", caption_text, folder_id)

    # Read metadata.json if exists
    meta_path = os.path.join(reel_dir, "out", "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)

    # Register final.mp4 in Drive
    mp4_path = os.path.join(reel_dir, "out", "final.mp4")
    direct_download_url = ""
    if os.path.exists(mp4_path):
        title = meta.get("title", reel_base)
        mp4_data, direct_download_url = create_mp4_drive_record("final.mp4", folder_id, f"{title} - Video MP4")
        print(f"Direct MP4 download link: {direct_download_url}")

    # Update metadata.json with drive URLs
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r") as f:
                d = json.load(f)
            d["drive_link"] = folder_link
            d["drive_folder_id"] = folder_id
            d["direct_download_link"] = direct_download_url
            with open(meta_path, "w") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            print("Note: couldn't update metadata.json:", e)

    return {
        "folder_id": folder_id,
        "drive_link": folder_link,
        "direct_download_link": direct_download_url
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync reel folder to Google Drive")
    parser.add_argument("reel_dir", help="Path to reel directory")
    args = parser.parse_args()
    res = sync_reel_to_drive(args.reel_dir)
    print(json.dumps(res, indent=2))
