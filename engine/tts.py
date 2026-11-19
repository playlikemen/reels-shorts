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
        for attempt in range(3):
            try:
                words = asyncio.run(_edge(text, voice, rate, pitch, mp3))
                break
            except Exception as e:  # transient websocket errors happen; retry
                if attempt == 2:
                    raise
        js.write_text(json.dumps(words))
    return str(mp3), duration(mp3), json.loads(js.read_text())


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
    return re.sub(r"[^a-z0-9%$.]", "", w.lower()).strip(".")
