"""Shared settings for the ops scripts. Brand-specific values live in brands/<brand>/brand.json."""
import json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = pathlib.Path.home() / ".local" / "state" / "reels-shorts"
STATE.mkdir(parents=True, exist_ok=True)

SPREADSHEET_ID = "1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk"
SHEETS_ACCOUNT = "googlesheets_louse-token"
TAB_SHEET_IDS = {"@StackShade": 0, "@indexfast": 1056788903, "@campusloop": 406628331}
DRIVE_ACCOUNT = "googledrive_footle-khir"
DRIVE_PARENT = "1upAISpZAnmyDDYki_FH9tK-FVh_djqLS"
TIMEZONE = "Asia/Kolkata"
MIN_MP4_BYTES = 100 * 1024

# Sheet columns, in order. Column letters follow from the position (A = first).
HEADERS = [
    "Video ID", "Date", "Category / Topic", "Format", "Duration", "Local Path", "Google Drive Folder",
    "Direct MP4 Download Link", "YouTube Title", "YouTube SEO Tags (Separated)", "YouTube Best SEO Description",
    "Instagram Viral Caption", "Instagram Hashtags", "Instagram Status", "Instagram Post URL",
    "YouTube Status", "YouTube Shorts URL", "Scheduled Time (IST)",
]
COL_WIDTHS = [90, 100, 200, 150, 80, 220, 180, 230, 260, 260, 340, 320, 220, 130, 200, 170, 200, 160]


def brand(key):
    return json.load(open(ROOT / "brands" / key / "brand.json"))


def brands():
    return [brand(p.parent.name) for p in sorted((ROOT / "brands").glob("*/brand.json"))]
