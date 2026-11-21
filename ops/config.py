"""Shared settings for the ops scripts. Brand-specific values live in brands/<brand>/brand.json."""
import json, pathlib, re

ROOT = pathlib.Path(__file__).resolve().parent.parent
STATE = pathlib.Path.home() / ".local" / "state" / "reels-shorts"
STATE.mkdir(parents=True, exist_ok=True)

SPREADSHEET_ID = "1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk"
SHEETS_ACCOUNT = "googlesheets_louse-token"
TAB_SHEET_IDS = {"@StackShade": 0, "@indexfast": 1056788903, "@campusloop": 406628331, "@craftlayer": 1350891349}
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


# Per-channel publishing settings written by the studio (Settings > Channels). They overlay brand.json so cron, the
# CLI and the studio read one value: {"<brand key>": {"auto_publish": bool, "youtube_auto": bool, "slots": ["12:30"],
# "cap": 2}}. A missing key keeps the brand.json value; auto-publish and YouTube auto-upload default to on.
CHANNEL_KEYS = {"auto_publish", "youtube_auto", "slots", "cap"}
SLOT_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def channels_path():
    return STATE / "channels.json"


def channels():
    try:
        return json.loads(channels_path().read_text())
    except (OSError, ValueError):
        return {}


def save_channel(key, values):
    """Validate and store one brand's channel settings. Returns (before, after) for the audit log."""
    bad = set(values) - CHANNEL_KEYS
    if bad:
        raise ValueError(f"unknown channel settings: {', '.join(sorted(bad))}")
    clean = {}
    for k, v in values.items():
        if k in ("auto_publish", "youtube_auto"):
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be true or false")
            clean[k] = v
        elif k == "slots":
            slots = sorted({str(x).strip() for x in (v or []) if str(x).strip()})
            if not slots or not all(SLOT_RE.match(x) for x in slots):
                raise ValueError("slots: one or more times like 12:30")
            clean[k] = slots
        elif k == "cap":
            if v in (None, "", 0):
                clean[k] = None
            else:
                try:
                    clean[k] = int(v)
                except (TypeError, ValueError):
                    raise ValueError("cap must be a whole number")
                if not 1 <= clean[k] <= 20:
                    raise ValueError("cap must be between 1 and 20")
    data = channels()
    before = dict(data.get(key) or {})
    data[key] = {**before, **clean}
    path = channels_path()
    path.write_text(json.dumps(data, indent=1) + "\n")
    return before, data[key]


def _overlay(b):
    c = channels().get(b["key"]) or {}
    b["auto_publish"] = c.get("auto_publish", b.get("auto_publish", True))
    b["youtube_auto"] = c.get("youtube_auto", b.get("youtube_auto", True))
    if c.get("slots"):
        b["slots_ist"] = c["slots"]
    if "cap" in c:
        b["max_reels_per_day"] = c["cap"]
    return b


def brand(key):
    return _overlay(json.load(open(ROOT / "brands" / key / "brand.json")))


def brands():
    return [brand(p.parent.name) for p in sorted((ROOT / "brands").glob("*/brand.json"))]
