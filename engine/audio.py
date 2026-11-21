"""Royalty-free procedural music beds + UI sound effects, and the final mix.

Everything is synthesised with numpy, so there is no licensing question and no download.
Presets:  pulse  - minimal electronic pulse (news/explainer, sits far under the voice)
          bright - upbeat pop/lo-fi bed (hype/tutorial shorts)
          none   - voice only
"""
import json, subprocess, wave
import pathlib
import numpy as np

SR = 44100
rng = np.random.default_rng(7)


def _write(path, x):
    x = np.clip(x, -1, 1)
    if x.ndim == 1:
        x = np.stack([x, x], 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def _lp(x, cutoff):
    """one-pole low-pass, cutoff may be an array (sweeps)."""
    a = np.exp(-2 * np.pi * np.broadcast_to(cutoff, x.shape) / SR)
    y = np.empty_like(x); acc = 0.0
    for i in range(len(x)):
        acc = (1 - a[i]) * x[i] + a[i] * acc
        y[i] = acc
    return y


def _lp_fast(x, cutoff):
    # vectorised FFT low-pass for fixed cutoff (long signals)
    X = np.fft.rfft(x); f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / np.sqrt(1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x))


def _env(n, a=0.005, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / max(a, 1e-4)) * np.exp(-t / d)


def note(m):
    return 440 * 2 ** ((m - 69) / 12)


# ---------------------------------------------------------------- SFX
def sfx(kind):
    if kind == "whoosh":
        n = int(SR * 0.45); t = np.arange(n) / SR
        noise = rng.standard_normal(n)
        cut = 300 + 5000 * np.sin(np.pi * t / t[-1]) ** 2
        y = _lp(noise, cut) * np.sin(np.pi * t / t[-1]) ** 1.5
        return 0.5 * y / np.abs(y).max()
    if kind == "pop":
        n = int(SR * 0.09); t = np.arange(n) / SR
        f = 900 * np.exp(-t * 30) + 380
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.002, 0.03)
        return 0.35 * y
    if kind == "tick":
        n = int(SR * 0.025)
        y = _lp(rng.standard_normal(n), 6000) * _env(n, 0.0005, 0.006)
        return 0.25 * y / np.abs(y).max()
    if kind == "stamp":
        n = int(SR * 0.25); t = np.arange(n) / SR
        f = 140 * np.exp(-t * 12) + 55
        y = np.sin(2 * np.pi * np.cumsum(f) / SR) * _env(n, 0.001, 0.08)
        y += 0.4 * _lp(rng.standard_normal(n), 2500) * _env(n, 0.001, 0.03)
        return 0.6 * y / np.abs(y).max()
    if kind == "ding":
        n = int(SR * 0.8); t = np.arange(n) / SR
        y = (np.sin(2 * np.pi * 1318.5 * t) + 0.5 * np.sin(2 * np.pi * 1975.5 * t)) * _env(n, 0.002, 0.25)
        return 0.22 * y
    if kind == "riser":
        n = int(SR * 0.9); t = np.arange(n) / SR
        y = _lp(rng.standard_normal(n), 200 + 7000 * (t / t[-1]) ** 2) * (t / t[-1]) ** 2
        return 0.35 * y / np.abs(y).max()
    return np.zeros(1)


BANK = pathlib.Path(__file__).parent / "sfx_bank"


def _bank(pack, kind, ref):
    """Recorded/rendered takes for one cue kind from engine/sfx_bank/<pack>/<kind>_N.wav (made with earshot, see
    sfx_bank/README.md), resampled to SR and matched to the RMS of the synthesized cue so the mix balance holds."""
    import soundfile as sf
    takes = []
    for f in sorted((BANK / pack).glob(f"{kind}_*.wav")):
        x, sr = sf.read(f, always_2d=True); x = x.mean(axis=1)
        if sr != SR:
            x = np.interp(np.arange(int(len(x) * SR / sr)) * sr / SR, np.arange(len(x)), x)
        rms = np.sqrt(np.mean(x ** 2)) or 1.0
        takes.append(x * (np.sqrt(np.mean(ref ** 2)) / rms))
    return takes


def build_sfx(events, dur, out, gain=1.0, pack=None):
    track = np.zeros(int(SR * dur) + SR)
    cache, uses = {}, {}
    for e in events:
        k = e["sfx"]
        if k not in cache:
            ref = sfx(k)
            cache[k] = (_bank(pack, k, ref) if pack else []) or [ref]
        takes = cache[k]; s = takes[uses.get(k, 0) % len(takes)]; uses[k] = uses.get(k, 0) + 1
        i = int(e["t"] * SR)
        if i < 0 or i >= len(track):
            continue
        j = min(len(track), i + len(s))
        track[i:j] += s[: j - i] * gain * e.get("g", 1.0)
    _write(out, track[: int(SR * dur)])


