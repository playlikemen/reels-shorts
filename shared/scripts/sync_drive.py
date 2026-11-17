#!/usr/bin/env python3.11
"""sync_drive.py: Upload and verify reel video and metadata to Google Drive for @StackShade.

- Enforces pre-upload file validation (verifies local MP4 size > 100KB).
- Uses Google Drive resumable upload API to stream full binary video bytes.
- Verifies post-upload Drive metadata to guarantee size > 0 bytes before sheet logging.
- Generates direct one-click download URLs (https://drive.google.com/uc?id={file_id}&export=download).

Drive Folder: https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS
Folder ID: 1upAISpZAnmyDDYki_FH9tK-FVh_djqLS
Composio Accounts: googledrive_footle-khir (owner), googledrive_peho-tiler (proxy)
"""

import sys
import os
import json
import re
import subprocess
import argparse

PARENT_FOLDER_ID = "1upAISpZAnmyDDYki_FH9tK-FVh_djqLS"
OFFICIAL_ACCOUNT = "googledrive_footle-khir"

def get_composio_key():
    config_path = os.path.expanduser("~/.claude.json")
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with open(config_path) as f:
        data = json.load(f)
    return data["mcpServers"]["composio"]["headers"]["x-consumer-api-key"]

def call_composio_tool(slug, args, account=OFFICIAL_ACCOUNT):
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

def call_proxy(endpoint, method, parameters=None, body=None):
    key = get_composio_key()
    payload_args = {
        "toolkit_slug": "googledrive",
        "endpoint": endpoint,
        "method": method
    }
    if parameters:
        payload_args["parameters"] = parameters
    if body:
        payload_args["body"] = body

    req_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "COMPOSIO_PROXY_EXECUTE",
            "arguments": payload_args
        }
    })
    cmd = [
        "curl", "-sS", "-m", "60", "-X", "POST", "https://connect.composio.dev/mcp",
        "-H", f"x-consumer-api-key: {key}",
        "-H", "content-type: application/json",
        "-H", "accept: application/json, text/event-stream",
        "-d", req_body
    ]
    raw = subprocess.run(cmd, capture_output=True, text=True).stdout
    m = re.search(r"^data: (.*)$", raw, re.M)
    if not m:
        raise RuntimeError(f"Composio Proxy error: {raw[:300]}")
    payload = json.loads(m.group(1))
    content_text = payload.get("result", {}).get("content", [{}])[0].get("text", "{}")
    res = json.loads(content_text)
    return res.get("data", {})

def create_drive_folder(folder_name, parent_id=PARENT_FOLDER_ID):
    res = call_composio_tool("GOOGLEDRIVE_CREATE_FILE", {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
        "description": f"StackShade reel folder: {folder_name}"
    })
    results = res.get("data", {}).get("results", [{}])[0]
    return results.get("response", {}).get("data", {})

