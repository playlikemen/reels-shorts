#!/usr/bin/env python3
"""
Studio Sound FX Synthesizer
Generates studio-grade sound effects for Linux terminal motion graphics using pure Python math & wave.
Guarantees 100% offline determinism, zero external dependencies, zero latency.
"""

import os
import wave
import math
import struct
import random

AUDIO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "audio")

def write_wav(filepath, duration_sec, sample_rate=44100, func=None):
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    n_samples = int(duration_sec * sample_rate)
    with wave.open(filepath, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            t = i / sample_rate
            val = func(t, duration_sec)
            val = max(-1.0, min(1.0, val))
            sample = int(val * 32767)
            frames.extend(struct.pack("<h", sample))
        wf.writeframes(frames)
    return filepath

def generate_keyboard_clack(t, d):
    """Mechanical key switch click: damped dual-tone + noise burst"""
    if t > 0.04:
        return 0.0
    tone = math.sin(2 * math.pi * 2200 * t) * 0.4 + math.sin(2 * math.pi * 3800 * t) * 0.3
    noise = (random.random() * 2 - 1) * 0.3
    decay = math.exp(-120 * t)
    return (tone + noise) * decay

def generate_terminal_enter(t, d):
    """Clean retro computer bell / enter trigger"""
    freq = 1050
    harm = math.sin(2 * math.pi * freq * 2 * t) * 0.25
    fundamental = math.sin(2 * math.pi * freq * t) * 0.75
    decay = math.exp(-22 * t)
    return (fundamental + harm) * decay

def generate_sub_whoosh(t, d):
    """Sub-bass drop + gentle air whoosh for camera zoom punch / scene cuts"""
    progress = t / d
    freq = 140 * (1 - progress) + 38 * progress
    sub = math.sin(2 * math.pi * freq * t) * 0.8
    air = (random.random() * 2 - 1) * 0.15 * math.sin(math.pi * progress)
    env = math.sin(math.pi * progress)
    return (sub + air) * env

def generate_chime_success(t, d):
    """Two-tone major third melodic success chime (E5 -> G#5)"""
    if t < 0.08:
        freq = 659.25  # E5
        decay = math.exp(-10 * t)
    else:
        freq = 830.61  # G#5
        decay = math.exp(-12 * (t - 0.08))
    tone = math.sin(2 * math.pi * freq * t) * 0.8 + math.sin(2 * math.pi * freq * 2 * t) * 0.2
    return tone * decay

def generate_alert_warning(t, d):
    """Dissonant low alert buzz for dangerous commands / error states"""
    f1 = 180
    f2 = 240
    tone = math.sin(2 * math.pi * f1 * t) * 0.5 + math.sin(2 * math.pi * f2 * t) * 0.5
    square = 0.8 if tone > 0 else -0.8
    env = math.sin(math.pi * (t / d))
    return square * env * 0.6

def generate_pop_caption(t, d):
    """High pitch micro pop for kinetic caption word highlights"""
    if t > 0.035:
        return 0.0
    freq = 1200 - (t / 0.035) * 400
    decay = math.exp(-140 * t)
    return math.sin(2 * math.pi * freq * t) * decay * 0.5

def build_all_sfx():
    """Build all studio SFX into shared/assets/audio/"""
    print("[sfx] Synthesizing studio sound effects library...")
    write_wav(os.path.join(AUDIO_DIR, "keyboard_clack.wav"), 0.05, func=generate_keyboard_clack)
    write_wav(os.path.join(AUDIO_DIR, "terminal_enter.wav"), 0.15, func=generate_terminal_enter)
    write_wav(os.path.join(AUDIO_DIR, "whoosh_sub.wav"), 0.40, func=generate_sub_whoosh)
    write_wav(os.path.join(AUDIO_DIR, "chime_success.wav"), 0.45, func=generate_chime_success)
    write_wav(os.path.join(AUDIO_DIR, "alert_warning.wav"), 0.25, func=generate_alert_warning)
    write_wav(os.path.join(AUDIO_DIR, "pop_caption.wav"), 0.04, func=generate_pop_caption)
    print(f"[sfx] Studio sound effects library ready in {AUDIO_DIR}")

if __name__ == "__main__":
    build_all_sfx()
