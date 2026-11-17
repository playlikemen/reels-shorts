#!/usr/bin/env python3.11
"""sync_sheet.py: Manage, synchronize, and beautify video records in Google Sheets.

Spreadsheet: https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit
Tabs: @StackShade, @indexfast
Composio Account: googlesheets_louse-token
"""

import sys
import os
import json
import re
import subprocess
import argparse

SPREADSHEET_ID = "1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk"
ACCOUNT_ID = "googlesheets_louse-token"

TAB_SHEET_IDS = {
    "@StackShade": 0,
    "@indexfast": 1056788903,
    "@BehaviourSchool": 875156192
}

HEADERS = [
    "Video ID",                       # Col A (0)
    "Date",                           # Col B (1)
    "Category / Topic",               # Col C (2)
    "Format",                         # Col D (3)
    "Duration",                       # Col E (4)
    "Local Path",                     # Col F (5)
    "Google Drive Folder",            # Col G (6)
    "Direct MP4 Download Link",       # Col H (7)
    "YouTube Title",                  # Col I (8)
    "YouTube SEO Tags (Separated)",   # Col J (9)
    "YouTube Best SEO Description",   # Col K (10)
    "Instagram Viral Caption",        # Col L (11)
    "Instagram Hashtags",             # Col M (12)
    "Instagram Status",               # Col N (13)
    "Instagram Post URL",             # Col O (14)
    "YouTube Status",                 # Col P (15)
    "YouTube Shorts URL"              # Col Q (16)
]

COL_WIDTHS = [
    90,   # A: Video ID
    100,  # B: Date
    180,  # C: Category / Topic
    150,  # D: Format
    80,   # E: Duration
    200,  # F: Local Path
    180,  # G: Drive Folder Link
    230,  # H: Direct MP4 Download Link
    260,  # I: YouTube Title
    260,  # J: YouTube SEO Tags
    340,  # K: YouTube Description
    320,  # L: Instagram Viral Caption
    220,  # M: Instagram Hashtags
    120,  # N: Instagram Status
    180,  # O: Instagram Permalink
    120,  # P: YouTube Status
    180   # Q: YouTube Shorts URL
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

def call_sheets_batch_update(requests):
    key = get_composio_key()
    req_body = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "COMPOSIO_PROXY_EXECUTE",
            "arguments": {
                "toolkit_slug": "googlesheets",
                "endpoint": f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}:batchUpdate",
                "method": "POST",
                "body": {"requests": requests}
            }
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
    return res

def get_all_rows(sheet_tab="@StackShade"):
    res = call_composio_tool("GOOGLESHEETS_VALUES_GET", {
        "spreadsheet_id": SPREADSHEET_ID,
        "range": f"'{sheet_tab}'!A1:Q100"
    })
    results = res.get("data", {}).get("results", [{}])[0]
    return results.get("response", {}).get("data", {}).get("values", [])

def validate_video_deliverable(video_data):
    """Guarantees the video file exists and is strictly not 0 KB before sheet entry."""
    local_path = video_data.get("local_path")
    if not local_path or not os.path.exists(local_path):
        raise FileNotFoundError(f"Validation Error: Video file not found at '{local_path}'. Cannot add to sheet.")
    
    file_size = os.path.getsize(local_path)
    if file_size < 100 * 1024:  # Under 100 KB is invalid/empty
        raise ValueError(f"Validation Error: Video file '{local_path}' is {file_size} bytes (0 KB or corrupted). Refusing to add to sheet.")

    direct_link = video_data.get("direct_download_link", "")
    if not direct_link:
        raise ValueError("Validation Error: Missing direct_download_link in metadata. Run sync_drive.py first.")

    print(f"Video validation PASSED: {local_path} ({round(file_size/1024/1024, 2)} MB) with verified download link.")
    return True

