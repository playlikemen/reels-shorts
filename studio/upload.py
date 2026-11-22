"""Add an uploaded video as a new reel: checks, normalise, thumbnail, Drive, Sheet row, optional publish.

  python3.11 -m studio.upload '<json params>'      # run by the studio's "upload" job; params come from /api/upload

Params: file (name under <state>/uploads/), brand, lang (EN/HI or ''), topic, caption, hashtags, yt_title, yt_desc,
after (draft | schedule | next | now), when (YYYY-MM-DD HH:MM for schedule).

Steps
1. next id for the brand: <prefix>-U<nnn>[-<LANG>], e.g. CR-U001-EN (uploads never collide with rendered ids)
2. move the file to out/<brand>/<ID>/<id>.mp4 (server-chosen name)
3. ffprobe: must be a video of at most 90 s. If it is not 1080x1920 h264/aac at 30 fps and about -14 LUFS, it is
   re-encoded (scaled and padded to 1080x1920, loudness-normalised) with ffmpeg
4. thumb.jpg  5. Drive (ops/drive.archive)  6. studio row (Ready for schedule/next/now, Hold for draft), then the Sheet mirror
7. after=now: posted at once through studio.publish_job (the scheduler lock and code path)
"""
import json, re, shutil, subprocess, sys

from . import ROOT, STATE
from . import store as S
from . import sync as Y
import config as K

MAX_SECONDS = 90
AFTER = ("draft", "schedule", "next", "now")


class UploadError(Exception):
    pass


def next_id(brand_key, lang="", db=None):
    """<prefix>-U<nnn>[-LANG], one more than any upload id in the store or under out/<brand>/."""
    db = db or S.connect()
    prefix = K.brand(brand_key)["id_prefix"]
    pat = re.compile(rf"^{re.escape(prefix)}-U(\d{{3,4}})(-[A-Z]{{2}})?$")
    seen = [r["video_id"] for r in db.execute("SELECT video_id FROM reels")]
    d = ROOT / "out" / brand_key
    if d.is_dir():
        seen += [p.name for p in d.iterdir()]
    n = max([int(m.group(1)) for m in map(pat.match, seen) if m] or [0]) + 1
    return f"{prefix}-U{n:03d}" + (f"-{lang.upper()}" if lang else "")


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                          "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate",
                          "-of", "json", str(path)], capture_output=True, text=True)
    try:
        info = json.loads(out.stdout or "{}")
    except ValueError:
        info = {}
    streams = info.get("streams") or []
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not v or "format" not in info:
        raise UploadError("this file is not a video ffprobe can read")
    a = next((s for s in streams if s.get("codec_type") == "audio"), {})
    p = {"w": v.get("width"), "h": v.get("height"), "fps": v.get("r_frame_rate"), "vcodec": v.get("codec_name"),
         "acodec": a.get("codec_name"), "duration": float(info["format"].get("duration") or 0), "lufs": None}
    if a:
        loud = subprocess.run(["ffmpeg", "-i", str(path), "-af", "ebur128=framelog=quiet", "-f", "null", "-"],
                              capture_output=True, text=True).stderr
        m = re.findall(r"I:\s+(-?[\d.]+) LUFS", loud)
        p["lufs"] = float(m[-1]) if m else None
    return p


def problems(p):
    out = []
    if (p["w"], p["h"]) != (1080, 1920):
        out.append(f"resolution {p['w']}x{p['h']}")
    if p["fps"] != "30/1":
        out.append(f"frame rate {p['fps']}")
    if p["vcodec"] != "h264" or p["acodec"] != "aac":
        out.append(f"codecs {p['vcodec']}/{p['acodec']}")
    if p["acodec"] and (p["lufs"] is None or abs(p["lufs"] + 14) > 1.5):
        out.append(f"loudness {p['lufs']} LUFS")
    return out


def normalise(src, dst, has_audio):
    vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,fps=30,format=yuv420p"
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(src)]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    cmd += ["-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0", "-vf", vf, "-c:v", "libx264", "-preset", "medium",
            "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart"]
    if has_audio:
        cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    subprocess.run(cmd + [str(dst)], check=True, capture_output=True, timeout=1800)


def thumb(mp4, dst, duration):
    t = min(1.0, max(0.0, duration / 3))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.2f}", "-i", str(mp4), "-frames:v", "1", "-q:v", "3", str(dst)],
                   check=True, capture_output=True, timeout=120)


