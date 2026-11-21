"""Reels Studio: a password-protected web dashboard over the reels-shorts pipeline.

It reuses the ops/ modules (sheet, scheduler, publishers, insights) instead of rewriting them. See studio/README.md.
"""
import os, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OPS = ROOT / "ops"
if str(OPS) not in sys.path:
    sys.path.insert(0, str(OPS))

HOME = pathlib.Path.home()
STATE = pathlib.Path(os.environ.get("STUDIO_STATE", HOME / ".local" / "state" / "reels-shorts"))
CONFIG_DIR = pathlib.Path(os.environ.get("STUDIO_CONFIG", HOME / ".config" / "reels-studio"))
DB_PATH = pathlib.Path(os.environ.get("STUDIO_DB", STATE / "studio.db"))
BACKUP_DIR = STATE / "backup"
JOB_LOGS = STATE / "studio-jobs"
CACHE = STATE / "studio-cache"
WEB = pathlib.Path(__file__).resolve().parent / "web"
FILMCRAFT = pathlib.Path(os.environ.get("STUDIO_FILMCRAFT", HOME / ".local/opt/filmcraft/web/filmcraft-web-0.20.1"))
EARSHOT = pathlib.Path(os.environ.get("STUDIO_EARSHOT", HOME / ".local/bin/earshot"))
SFX_BANK = ROOT / "engine" / "sfx_bank"
HOST, PORT = "127.0.0.1", int(os.environ.get("STUDIO_PORT", "4820"))
PY = sys.executable or "python3.11"
