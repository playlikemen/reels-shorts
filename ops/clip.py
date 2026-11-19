"""Turn a phone recording into a ready-to-post Reel: upright 1080x1920, captions, hook text, -14 LUFS.

  python3.11 ops/clip.py inbox/campusloop/day1.mp4 --brand campusloop --id CL-201 \
      --hook "I built an app only my college can use" --topic "Founder / why I built it" \
      --caption "Day 1 of building CampusLoop in my hostel room." --schedule "2026-11-21 19:30"

  --rotate 90|180|270   turn a sideways recording upright (clockwise degrees)
  --trim 2.5-41         keep only this part, in seconds
  --no-captions         skip speech captions
  --no-sync             render and verify only; no Drive upload, no sheet row

  --language en|hi      speech language for captions (default: detect)

Captions come from faster-whisper word timings, three words at a time, set in Montserrat (system font; Hindi
falls back to Lohit Devanagari). Hindi speech is captioned in Devanagari. Watch the output once before syncing
and fix wrong words with --fix "wrong=right,wrong2=right2". For mixed Hindi and English, --no-captions and
captions added in the Instagram editor are usually cleaner.
"""
import argparse, os, re, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import config as K
from make import verify

ROTATE = {"90": "transpose=1,", "180": "transpose=1,transpose=1,", "270": "transpose=2,", "": ""}


def ass_time(t):
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def words(src, model_size, language):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(src), word_timestamps=True, vad_filter=True, language=language or None)
    return [(w.start, w.end, w.word.strip()) for s in segments for w in (s.words or []) if w.word.strip()]


def write_ass(path, ws, hook, accent, fixes):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Cap,Montserrat,74,&H00FFFFFF,&H00000000,&H00000000,1,1,7,0,2,70,70,430
Style: Hook,Montserrat,62,&H00FFFFFF,{accent},{accent},1,3,18,0,8,70,70,260

[Events]
Format: Layer, Start, End, Style, Text
"""
    lines = []
    if hook:
        lines.append(f"Dialogue: 1,{ass_time(0)},{ass_time(3.2)},Hook,{hook}")
    for i in range(0, len(ws), 3):
        chunk = ws[i:i + 3]
        text = " ".join(fixes.get(w[2].lower().strip(".,!?"), w[2]) for w in chunk)
        end = min(chunk[-1][1] + 0.15, ws[i + 3][0] if i + 3 < len(ws) else chunk[-1][1] + 0.6)
        lines.append(f"Dialogue: 0,{ass_time(chunk[0][0])},{ass_time(end)},Cap,{text.upper()}")
    open(path, "w").write(head + "\n".join(lines) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src"); ap.add_argument("--brand", required=True); ap.add_argument("--id", required=True)
    ap.add_argument("--hook", default=""); ap.add_argument("--topic", default="Founder clip"); ap.add_argument("--caption", default="")
    ap.add_argument("--schedule", default=""); ap.add_argument("--rotate", default="", choices=list(ROTATE))
    ap.add_argument("--trim", default=""); ap.add_argument("--fix", default=""); ap.add_argument("--model", default="small")
    ap.add_argument("--language", default="", help="en or hi; empty = detect")
    ap.add_argument("--no-captions", action="store_true"); ap.add_argument("--no-sync", action="store_true")
    a = ap.parse_args()
    b = K.brand(a.brand)
    out = K.ROOT / "out" / a.brand / a.id
    out.mkdir(parents=True, exist_ok=True)
    cut, mp4, ass = out / "cut.mp4", out / f"{a.id.lower()}.mp4", out / "captions.ass"

    # 1. Upright, 1080x1920 (crop to fill), 30 fps, trimmed. Captions are timed against this file.
    trim = []
    if a.trim:
        start, end = a.trim.split("-")
        trim = ["-ss", start, "-to", end]
    subprocess.run(["ffmpeg", "-v", "error", "-y", *trim, "-i", a.src,
                    "-vf", f"{ROTATE[a.rotate]}scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast", "-c:a", "aac", "-b:a", "192k", str(cut)], check=True)

    # 2. Captions and hook
    ws = [] if a.no_captions else words(cut, a.model, a.language)
    fixes = dict(p.split("=", 1) for p in a.fix.split(",") if "=" in p)
    accent = b["styles"]["clean"]["theme"].get("accent", "#6A3DE8").lstrip("#")
    write_ass(ass, ws, a.hook, f"&H00{accent[4:6]}{accent[2:4]}{accent[0:2]}".upper(), {k.lower(): v for k, v in fixes.items()})
    print(f"captions: {len(ws)} words ->", ass)

    # 3. Burn captions, set loudness to -14 LUFS
    sub = str(ass).replace(":", r"\:")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(cut), "-vf", f"subtitles={sub}",
                    "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:v", "libx264", "-crf", "20", "-preset", "medium",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(mp4)], check=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", str(mp4), "-frames:v", "1", str(out / "thumb.jpg")], check=True)

    p, problems = verify(mp4, "short")
    print("verify:", p)
    if problems:
        raise SystemExit("NOT OK: " + "; ".join(problems))
    if a.no_sync:
        print("OK (not synced)", mp4); return
    if not (a.caption and re.fullmatch(r"\d{4}-\d\d-\d\d \d\d:\d\d", a.schedule)):
        raise SystemExit('to sync, pass --caption "..." and --schedule "YYYY-MM-DD HH:MM" (IST)')

    import drive, sheet
    d = drive.archive(f"{a.schedule[:10]}-{a.id}-{re.sub(r'[^a-z0-9]+', '-', a.topic.lower()).strip('-')[:40]}", mp4)
    row = sheet.upsert(b["sheet_tab"], {
        "Video ID": a.id, "Date": a.schedule[:10], "Category / Topic": a.topic, "Format": "Phone clip",
        "Duration": f"{round(p['duration'])}s", "Local Path": str(mp4.relative_to(K.ROOT)),
        "Google Drive Folder": d["folder_link"], "Direct MP4 Download Link": d["direct_link"],
        "YouTube Title": "", "YouTube SEO Tags (Separated)": "", "YouTube Best SEO Description": "",
        "Instagram Viral Caption": a.caption, "Instagram Hashtags": " ".join(b["hashtags"]),
        "Instagram Status": "Ready", "Instagram Post URL": "",
        "YouTube Status": "Ready" if b.get("youtube") else "No channel", "YouTube Shorts URL": "",
        "Scheduled Time (IST)": a.schedule,
    })
    print(f"OK {a.id}: sheet row {row} in {b['sheet_tab']}, scheduled {a.schedule} IST")


if __name__ == "__main__":
    main()