# ---------------------------------------------------------------- MUSIC
PROG = {  # midi roots + chord intervals
    "pulse": dict(bpm=104, chords=[(50, [0, 3, 7, 10]), (46, [0, 4, 7, 11]), (53, [0, 4, 7, 9]), (48, [0, 4, 7, 10])]),
    "bright": dict(bpm=118, chords=[(45, [0, 3, 7, 10]), (41, [0, 4, 7, 11]), (48, [0, 4, 7, 14]), (43, [0, 4, 7, 9])]),
}


def build_music(preset, dur, out):
    if preset == "none":
        _write(out, np.zeros(int(SR * dur))); return
    p = PROG[preset]; beat = 60 / p["bpm"]; bar = beat * 4
    n = int(SR * (dur + 1)); mix = np.zeros(n)
    t_all = np.arange(n) / SR
    nbars = int(dur / bar) + 2
    for b in range(nbars):
        root, iv = p["chords"][b % len(p["chords"])]
        s0 = int(b * bar * SR); L = int(bar * SR)
        if s0 >= n:
            break
        L = min(L, n - s0); t = np.arange(L) / SR
        # pad: detuned saws, soft attack, filtered
        pad = np.zeros(L)
        for k in iv:
            for det in (-0.07, 0.07):
                f = note(root + 12 + k) * 2 ** (det / 12)
                pad += 2 * ((t * f) % 1) - 1
        pad = _lp_fast(pad, 900 if preset == "pulse" else 1600)
        pad *= np.minimum(1, t / 0.4) * np.minimum(1, (bar - t) / 0.15)
        mix[s0:s0 + L] += 0.045 * pad
        # bass on beats
        for q in range(4):
            i = s0 + int(q * beat * SR); m = int(beat * SR * 0.9)
            if i + m > n:
                break
            tt = np.arange(m) / SR
            mix[i:i + m] += 0.16 * np.sin(2 * np.pi * note(root) * tt) * _env(m, 0.01, 0.35)
        # arp / plucks (bright) or soft blips (pulse)
        steps = 8
        for q in range(steps):
            i = s0 + int(q * beat / 2 * SR); m = int(SR * 0.22)
            if i + m > n:
                break
            k = iv[(q * 2 + b) % len(iv)] + (12 if q % 4 == 3 else 0)
            tt = np.arange(m) / SR
            tri = 2 * np.abs(2 * ((tt * note(root + 24 + k)) % 1) - 1) - 1
            vol = 0.05 if preset == "bright" else 0.022
            mix[i:i + m] += vol * tri * _env(m, 0.002, 0.07)
        # drums
        for q in range(4):
            i = s0 + int(q * beat * SR)
            if i + int(SR * 0.3) > n:
                break
            m = int(SR * 0.3); tt = np.arange(m) / SR
            kick = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-tt * 25) + 45) / SR) * _env(m, 0.001, 0.12)
            if preset == "bright" or q % 2 == 0:
                mix[i:i + m] += (0.32 if preset == "bright" else 0.2) * kick
            if q in (1, 3):
                mm = int(SR * 0.18)
                sn = _lp_fast(rng.standard_normal(mm), 5000) * _env(mm, 0.001, 0.05)
                mix[i:i + mm] += (0.12 if preset == "bright" else 0.05) * sn / np.abs(sn).max()
            for h in (0, 0.5):
                j = i + int(h * beat * SR); mm = int(SR * 0.05)
                if j + mm > n:
                    break
                hat = np.diff(rng.standard_normal(mm + 1)) * _env(mm, 0.0005, 0.012)
                mix[j:j + mm] += (0.05 if preset == "bright" else 0.03) * hat
    mix = mix[: int(SR * dur)]
    fade = int(SR * 1.5)
    mix[-fade:] *= np.linspace(1, 0, fade)
    mix[: int(SR * 0.3)] *= np.linspace(0, 1, int(SR * 0.3))
    mix /= max(1e-6, np.abs(mix).max()) / 0.8
    st = np.stack([mix, np.roll(mix, 220)], 1)  # tiny stereo widening
    _write(out, st)


def mix_final(video, voice, music, sfxwav, out, music_db=-20, sfx_db=-8, lufs=-14):
    """voice + ducked music + sfx -> loudness-normalised AAC, video stream copied."""
    fc = (f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.0,asplit=2[v][vsc];"
          f"[2:a]volume={music_db}dB[m];"
          f"[m][vsc]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[md];"
          f"[3:a]volume={sfx_db}dB[s];"
          f"[v][md][s]amix=inputs=3:normalize=0:duration=first,"
          f"loudnorm=I={lufs}:TP=-1.5:LRA=11[a]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-i", voice, "-i", music, "-i", sfxwav,
                    "-filter_complex", fc, "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", out], check=True)
