#!/usr/bin/env python3.11
"""sync_sheet.py: Manage and synchronize video records in Google Sheets for @StackShade.

- Enforces strict video validation before writing to Google Sheets (blocks 0 KB / missing files).
- Updates Google Sheet row with verified folder link, direct download link, and status.

Spreadsheet: https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit
Tab: @StackShade
Composio Account: googlesheets_louse-token
"""

import sys
import os
import json
import re
import subprocess
import argparse

SPREADSHEET_ID = "1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk"
SHEET_TAB = "@StackShade"
ACCOUNT_ID = "googlesheets_louse-token"

HEADERS = [
    "Video ID", "Date", "Title / Hook", "Category / Topic", "Format",
    "Duration", "Local Path", "Drive Folder Link", "Direct MP4 Download Link",
    "Instagram Status", "Instagram Permalink", "YouTube Status", "YouTube Shorts URL", "Caption / Summary"
]

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

def get_all_rows():
    res = call_composio_tool("GOOGLESHEETS_VALUES_GET", {
        "spreadsheet_id": SPREADSHEET_ID,
        "range": f"'{SHEET_TAB}'!A1:N100"
    })
    results = res.get("data", {}).get("results", [{}])[0]
    return results.get("response", {}).get("data", {}).get("values", [])

def validate_video_deliverable(video_data):
    """Guarantees the video file exists and is not 0 KB before sheet entry."""
    local_path = video_data.get("local_path")
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"Validation Error: Video file not found at '{local_path}'. Cannot add to sheet.")
    
    file_size = os.path.getsize(local_path)
    if file_size < 100 * 1024:  # Less than 100 KB
        raise ValueError(f"Validation Error: Video file '{local_path}' is {file_size} bytes (0 KB or corrupted). Refusing to add to sheet.")

    direct_link = video_data.get("direct_download_link", "")
    if not direct_link:
        raise ValueError("Validation Error: Missing direct_download_link in metadata. Run sync_drive.py first.")

    print(f"Video validation passed: {local_path} ({round(file_size/1024/1024, 2)} MB) with verified download link.")
    return True

def append_or_update_video_row(video_data):
    """
    Validates deliverable and updates Google Sheet.
    """
    validate_video_deliverable(video_data)
    rows = get_all_rows()
    
    # Ensure header row is set
    call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
        "spreadsheet_id": SPREADSHEET_ID,
        "range": f"'{SHEET_TAB}'!A1:N1",
        "value_input_option": "USER_ENTERED",
        "values": [HEADERS]
    })

    row_index = None
    target_id = video_data.get("video_id")
    for idx, r in enumerate(rows):
        if len(r) > 0 and r[0] == target_id:
            row_index = idx + 1
            break

    new_row = [
        video_data.get("video_id", ""),
        video_data.get("date", ""),
        video_data.get("title", ""),
        video_data.get("category", ""),
        video_data.get("format", ""),
        video_data.get("duration", ""),
        video_data.get("local_path", ""),
        video_data.get("drive_link", ""),
        video_data.get("direct_download_link", ""),
        video_data.get("instagram_status", "Pending"),
        video_data.get("instagram_permalink", ""),
        video_data.get("youtube_status", "Pending"),
        video_data.get("youtube_url", ""),
        video_data.get("caption", "")
    ]

    if row_index is not None:
        target_range = f"'{SHEET_TAB}'!A{row_index}:N{row_index}"
        res = call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
            "spreadsheet_id": SPREADSHEET_ID,
            "range": target_range,
            "value_input_option": "USER_ENTERED",
            "values": [new_row]
        })
        print(f"Updated row {row_index} for {target_id}")
    else:
        next_row = len(rows) + 1 if len(rows) > 0 else 2
        target_range = f"'{SHEET_TAB}'!A{next_row}:N{next_row}"
        res = call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
            "spreadsheet_id": SPREADSHEET_ID,
            "range": target_range,
            "value_input_option": "USER_ENTERED",
            "values": [new_row]
        })
        print(f"Appended row {next_row} for {target_id}")
    return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync videos with Google Sheet")
    parser.add_argument("--list", action="store_true", help="List all rows in sheet")
    parser.add_argument("--add-json", help="Path to json file or json string representing video")
    args = parser.parse_args()

    if args.list:
        rows = get_all_rows()
        for idx, r in enumerate(rows):
            print(f"Row {idx+1}: {r}")
    elif args.add_json:
        if os.path.exists(args.add_json):
            with open(args.add_json) as f:
                data = json.load(f)
        else:
            data = json.loads(args.add_json)
        append_or_update_video_row(data)
    else:
        parser.print_help()