def upload_binary_file_resumable(local_path, parent_id, remote_name=None, description=""):
    """Streams actual binary bytes into Google Drive using resumable upload."""
    if not os.path.exists(local_path):
        raise FileNotFoundError(f"Local file does not exist: {local_path}")
    
    file_size = os.path.getsize(local_path)
    if file_size < 100 * 1024:  # Must be > 100 KB
        raise ValueError(f"File {local_path} is suspiciously small ({file_size} bytes). Minimum 100 KB required.")

    name = remote_name or os.path.basename(local_path)
    print(f"Initiating Google Drive upload for {name} ({file_size} bytes)...")

    init_data = call_proxy(
        endpoint="https://www.googleapis.com/upload/drive/v3/files",
        method="POST",
        parameters=[{"name": "uploadType", "value": "resumable", "type": "query"}],
        body={
            "name": name,
            "parents": [parent_id],
            "description": description
        }
    )
    upload_url = init_data.get("headers", {}).get("location")
    if not upload_url:
        raise RuntimeError(f"Failed to initiate resumable upload session: {init_data}")

    # Stream the file bytes using curl PUT
    print(f"Streaming {file_size} bytes to Google Drive...")
    put_res = subprocess.run([
        "curl", "-sS", "-m", "300", "-X", "PUT",
        "-H", "Content-Type: video/mp4",
        "-H", f"Content-Length: {file_size}",
        "--upload-file", local_path,
        upload_url
    ], capture_output=True, text=True)

    if put_res.returncode != 0:
        raise RuntimeError(f"cURL upload failed: {put_res.stderr}")

    resp_json = json.loads(put_res.stdout)
    file_id = resp_json.get("id")
    if not file_id:
        raise RuntimeError(f"Upload completed but no file ID returned: {put_res.stdout}")

    # Verify uploaded file size from Google Drive API
    verify_res = call_composio_tool("GOOGLEDRIVE_GET_FILE_METADATA", {
        "fileId": file_id,
        "fields": "id,name,size,webContentLink,webViewLink"
    })
    meta = verify_res.get("data", {}).get("results", [{}])[0].get("response", {}).get("data", {})
    uploaded_size = int(meta.get("size", "0"))

    if uploaded_size == 0 or uploaded_size != file_size:
        raise RuntimeError(f"CRITICAL ERROR: Upload verification failed! Google Drive reported size {uploaded_size} bytes (expected {file_size} bytes).")

    print(f"Upload verified! Size on Drive: {uploaded_size} bytes ({round(uploaded_size/1024/1024, 2)} MB).")

    # Share with anyone as reader so direct download link works for anyone without login
    call_composio_tool("GOOGLEDRIVE_CREATE_PERMISSION", {
        "file_id": file_id,
        "type": "anyone",
        "role": "reader"
    })

    direct_download_url = f"https://drive.google.com/uc?id={file_id}&export=download"
    return {
        "file_id": file_id,
        "file_name": name,
        "size": uploaded_size,
        "view_link": meta.get("webViewLink"),
        "direct_download_url": direct_download_url
    }

def sync_reel_to_drive(reel_dir):
    """
    Validates local video, uploads to Google Drive, verifies size > 0,
    and updates metadata.json with the direct download URL.
    """
    reel_base = os.path.basename(os.path.abspath(reel_dir))
    mp4_path = os.path.join(reel_dir, "out", "final.mp4")
    
    # 1. PRE-CHECK: Verify video file locally
    if not os.path.exists(mp4_path):
        raise FileNotFoundError(f"Missing video deliverable: {mp4_path}")
    local_size = os.path.getsize(mp4_path)
    if local_size == 0:
        raise ValueError(f"CRITICAL: Local video file {mp4_path} is 0 KB! Render must be fixed first.")
    print(f"Validated local video: {mp4_path} ({round(local_size/1024/1024, 2)} MB)")

    # 2. Create / locate Drive folder
    folder_data = create_drive_folder(reel_base)
    folder_id = folder_data.get("id")
    folder_link = folder_data.get("display_url") or f"https://drive.google.com/drive/folders/{folder_id}"

    # 3. Read metadata
    meta_path = os.path.join(reel_dir, "out", "metadata.json")
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            meta = json.load(f)

    # 4. Upload binary video bytes
    title = meta.get("title", reel_base)
    upload_info = upload_binary_file_resumable(
        local_path=mp4_path,
        parent_id=folder_id,
        remote_name="final.mp4",
        description=f"{title} - 1080x1920 MP4 Video"
    )

    # 5. Update metadata.json with verified drive links
    meta["drive_link"] = folder_link
    meta["drive_folder_id"] = folder_id
    meta["drive_file_id"] = upload_info["file_id"]
    meta["drive_file_size"] = upload_info["size"]
    meta["direct_download_link"] = upload_info["direct_download_url"]

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return meta

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync and upload verified reel to Google Drive")
    parser.add_argument("reel_dir", help="Path to reel directory")
    args = parser.parse_args()
    res = sync_reel_to_drive(args.reel_dir)
    print(json.dumps(res, indent=2))
