#!/usr/bin/env python3
"""spec.json -> finished MP4 (+ .srt captions + thumbnail still).

  python3 build.py spec.json --out out/my_video            # full render
  python3 build.py spec.json --out out/x --stills 2,9,15   # also save preview stills at those seconds
  python3 build.py spec.json --out out/x --stills-only --stills 2,9   # look before the full render

Pipeline: per-scene TTS (word timestamps) -> cue words resolved to seconds -> deterministic HTML render
(Playwright, frame by frame) -> procedural music + SFX -> ducked, loudness-normalised mix.
"""
import argparse, copy, json, math, os, pathlib, re, subprocess, sys, wave
import numpy as np

HERE = pathlib.Path(__file__).parent
sys.path.insert(0, str(HERE))
import tts as T
import audio as AU

FORMATS = {"short": (720, 1280), "long": (1280, 720), "square": (1080, 1080)}


def toks(s):
    return [T.norm(w) for w in re.findall(r"\S+", s) if T.norm(w)]


def find_phrase(words, phrase, start=0):
    """index of first word of `phrase` in scene words (normalised, prefix-tolerant). 'phrase#2' = 2nd hit."""
    nth = 1
    if "#" in phrase:
        phrase, k = phrase.rsplit("#", 1); nth = int(k)
    p = toks(phrase)
    W = [T.norm(w["w"]) for w in words]
    def eq(a, b):  # a = spoken word, b = cue token; cue may be a prefix ("octoverse" ~ "octoverse's")
        return a == b or (len(b) >= 4 and a.startswith(b) and len(a) - len(b) <= 3)
    hits = 0
    for i in range(len(W)):
        if all(i + j < len(W) and eq(W[i + j], p[j]) for j in range(len(p))):
            hits += 1
            if hits == nth:
                return i
    return None


def resolve(obj, words, off, floor, lead, warn):
    """walk element tree; replace cue keys with absolute times."""
    if isinstance(obj, list):
        for x in obj:
            resolve(x, words, off, floor, lead, warn)
        return
    if not isinstance(obj, dict):
        return
    for key, out in (("at", "tin"), ("moveAt", "moveTin"), ("vAt", "vAt"), ("outAt", "out"), ("fillAt", "fillTin"), ("labelAt", "labelTin")):
        if key in obj and obj[key] is not None:
            cue = obj[key]
            if isinstance(cue, (int, float)):
                t = off + float(cue)
            else:
                i = find_phrase(words, str(cue))
                if i is None:
                    warn.append(f"cue '{cue}' not found in: {' '.join(w['w'] for w in words)}")
                    t = None
                else:
                    t = off + words[i]["s"] - lead
            if t is not None:
                obj[out] = round(max(floor, t), 3)
            if key != out:
                obj.pop(key, None)
    for v in obj.values():
        if isinstance(v, (list, dict)):
            resolve(v, words, off, floor, lead, warn)


def caption_times(cap, words, off):
    """map caption segment words onto spoken words (sequential, fuzzy)."""
    W = [T.norm(w["w"]) for w in words]
    j = 0
    for seg in cap:
        out = []
        for raw in re.findall(r"\S+", seg["text"]):
            n = T.norm(raw)
            hit = None
            for k in range(j, min(len(W), j + 8)):
                if n and (W[k] == n or W[k].startswith(n) or n.startswith(W[k])):
                    hit = k; break
            if hit is None:
                t = off + (words[j]["s"] if j < len(words) else (words[-1]["e"] if words else 0))
            else:
                t = off + words[hit]["s"]; j = hit + 1
            out.append({"w": raw, "t": round(t, 3)})
        seg["ws"] = out


def auto_caption(say):
    parts = re.split(r"(?<=[.!?,])\s+", say.strip())
    cap = []
    for i, p in enumerate(parts):
        ws = p.split()
        while ws:
            chunk, ws = ws[:6], ws[6:]
            cap.append({"text": " ".join(chunk), "size": "l" if len(cap) % 2 else "m", "pos": "top" if len(cap) < 2 else "bottom"})
    return cap


