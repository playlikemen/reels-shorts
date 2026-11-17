#!/usr/bin/env python3.11
"""daily_scheduler.py: Automated daily pipeline to post 2-3 reels on Instagram for StackShade and IndexFast.

Content Mix:
1. StackShade (System Design / Deep Engineering)
2. StackShade (Tech Trend / News / Cyber Alert)
3. IndexFast (Google Indexing / SEO Automation Hack)

Usage:
  python3.11 pipeline/daily_scheduler.py --dry-run
  python3.11 pipeline/daily_scheduler.py --publish
"""

import sys
import os
import json
import glob
import argparse
from datetime import datetime

# Add shared/scripts to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../shared/scripts")))

from publish_instagram import publish_reel, BRAND_ACCOUNTS, BRAND_TABS
from sync_drive import sync_reel_to_drive
from sync_sheet import append_or_update_video_row, get_all_rows, beautify_tab

REELS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../brands"))

def scan_ready_reels(brand_filter=None):
    """
    Finds all reels that have generated MP4s and are ready to publish.
    Returns categorized list: { 'stackshade_arch': [...], 'stackshade_news': [...], 'indexfast': [...] }
    """
    pattern = os.path.join(REELS_ROOT, "*", "reels", "*", "out", "metadata.json")
    meta_files = glob.glob(pattern)
    
    ready_queue = {
        "stackshade_arch": [],
        "stackshade_news": [],
        "indexfast": []
    }

    for mf in sorted(meta_files):
        try:
            with open(mf) as f:
                data = json.load(f)
        except Exception as e:
            print(f"Warning: Could not parse {mf}: {e}")
            continue

        reel_dir = os.path.dirname(os.path.dirname(mf))
        mp4_path = os.path.join(reel_dir, "out", "final.mp4")
        
        # Validation: Deliverable must exist and be > 100 KB
        if not os.path.exists(mp4_path) or os.path.getsize(mp4_path) < 100 * 1024:
            continue

        brand = "indexfast" if "indexfast" in reel_dir else "stackshade"
        if brand_filter and brand != brand_filter:
            continue

        item = {
            "reel_dir": reel_dir,
            "meta_path": mf,
            "data": data,
            "brand": brand,
            "video_id": data.get("video_id", os.path.basename(reel_dir)),
            "title": data.get("title", ""),
            "category": data.get("category", ""),
            "status": data.get("instagram_status", "Ready")
        }

        if brand == "indexfast":
            ready_queue["indexfast"].append(item)
        else:
            cat = item["category"].lower()
            if "news" in cat or "alert" in cat or "trend" in cat or "cyber" in cat:
                ready_queue["stackshade_news"].append(item)
            else:
                ready_queue["stackshade_arch"].append(item)

    return ready_queue

def run_daily_schedule(dry_run=False, brand_filter=None):
    print("=" * 65)
    print(f"  DAILY REELS/SHORTS AUTOMATED PIPELINE - {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
    print("=" * 65)

    queue = scan_ready_reels(brand_filter)
    
    print(f"\n[QUEUE SUMMARY]")
    print(f"  • StackShade Architecture Reels: {len(queue['stackshade_arch'])} ready")
    print(f"  • StackShade Trend/News Reels:   {len(queue['stackshade_news'])} ready")
    print(f"  • IndexFast SEO Reels:           {len(queue['indexfast'])} ready")

    # Select daily slots: 1 Arch + 1 Trend/News + 1 IndexFast
    slots = []
    
    # 1. StackShade Architecture
    arch_pending = [r for r in queue["stackshade_arch"] if r["status"] != "Published"]
    if arch_pending:
        slots.append(("StackShade Architecture", arch_pending[0]))

    # 2. StackShade Trend / News
    news_pending = [r for r in queue["stackshade_news"] if r["status"] != "Published"]
    if news_pending:
        slots.append(("StackShade Trend / News", news_pending[0]))
    elif len(arch_pending) > 1:
        # Fallback to second architecture reel if no separate news reel
        slots.append(("StackShade Engineering 2", arch_pending[1]))

    # 3. IndexFast
    index_pending = [r for r in queue["indexfast"] if r["status"] != "Published"]
    if index_pending:
        slots.append(("IndexFast Growth / SEO", index_pending[0]))

    print(f"\n[PLANNED POSTING SLOTS: {len(slots)} VIDEOS TODAY]")
    for label, item in slots:
        print(f"  [{label}] ID: {item['video_id']} | Title: {item['title'][:45]}... | Status: {item['status']}")

    if dry_run:
        print("\n[DRY RUN COMPLETE] No live posts executed.")
        return slots

    # Execute Publishing Cycle
    results = []
    for label, item in slots:
        print(f"\n---> Executing Slot: {label} ({item['video_id']})")
        reel_dir = item["reel_dir"]

        # Ensure Drive upload is synced & non-zero
        if not item["data"].get("direct_download_link"):
            print("Syncing deliverable to Google Drive first...")
            synced_meta = sync_reel_to_drive(reel_dir)
            item["data"] = synced_meta

        # Publish via Composio Instagram
        try:
            pub_res = publish_reel(reel_dir)
            print(f"SUCCESS: Published to Instagram! Link: {pub_res.get('permalink')}")
            results.append(pub_res)
        except Exception as e:
            print(f"Publishing warning: {e}")
            results.append({"video_id": item["video_id"], "error": str(e), "status": "Failed"})

    # Beautify both tabs after posting cycle
    print("\nBeautifying Google Sheet tabs...")
    try:
        beautify_tab("@StackShade")
        beautify_tab("@indexfast")
    except Exception as e:
        print(f"Beautify note: {e}")

    print("\nDaily schedule cycle finished.")
    return results

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily Reels & Shorts Post Scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Inspect planned posts without publishing")
    parser.add_argument("--publish", action="store_true", help="Execute live publishing cycle")
    parser.add_argument("--brand", choices=["stackshade", "indexfast"], help="Filter by brand")
    args = parser.parse_args()

    if not args.publish and not args.dry_run:
        # Default to dry-run to prevent accidental double-posting
        args.dry_run = True

    run_daily_schedule(dry_run=args.dry_run, brand_filter=args.brand)
