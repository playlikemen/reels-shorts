#!/usr/bin/env python3.11
"""Build one video from its spec, verify it, archive it to Drive and record it in the sheet.

  python3.11 ops/make.py specs/stackshade/SS-101.json --stills 0.2,4,9,15   # preview stills only (seconds)
  python3.11 ops/make.py specs/stackshade/SS-101.json                       # render, check, Drive, sheet
  python3.11 ops/make.py specs/stackshade/SS-101.json --no-sync             # render and check only
  python3.11 ops/make.py specs/stackshade/SS-101.json --only 0,3            # re-render those scenes (same narration)
  python3.11 ops/make.py specs/stackshade/SS-101.json --sync-only           # Drive + sheet for an existing render

The spec is an engine spec (see skills/kinetic-explainer-video/SKILL.md) plus a "meta" block (see SKILL.md).
Brand defaults from brands/<brand>/brand.json (voice, music, colours) fill anything the spec leaves out.
"""
import argparse, json, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import config as K

META_REQUIRED = ["id", "brand", "topic", "yt_title", "yt_tags", "yt_description", "ig_caption", "ig_hashtags", "sources", "schedule"]


def merged_spec(spec):
    b = K.brand(spec["meta"]["brand"])
    out = dict(spec)
    out.setdefault("voice", b["voice"])
    for k, v in b["styles"][spec["style"]].items():
        if k == "theme":
            out["theme"] = {**v, **spec.get("theme", {})}
        else:
            out.setdefault(k, v)
    out["slug"] = spec["meta"]["id"].lower()
    out.setdefault("format", "short")
    return out


def probe(mp4):
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
                                      "-of", "json", str(mp4)], capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), {})
    loud = subprocess.run(["ffmpeg", "-i", str(mp4), "-af", "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)
    return {"w": v["width"], "h": v["height"], "fps": v["r_frame_rate"], "vcodec": v["codec_name"], "acodec": a.get("codec_name"),
            "duration": float(info["format"]["duration"]), "size": int(info["format"]["size"]), "lufs": float(m[-1]) if m else None}


def verify(mp4, fmt):
    p = probe(mp4)
    want = {"short": (1080, 1920), "long": (1920, 1080)}.get(fmt)
    problems = []
    if want and (p["w"], p["h"]) != want: problems.append(f"resolution {p['w']}x{p['h']}, want {want[0]}x{want[1]}")
    if p["fps"] != "30/1": problems.append(f"frame rate {p['fps']}, want 30")
    if p["vcodec"] != "h264" or p["acodec"] != "aac": problems.append(f"codecs {p['vcodec']}/{p['acodec']}, want h264/aac")
    if p["size"] < K.MIN_MP4_BYTES: problems.append(f"file is only {p['size']} bytes")
    if fmt == "short" and not 15 <= p["duration"] <= 90: problems.append(f"duration {p['duration']:.1f}s outside 15-90s")
    if p["lufs"] is None or abs(p["lufs"] + 14) > 1.5: problems.append(f"loudness {p['lufs']} LUFS, want about -14")
    return p, problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--stills", default=""); ap.add_argument("--only", default="")
    ap.add_argument("--no-sync", action="store_true"); ap.add_argument("--sync-only", action="store_true")
    ap.add_argument("--workers", type=int, default=min(8, os.cpu_count() or 2))
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    meta = spec.get("meta") or {}
    missing = [k for k in META_REQUIRED if not meta.get(k)]
    if missing:
        raise SystemExit(f"spec meta is missing: {', '.join(missing)}")
    b = K.brand(meta["brand"])
    out = K.ROOT / "out" / meta["brand"] / meta["id"]
    out.mkdir(parents=True, exist_ok=True)
    build = merged_spec(spec)
    json.dump(build, open(out / "spec.build.json", "w"), indent=1)
    mp4 = out / f"{build['slug']}.mp4"

    if not a.sync_only:
        cmd = [sys.executable, str(K.ROOT / "engine" / "build.py"), str(out / "spec.build.json"), "--out", str(out), "--workers", str(a.workers)]
        if a.stills: cmd += ["--stills", a.stills, "--stills-only"]
        if a.only: cmd += ["--only", a.only]
        log = subprocess.run(cmd, capture_output=True, text=True)
        print(log.stdout[-3000:]); print(log.stderr[-2000:], file=sys.stderr)
        if log.returncode != 0:
            raise SystemExit("build failed")
        if "WARN" in log.stdout:
            raise SystemExit("fix every WARN (a cue phrase was not found in the narration) before going on")
        if a.stills:
            print("stills in", out); return
        subprocess.run([sys.executable, str(K.ROOT / "engine" / "check.py"), str(mp4)], check=True)

    p, problems = verify(mp4, build["format"])
    print("verify:", p)
    if problems:
        raise SystemExit("NOT OK: " + "; ".join(problems))
    if a.no_sync:
        print("OK (not synced)", mp4); return

    import drive, sheet
    d = drive.archive(f"{meta['schedule'][:10]}-{meta['id']}-{re.sub(r'[^a-z0-9]+', '-', meta['topic'].lower()).strip('-')[:40]}", mp4)
    description = meta["yt_description"].rstrip() + "\n\nSources:\n" + "\n".join(meta["sources"]) + "\n\nVoiceover is AI-generated."
    row = sheet.upsert(b["sheet_tab"], {
        "Video ID": meta["id"], "Date": meta["schedule"][:10], "Category / Topic": meta["topic"],
        "Format": f"Kinetic Engine / {build['style']}", "Duration": f"{round(p['duration'])}s",
        "Local Path": str(mp4.relative_to(K.ROOT)), "Google Drive Folder": d["folder_link"], "Direct MP4 Download Link": d["direct_link"],
        "YouTube Title": meta["yt_title"], "YouTube SEO Tags (Separated)": ", ".join(meta["yt_tags"]),
        "YouTube Best SEO Description": description, "Instagram Viral Caption": meta["ig_caption"],
        "Instagram Hashtags": " ".join(meta["ig_hashtags"]), "Instagram Status": "Ready", "Instagram Post URL": "",
        "YouTube Status": "Ready" if b.get("youtube") else "No channel", "YouTube Shorts URL": "",
        "Scheduled Time (IST)": meta["schedule"],
    })
    print(f"OK {meta['id']}: sheet row {row} in {b['sheet_tab']}, Drive {d['folder_link']}, scheduled {meta['schedule']} IST")


if __name__ == "__main__":
    main()
