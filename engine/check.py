#!/usr/bin/env python3
"""Verify a finished video before publishing.

  python3 check.py out/x/video.mp4 [--transcribe]

Prints duration, resolution, integrated loudness, writes contact.jpg (12 frames) next to the video, and with
--transcribe runs faster-whisper so the narration can be compared with the script.
"""
import json, pathlib, re, subprocess, sys

v = pathlib.Path(sys.argv[1])
info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height,r_frame_rate",
                                  "-of", "json", str(v)], capture_output=True, text=True).stdout)
dur = float(info["format"]["duration"])
vs = [s for s in info["streams"] if s["codec_type"] == "video"][0]
loud = subprocess.run(["ffmpeg", "-i", str(v), "-af", "ebur128=framelog=quiet", "-f", "null", "-"], capture_output=True, text=True).stderr
I = re.search(r"I:\s+(-?[\d.]+) LUFS", loud)
print(f"duration {dur:.2f}s  {vs['width']}x{vs['height']} @ {vs['r_frame_rate']}  loudness {I.group(1) if I else '?'} LUFS (target -14)")
n = 12
times = [dur * (i + 0.5) / n for i in range(n)]
tiles = []
for i, t in enumerate(times):
    p = v.parent / f"_c{i:02d}.jpg"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", str(v), "-frames:v", "1", "-vf", "scale=360:-1", str(p)], check=True)
    tiles.append(p)
args = sum([["-i", str(p)] for p in tiles], [])
cols = 6
fc = "".join(f"[{i}]" for i in range(n)) + f"xstack=inputs={n}:layout=" + "|".join(
    f"{'+'.join(['w0'] * (i % cols)) or '0'}_{'+'.join(['h0'] * (i // cols)) or '0'}" for i in range(n))
subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-q:v", "3", str(v.parent / "contact.jpg")], check=True)
for p in tiles:
    p.unlink()
print("contact sheet:", v.parent / "contact.jpg", "(frames at", ", ".join(f"{t:.1f}s" for t in times) + ")")
if "--transcribe" in sys.argv:
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(v), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    segs, _ = WhisperModel("small.en", device="cpu", compute_type="int8").transcribe(np.frombuffer(raw, np.int16).astype(np.float32) / 32768)
    for s in segs:
        print(f"[{s.start:6.2f}-{s.end:6.2f}] {s.text.strip()}")
