"""Reel rows for the ops scripts, from the studio store (the source of truth), with the Sheet as a mirror.

Same shape as ops/sheet.py, so the scheduler and make.py did not change much:
  rows(tab)                    -> list of dicts by header name; `_row` is the Video ID
  set_cells(tab, video_id, {}) -> store first, then the Sheet mirror for that row (best effort)
  upsert(tab, record)          -> create or replace the store row, then mirror it
"""
import os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _sync():
    from studio import sync
    return sync


def rows(tab):
    return _sync().store_rows(tab)


def set_cells(tab, key, updates):
    _sync().set_cells(tab, key, updates)


def upsert(tab, record, who="make.py"):
    Y = _sync()
    vid = Y.upsert_local(tab, record, who=who)
    try:
        Y.push_one(vid)
    except Exception as e:
        print(f"Sheet mirror not updated for {vid} ({str(e)[:120]}); the next push retries")
    return vid
