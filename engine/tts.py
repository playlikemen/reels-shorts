"""Voice-over generation with word-level timestamps.

Backends
  edge   : Microsoft neural voices via edge-tts (free, no key, word boundaries built in)  [default]
  file   : your own recording / ElevenLabs export per scene -> timestamps via faster-whisper
Every backend returns (audio_path, duration_s, words) where words = [{"w","s","e"}] in seconds,
relative to the start of that audio file.
"""
import asyncio, hashlib, json, os, pathlib, re, subprocess

CACHE = pathlib.Path(os.environ.get("KV_CACHE", pathlib.Path.home() / ".cache" / "kinetic-video"))
CACHE.mkdir(parents=True, exist_ok=True)


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True).stdout.strip()
    return float(out)


async def _edge(text, voice, rate, pitch, out_mp3):
    import edge_tts, ssl
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if ca and os.path.exists(ca):  # sandboxes with a TLS-inspecting proxy need its CA bundle
        edge_tts.communicate._SSL_CTX = ssl.create_default_context(cafile=ca)
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    words = []
    with open(out_mp3, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                s = chunk["offset"] / 1e7
                words.append({"w": chunk["text"], "s": round(s, 3), "e": round(s + chunk["duration"] / 1e7, 3)})
    return words


def edge_tts(text, voice="en-US-AndrewNeural", rate="+0%", pitch="+0Hz"):
    key = hashlib.sha1(json.dumps([text, voice, rate, pitch]).encode()).hexdigest()[:16]
    mp3, js = CACHE / f"{key}.mp3", CACHE / f"{key}.json"
    if not (mp3.exists() and js.exists()):
        # Some voices (the Multilingual ones) return no audio for certain sentences every time.
        # The same words with the final punctuation or the commas removed usually work, and keep captions aligned.
        variants = [text, text, text.rstrip(".!?। "), text.replace(",", ""), text.rstrip(".!?। ").replace(",", ""),
                    text.replace(":", ","), text + ".."]
        for attempt, variant in enumerate(variants):
            try:
                words = asyncio.run(_edge(variant, voice, rate, pitch, mp3))
                break
            except Exception as e:  # transient websocket errors, or a sentence the voice will not read
                if attempt == len(variants) - 1:
                    raise
        js.write_text(json.dumps(words))
    return str(mp3), duration(mp3), json.loads(js.read_text())


_KOKORO = {}


def kokoro_tts(text, voice="af_heart", speed=1.2, lang="a"):
    """Kokoro-82M (Apache-2.0, runs on CPU): far more natural and lively than edge voices. English ("a"/"b") works
    without espeak-ng; Hindi ("h") needs espeak-ng, which this host cannot load (glibc 2.28)."""
    key = hashlib.sha1(json.dumps(["kokoro", text, voice, speed, lang]).encode()).hexdigest()[:16]
    wav, js = CACHE / f"{key}.wav", CACHE / f"{key}.json"
    if not (wav.exists() and js.exists()):
        import numpy as np, soundfile as sf
        from kokoro import KPipeline
        if lang not in _KOKORO:
            _KOKORO[lang] = KPipeline(lang_code=lang, repo_id="hexgrad/Kokoro-82M")
        parts, words, off = [], [], 0.0
        for r in _KOKORO[lang](text, voice=voice, speed=speed):
            a = r.audio.numpy(); parts.append(a)
            for tk in (r.tokens or []):
                if tk.start_ts is None or not re.search(r"\w", tk.text):
                    continue
                if words and not words[-1]["ws"] and re.match(r"^['’]?\w", tk.text) and tk.text[0] in "'’":
                    words[-1]["w"] += tk.text; words[-1]["e"] = round(off + (tk.end_ts or tk.start_ts), 3)   # "ca" + "n't"
                else:
                    words.append({"w": tk.text, "s": round(off + tk.start_ts, 3), "e": round(off + (tk.end_ts or tk.start_ts), 3)})
                words[-1]["ws"] = bool(tk.whitespace)
            off += len(a) / 24000
        sf.write(wav, np.concatenate(parts), 24000)
        js.write_text(json.dumps([{k: w[k] for k in ("w", "s", "e")} for w in words]))
    return str(wav), duration(wav), json.loads(js.read_text())


def align_file(path, model="small.en"):
    """Word timestamps for any voice file (ElevenLabs, a mic recording, ...)."""
    import numpy as np
    from faster_whisper import WhisperModel
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    audio = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    segs, _ = WhisperModel(model, device="cpu", compute_type="int8").transcribe(audio, word_timestamps=True)
    words = [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)} for s in segs for w in s.words]
    return str(path), duration(path), words


def norm(w):
    return re.sub(r"[^a-z0-9%$.\u0900-\u097f]", "", w.lower()).strip(".").strip("\u0964\u0965")
