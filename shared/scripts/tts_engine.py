#!/usr/bin/env python3.11
"""tts_engine.py: High-fidelity Neural Voiceover & Word-by-Word Caption Generator.

Uses Microsoft Edge Neural TTS with exact millisecond word-boundary timestamps
for Hormozi / TikTok-style kinetic karaoke captions.
"""

import sys
import os
import json
import asyncio
import ssl
import argparse
import subprocess

# Bypass SSL context issues in sandbox environment
unverified = ssl._create_unverified_context()
try:
    import edge_tts
    import edge_tts.communicate
    import edge_tts.voices
    edge_tts.communicate._SSL_CTX = unverified
    edge_tts.voices._SSL_CTX = unverified
except ImportError:
    pass

DEFAULT_VOICE = "en-US-ChristopherNeural"  # Authoritative, energetic tech narrator

def group_words_into_pages(words, max_words_per_page=3, max_gap_seconds=0.45):
    """
    Groups words into short, punchy 1-3 word pages matching TikTok/Hormozi viral standards.
    """
    pages = []
    current_page = []
    page_start = 0.0

    for idx, w in enumerate(words):
        if not current_page:
            page_start = w["start"]
            current_page.append(w)
            continue

        prev_word = current_page[-1]
        gap = w["start"] - prev_word["end"]

        # Break page if: reached word limit, long pause, or sentence punctuation
        has_punctuation = any(prev_word["word"].endswith(p) for p in [".", "?", "!", ":", ";", ","])
        if len(current_page) >= max_words_per_page or gap > max_gap_seconds or (len(current_page) >= 2 and has_punctuation):
            pages.append({
                "page_index": len(pages),
                "start": page_start,
                "end": prev_word["end"],
                "text": " ".join(item["word"] for item in current_page),
                "words": current_page
            })
            current_page = [w]
            page_start = w["start"]
        else:
            current_page.append(w)

    if current_page:
        pages.append({
            "page_index": len(pages),
            "start": page_start,
            "end": current_page[-1]["end"],
            "text": " ".join(item["word"] for item in current_page),
            "words": current_page
        })

    return pages

async def generate_speech_async(text, output_audio_path, output_json_path, voice=DEFAULT_VOICE, rate="+8%"):
    communicate = edge_tts.Communicate(text, voice=voice, rate=rate, boundary="WordBoundary")
    words = []
    
    os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
    
    with open(output_audio_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start_sec = round(chunk["offset"] / 10_000_000, 3)
                dur_sec = round(chunk["duration"] / 10_000_000, 3)
                words.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": round(start_sec + dur_sec, 3),
                    "duration": dur_sec
                })

    # Group words into TikTok-style pages
    pages = group_words_into_pages(words, max_words_per_page=3)

    # Convert audio to standard WAV for ffmpeg / chromium web audio muxing
    wav_path = output_audio_path.rsplit(".", 1)[0] + ".wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", output_audio_path,
        "-ac", "2", "-ar", "44100", wav_path
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Get total audio duration via ffprobe
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", wav_path
    ], capture_output=True, text=True)
    duration = float(probe.stdout.strip() or (words[-1]["end"] if words else 15.0))

    result = {
        "text": text,
        "voice": voice,
        "rate": rate,
        "audio_path": output_audio_path,
        "wav_path": wav_path,
        "duration": round(duration, 2),
        "total_words": len(words),
        "total_pages": len(pages),
        "words": words,
        "pages": pages
    }

    if output_json_path:
        os.makedirs(os.path.dirname(os.path.abspath(output_json_path)), exist_ok=True)
        with open(output_json_path, "w") as f:
            json.dump(result, f, indent=2)

    return result

def generate_voiceover(text, output_audio_path, output_json_path, voice=DEFAULT_VOICE, rate="+8%"):
    return asyncio.run(generate_speech_async(text, output_audio_path, output_json_path, voice, rate))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate neural voiceover and word-level captions")
    parser.add_argument("text", help="Narration text")
    parser.add_argument("output_audio", help="Path to output mp3 file")
    parser.add_argument("--json", dest="output_json", help="Path to output captions json")
    parser.add_argument("--voice", default=DEFAULT_VOICE, help="Voice name")
    parser.add_argument("--rate", default="+8%", help="Speed adjustment (+5%, +10%)")
    args = parser.parse_args()

    res = generate_voiceover(args.text, args.output_audio, args.output_json, args.voice, args.rate)
    print(f"Generated {res['duration']}s voiceover ({res['total_words']} words, {res['total_pages']} caption pages)")