def srt(words_abs, path):
    def ts(x):
        h, r = divmod(x, 3600); m, s = divmod(r, 60)
        return f"{int(h):02}:{int(m):02}:{int(s):02},{int((s % 1) * 1000):03}"
    lines, cur = [], []
    for w in words_abs:
        cur.append(w)
        if len(cur) >= 7 or re.search(r"[.!?]$", w["w"]):
            lines.append(cur); cur = []
    if cur:
        lines.append(cur)
    with open(path, "w") as f:
        for i, l in enumerate(lines, 1):
            f.write(f"{i}\n{ts(l[0]['s'])} --> {ts(l[-1]['e'] + 0.05)}\n{' '.join(w['w'] for w in l)}\n\n")


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "44100", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec"); ap.add_argument("--out", default="out/video")
    ap.add_argument("--stills", default=""); ap.add_argument("--stills-only", action="store_true")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--only", default="", help="comma list of scene indexes to re-render (others reused)")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    W, H = (spec["W"], spec["H"]) if "W" in spec else FORMATS[spec.get("format", "short")]
    v = spec.get("voice", {})
    gap, lead_in, tail = spec.get("gap", 0.16), spec.get("lead_in", 0.15), spec.get("tail", 1.4)

    # 1) voice per scene
    clips = []
    for i, sc in enumerate(spec["scenes"]):
        if sc.get("voice_file"):
            p, d, words = T.align_file(sc["voice_file"])
        elif v.get("engine", "edge") == "edge":
            p, d, words = T.edge_tts(sc["say"], v.get("name", "en-US-AndrewNeural"), v.get("rate", "+0%"), v.get("pitch", "+0Hz"))
        else:
            raise SystemExit("unknown voice engine")
        clips.append((p, d, words))
        print(f"voice {i:02d}: {d:5.2f}s  {sc['say'][:60]}")

    # 2) timeline
    offs, t = [], lead_in
    for (p, d, words), sc in zip(clips, spec["scenes"]):
        offs.append(t); t += d + sc.get("gap_after", gap)
    duration = round(offs[-1] + clips[-1][1] + tail, 3)
    sr = 44100
    voice = np.zeros(int(sr * duration) + sr)
    words_abs = []
    for (p, d, words), o in zip(clips, offs):
        x = decode(p); i = int(o * sr); voice[i:i + len(x)] += x[: len(voice) - i]
        words_abs += [{"w": w["w"], "s": o + w["s"], "e": o + w["e"]} for w in words]
    voice = voice[: int(sr * duration)]
    with wave.open(str(out / "voice.wav"), "wb") as wv:
        wv.setnchannels(1); wv.setsampwidth(2); wv.setframerate(sr)
        wv.writeframes((np.clip(voice, -1, 1) * 32767).astype(np.int16).tobytes())
    srt(words_abs, out / "captions.srt")

    # 3) resolve cues
    rs = copy.deepcopy(spec)
    rs.update({"W": W, "H": H, "duration": duration, "fps": spec.get("fps", 30), "scale": spec.get("scale", 1080 / min(W, H) if min(W, H) < 1080 else 1)})
    warns = []
    prev_ch = None
    for i, (sc, (p, d, words), o) in enumerate(zip(rs["scenes"], clips, offs)):
        sc["t0"] = 0.0 if i == 0 else round(o - spec.get("pre", 0.12), 3)
        sc["vo"] = round(o, 3); sc["vd"] = round(d, 3)
        ch = sc.get("chapter", prev_ch)
        changed = ch != prev_ch
        prev_ch = ch
        floor = -1.0 if i == 0 else sc["t0"] + (0.28 if changed else 0.06)   # scene 0 may start mid-animation (hook frame)
        resolve(sc.get("els", []), words, o, floor, spec.get("lead", 0.06), warns)
        if rs["style"] == "clean":
            cap = sc["cap"] if "cap" in sc else auto_caption(sc["say"])   # "cap": [] = no captions
            caption_times(cap, words, o); sc["cap"] = cap
            resolve(sc.get("vis", []), words, o, floor, spec.get("lead", 0.06), warns)
    for w in warns:
        print("WARN", w)
    if a.stills:
        rs["stills"] = [float(x) for x in a.stills.split(",")]
    rs["stillsOnly"] = a.stills_only
    if a.only:
        rs["onlyScenes"] = [int(x) for x in a.only.split(",")]
    json.dump(rs, open(out / "resolved.json", "w"), indent=1)

    # 4) render frames
    subprocess.run(["node", str(HERE / "render.cjs"), str(out / "resolved.json"), str(out), str(a.workers)], check=True)
    if a.stills_only:
        print("stills written to", out); return

    # 5) audio + mix
    events = json.load(open(out / "events.json"))
    AU.build_music(spec.get("music", "pulse"), duration, out / "music.wav")
    AU.build_sfx(events if spec.get("sfx", True) else [], duration, out / "sfx.wav")
    final = out / (spec.get("slug", "video") + ".mp4")
    AU.mix_final(str(out / "video_silent.mp4"), str(out / "voice.wav"), str(out / "music.wav"), str(out / "sfx.wav"), str(final),
                 music_db=spec.get("music_db", -21), sfx_db=spec.get("sfx_db", -9), lufs=spec.get("lufs", -14))
    # thumbnail: frame at spec.thumb (s) or 1.2s
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(spec.get("thumb", 1.6)), "-i", str(final), "-frames:v", "1", "-q:v", "2", str(out / "thumb.jpg")], check=True)
    print("DONE", final, f"{duration:.1f}s")


if __name__ == "__main__":
    main()