def beautify_tab(sheet_tab="@StackShade"):
    """Applies modern executive styling, frozen header, column widths and padding."""
    sheet_id = TAB_SHEET_IDS.get(sheet_tab, 0)
    print(f"Beautifying tab '{sheet_tab}' (Sheet ID: {sheet_id})...")

    requests = [
        # 1. Freeze Header Row 1
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1}
                },
                "fields": "gridProperties.frozenRowCount"
            }
        },
        # 2. Header Row Style: Dark Obsidian #0F172A, Bold White Text, Centered
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": len(HEADERS)
                },
                "cell": {
                    "userEnteredFormat": {
                        "backgroundColor": {"red": 15/255, "green": 23/255, "blue": 42/255},
                        "textFormat": {
                            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                            "bold": True,
                            "fontSize": 10
                        },
                        "horizontalAlignment": "CENTER",
                        "verticalAlignment": "MIDDLE",
                        "wrapStrategy": "CLIP"
                    }
                },
                "fields": "userEnteredFormat(backgroundColor,textFormat,horizontalAlignment,verticalAlignment,wrapStrategy)"
            }
        },
        # 3. Header Row Height: 42px
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": 0,
                    "endIndex": 1
                },
                "properties": {"pixelSize": 42},
                "fields": "pixelSize"
            }
        },
        # 4. Text wrap strategy for SEO columns (J: SEO tags, K: Description, L: Viral caption)
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 1,
                    "endRowIndex": 100,
                    "startColumnIndex": 9,
                    "endColumnIndex": 13
                },
                "cell": {
                    "userEnteredFormat": {
                        "wrapStrategy": "WRAP",
                        "verticalAlignment": "TOP"
                    }
                },
                "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"
            }
        }
    ]

    # 5. Set Optimal Column Widths
    for idx, width in enumerate(COL_WIDTHS):
        requests.append({
            "updateDimensionProperties": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "COLUMNS",
                    "startIndex": idx,
                    "endIndex": idx + 1
                },
                "properties": {"pixelSize": width},
                "fields": "pixelSize"
            }
        })

    res = call_sheets_batch_update(requests)
    print(f"Tab '{sheet_tab}' beautification complete!")
    return res

def append_or_update_video_row(video_data, sheet_tab="@StackShade"):
    """
    Strictly validates video deliverable and syncs row with full SEO columns.
    """
    validate_video_deliverable(video_data)
    rows = get_all_rows(sheet_tab)
    
    # 1. Ensure header row is set
    call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
        "spreadsheet_id": SPREADSHEET_ID,
        "range": f"'{sheet_tab}'!A1:Q1",
        "value_input_option": "USER_ENTERED",
        "values": [HEADERS]
    })

    # 2. Check if row exists by Video ID
    row_index = None
    target_id = video_data.get("video_id")
    for idx, r in enumerate(rows):
        if len(r) > 0 and r[0] == target_id:
            row_index = idx + 1
            break

    # 3. Assemble full 17-column row
    new_row = [
        video_data.get("video_id", ""),
        video_data.get("date", ""),
        video_data.get("category", ""),
        video_data.get("format", ""),
        video_data.get("duration", ""),
        video_data.get("local_path", ""),
        video_data.get("drive_link", ""),
        video_data.get("direct_download_link", ""),
        video_data.get("yt_title", video_data.get("title", "") + " #shorts"),
        video_data.get("yt_seo_tags", ""),
        video_data.get("yt_description", ""),
        video_data.get("insta_caption", video_data.get("caption", "")),
        video_data.get("insta_hashtags", ""),
        video_data.get("instagram_status", "Ready"),
        video_data.get("instagram_permalink", video_data.get("instagram_url", "")),
        video_data.get("youtube_status", "Ready"),
        video_data.get("youtube_url", "")
    ]

    if row_index is not None:
        target_range = f"'{sheet_tab}'!A{row_index}:Q{row_index}"
        res = call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
            "spreadsheet_id": SPREADSHEET_ID,
            "range": target_range,
            "value_input_option": "USER_ENTERED",
            "values": [new_row]
        })
        print(f"Updated row {row_index} for {target_id} in {sheet_tab}")
    else:
        next_row = len(rows) + 1 if len(rows) > 0 else 2
        target_range = f"'{sheet_tab}'!A{next_row}:Q{next_row}"
        res = call_composio_tool("GOOGLESHEETS_VALUES_UPDATE", {
            "spreadsheet_id": SPREADSHEET_ID,
            "range": target_range,
            "value_input_option": "USER_ENTERED",
            "values": [new_row]
        })
        print(f"Appended row {next_row} for {target_id} in {sheet_tab}")

    # Auto-beautify tab after update
    beautify_tab(sheet_tab)
    return res

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync videos and beautify Google Sheet")
    parser.add_argument("--tab", default="@StackShade", help="Sheet tab name (@StackShade or @indexfast)")
    parser.add_argument("--list", action="store_true", help="List all rows in sheet")
    parser.add_argument("--beautify", action="store_true", help="Apply executive styling to tab")
    parser.add_argument("--add-json", help="Path to json file or json string representing video")
    args = parser.parse_args()

    if args.beautify:
        beautify_tab(args.tab)
    elif args.list:
        rows = get_all_rows(args.tab)
        for idx, r in enumerate(rows):
            print(f"Row {idx+1}: {r}")
    elif args.add_json:
        if os.path.exists(args.add_json):
            with open(args.add_json) as f:
                data = json.load(f)
        else:
            data = json.loads(args.add_json)
        append_or_update_video_row(data, args.tab)
    else:
        parser.print_help()