def validate(params):
    """Check the form fields; returns a cleaned dict. Raises UploadError."""
    b = {x["key"]: x for x in K.brands()}.get(params.get("brand"))
    if not b:
        raise UploadError("pick a channel")
    after = params.get("after", "draft")
    if after not in AFTER:
        raise UploadError(f"after must be one of {', '.join(AFTER)}")
    if after == "schedule" and not Y.TIME_RE.match(params.get("when") or ""):
        raise UploadError("schedule needs a time like 2026-12-01 19:30")
    lang = (params.get("lang") or "").strip().upper()
    if lang and not re.match(r"^[A-Z]{2}$", lang):
        raise UploadError("language: two letters such as EN or HI")
    topic = str(params.get("topic") or "").strip()
    if not 2 <= len(topic) <= 200:
        raise UploadError("topic: 2 to 200 characters")
    caption = str(params.get("caption") or "").strip()
    if len(caption) > 2200:
        raise UploadError("an Instagram caption is at most 2200 characters")
    if after != "draft" and not caption:
        raise UploadError("write a caption first (or save it as a draft)")
    return {"brand": b["key"], "after": after, "when": params.get("when") or "", "lang": lang, "topic": topic,
            "caption": caption, "hashtags": str(params.get("hashtags") or "").strip()[:600],
            "yt_title": str(params.get("yt_title") or "").strip()[:100], "yt_desc": str(params.get("yt_desc") or "").strip()[:5000],
            "file": params.get("file", "")}


def run(params, db=None, archive=None, upsert=None, publish=None):
    """The upload job. archive/upsert/publish are injectable for tests."""
    import drive
    from . import publish_job
    archive = archive or drive.archive
    upsert = upsert or (lambda tab, rec: Y.upsert_local(tab, rec, who=params.get("who", "owner"), db=db))
    db = db or S.connect()
    p = validate(params)
    src = STATE / "uploads" / p["file"]
    if not src.exists():
        raise UploadError("the uploaded file is gone; upload it again")
    b = K.brand(p["brand"])
    info = probe(src)
    if info["duration"] > MAX_SECONDS:
        raise UploadError(f"the video is {info['duration']:.0f} s; reels here are at most {MAX_SECONDS} s")
    vid = next_id(p["brand"], p["lang"], db)
    out = ROOT / "out" / p["brand"] / vid
    out.mkdir(parents=True, exist_ok=False)
    mp4 = out / f"{vid.lower()}.mp4"
    print(f"{vid}: {info['w']}x{info['h']} {info['vcodec']}/{info['acodec']} {info['duration']:.1f}s {info['lufs']} LUFS", flush=True)
    bad = problems(info)
    if bad:
        print("normalising (" + ", ".join(bad) + ") to 1080x1920 h264/aac 30 fps -14 LUFS", flush=True)
        normalise(src, mp4, bool(info["acodec"]))
        src.unlink()
        info = probe(mp4)
    else:
        shutil.move(str(src), mp4)
    thumb(mp4, out / "thumb.jpg", info["duration"])
    print("thumbnail written", flush=True)
    if mp4.stat().st_size < K.MIN_MP4_BYTES:
        raise UploadError("the video is under 100 KB after processing")
    links = archive(vid, mp4)
    print("Drive:", links["folder_link"], flush=True)
    if p["after"] == "draft":
        when, status = (p["when"] if Y.TIME_RE.match(p["when"]) else ""), "Hold"
    elif p["after"] == "schedule":
        when, status = p["when"], "Ready"
    elif p["after"] == "next":
        when, status = Y.next_free_slot(p["brand"], db=db), "Ready"
    else:
        when, status = Y.ist_now(), "Ready"
    rec = {"Video ID": vid, "Date": when[:10], "Category / Topic": p["topic"], "Format": "Upload (vertical short)",
           "Duration": f"{info['duration']:.0f}s", "Local Path": str(mp4.relative_to(ROOT)),
           "Google Drive Folder": links["folder_link"], "Direct MP4 Download Link": links["direct_link"],
           "YouTube Title": p["yt_title"], "YouTube SEO Tags (Separated)": "", "YouTube Best SEO Description": p["yt_desc"],
           "Instagram Viral Caption": p["caption"], "Instagram Hashtags": p["hashtags"], "Instagram Status": status,
           "Instagram Post URL": "", "YouTube Status": status if b.get("youtube") else "No channel",
           "YouTube Shorts URL": "", "Scheduled Time (IST)": when}
    if p["after"] == "now":
        rec["Instagram Status"] = "Hold"       # publish_job flips it; cron must not race the button for it
        if b.get("youtube"):
            rec["YouTube Status"] = "Hold"
    upsert(b["sheet_tab"], rec)
    print(f"Sheet row written in {b['sheet_tab']}: {rec['Instagram Status']} {when or '(no time)'}", flush=True)
    S.audit("upload", vid, None, {"after": p["after"], "when": when, "file": rec["Local Path"]}, params.get("who", "owner"), "", db)
    try:
        print("Sheet mirror:", json.dumps(Y.push([b["sheet_tab"]], db)), flush=True)
    except Exception as e:
        print(f"Sheet mirror not updated ({str(e)[:160]}); the next push retries", flush=True)
    code = 0
    if p["after"] == "now":
        print("publishing now (owner asked)", flush=True)
        code = (publish or publish_job.main)([vid, "--platform", "instagram", "--mirror"])
    print(f"DONE {vid}", flush=True)
    return vid, code


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    try:
        vid, code = run(json.loads(argv[0]))
    except (UploadError, Y.SyncError) as e:
        print(f"upload refused: {e}")
        return 1
    return code


if __name__ == "__main__":
    sys.exit(main())
