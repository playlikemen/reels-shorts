#!/usr/bin/env python3.11
"""Rebuild sheet rows for reels that are already archived on Drive, without uploading again.

  python3.11 ops/repair_rows.py CR-118-EN CR-119-EN ...                   # append or replace by Video ID
  python3.11 ops/repair_rows.py CR-101-HI --row 2 --status Published --url https://...

Used after the 2026-11-20 incident where truncated Composio reads made every upsert land on row 2.
The record is rebuilt from the spec (same fields as ops/make.py) plus the Drive folder found by name.
"""
import argparse, json, re, subprocess, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import composio as C, config as K, sheet
sys.path.insert(0, str(K.ROOT / "engine"))
from build import apply_lang


def drive_links(vid):
    q = f"name contains '{vid}' and '{K.DRIVE_PARENT}' in parents and trashed = false"
    folders = C.execute("GOOGLEDRIVE_FIND_FILE", {"q": q, "fields": "files(id,name,createdTime)"}, K.DRIVE_ACCOUNT).get("files", [])
    if not folders:
        raise SystemExit(f"{vid}: no Drive folder")
    f = sorted(folders, key=lambda x: x["createdTime"])[-1]
    files = C.execute("GOOGLEDRIVE_FIND_FILE", {"q": f"'{f['id']}' in parents and trashed = false", "fields": "files(id,name)"}, K.DRIVE_ACCOUNT).get("files", [])
    mp4 = next(x for x in files if x["name"].endswith(".mp4"))
    return f"https://drive.google.com/drive/folders/{f['id']}", f"https://drive.google.com/uc?id={mp4['id']}&export=download"


def record(vid):
    base, lang = re.match(r"(CR-\d+)-(HI|EN)$", vid).groups()
    spec = apply_lang(json.load(open(K.ROOT / "specs" / "craftlayer" / f"{base}.json")), lang.lower())
    meta = spec["meta"]
    mp4 = K.ROOT / "out" / "craftlayer" / vid / f"{vid.lower()}.mp4"
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(mp4)], capture_output=True, text=True).stdout)
    folder, direct = drive_links(vid)
    desc = meta["yt_description"].rstrip() + "\n\nSources:\n" + "\n".join(meta["sources"]) + "\n\nVoiceover is AI-generated."
    return {"Video ID": vid, "Date": meta["schedule"][:10], "Category / Topic": meta["topic"],
            "Format": f"Kinetic Engine / {spec['style']}", "Duration": f"{round(dur)}s",
            "Local Path": str(mp4.relative_to(K.ROOT)), "Google Drive Folder": folder, "Direct MP4 Download Link": direct,
            "YouTube Title": meta["yt_title"], "YouTube SEO Tags (Separated)": ", ".join(meta["yt_tags"]),
            "YouTube Best SEO Description": desc, "Instagram Viral Caption": meta["ig_caption"],
            "Instagram Hashtags": " ".join(meta["ig_hashtags"]), "Instagram Status": "Ready", "Instagram Post URL": "",
            "YouTube Status": "No channel", "YouTube Shorts URL": "", "Scheduled Time (IST)": meta["schedule"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--row", type=int)
    ap.add_argument("--status")
    ap.add_argument("--url", default="")
    ap.add_argument("--when")
    a = ap.parse_args()
    for vid in a.ids:
        rec = record(vid)
        if a.status:
            rec["Instagram Status"], rec["Instagram Post URL"] = a.status, a.url
        if a.when:
            rec["Scheduled Time (IST)"] = a.when
        if a.row:
            sheet._write("@craftlayer", f"A{a.row}:{sheet.LAST}{a.row}", [[str(rec[h]) for h in K.HEADERS]]); n = a.row
        else:
            n = sheet.upsert("@craftlayer", rec)
        print(f"{vid}: row {n}, {rec['Instagram Status']}, {rec['Scheduled Time (IST)']}")


if __name__ == "__main__":
    main()
