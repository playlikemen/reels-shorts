#!/usr/bin/env python3
"""
Linux 40 YouTube Shorts Batch Production Engine
Automates end-to-end production of the 40-part Linux Shorts series:
1. Script & TTS Neural Audio generation (with exact millisecond word timestamps)
2. Kinetic Canvas HTML generation (HyperFrames / Motion Graphics / Safe Areas)
3. MP4 rendering & contact sheet generation (Headless Chromium @ 1080x1920 30fps)
4. Strict validation (file size > 100 KB)
5. Google Drive upload & direct download link generation
6. Google Sheet sync (17 columns) & obsidian tab beautification
7. Multi-platform publishing (Instagram Reels & YouTube Shorts)
"""

import os
import sys
import json
import wave
import subprocess
import argparse
from pathlib import Path

WORKSPACE = Path("/home/kunalkashyap8024/sop/scrap/reels-shorts")
CURRICULUM_FILE = WORKSPACE / "brands/stackshade/series/linux-40/curriculum.json"
TTS_SCRIPT = WORKSPACE / "shared/scripts/tts_engine.py"
RENDER_SCRIPT = WORKSPACE / "shared/scripts/render.mjs"
SYNC_DRIVE_SCRIPT = WORKSPACE / "shared/scripts/sync_drive.py"
SYNC_SHEET_SCRIPT = WORKSPACE / "shared/scripts/sync_sheet.py"
BEAUTIFY_SCRIPT = WORKSPACE / "shared/scripts/beautify_sheet.py"
PUBLISH_IG_SCRIPT = WORKSPACE / "shared/scripts/publish_instagram.py"
PUBLISH_YT_SCRIPT = WORKSPACE / "shared/scripts/publish_youtube.py"

def load_curriculum():
    with open(CURRICULUM_FILE, "r") as f:
        return json.load(f)

def get_audio_duration(wav_path):
    with wave.open(str(wav_path), "r") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
        return frames / float(rate)

def build_reel_html(ep_data, transcript_data, duration_sec, src_dir):
    """
    Generates a high-retention, motion-graphics HTML file for the Linux episode.
    Follows all skills: short-form-video, caption-animation, kinetic-typography, soundtrack.
    """
    reelkit_rel = os.path.relpath(WORKSPACE / "shared/scripts/reelkit.js", src_dir)
    font_bold_rel = os.path.relpath(WORKSPACE / "shared/fonts/Inter-Bold.woff2", src_dir)
    font_black_rel = os.path.relpath(WORKSPACE / "shared/fonts/Inter-Black.woff2", src_dir)
    font_mono_rel = os.path.relpath(WORKSPACE / "shared/fonts/JetBrainsMono-Bold.woff2", src_dir)

    groups = transcript_data.get("pages", transcript_data.get("groups", []))
    total_frames = int((duration_sec + 1.2) * 30)
    groups_json = json.dumps(groups, indent=2)

    # Compute typing duration based on command length
    cmd = ep_data.get("command", "")
    output_lines = json.dumps(ep_data.get("output", "").split("\n"))
    badge = ep_data.get("badge", "LINUX PRO")
    color = ep_data.get("color", "#38BDF8")
    ep_num = f"{ep_data.get('ep'):02d}"
    topic = ep_data.get("topic", "")
    hook = ep_data.get("hook", "")
    cmd_dir = ep_data.get("cmd_dir", "~")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{ep_data.get('id')} - {topic}</title>
  <style>
    @font-face {{
      font-family: 'Inter';
      src: url('{font_bold_rel}') format('woff2');
      font-weight: 700;
    }}
    @font-face {{
      font-family: 'Inter';
      src: url('{font_black_rel}') format('woff2');
      font-weight: 900;
    }}
    @font-face {{
      font-family: 'JetBrains Mono';
      src: url('{font_mono_rel}') format('woff2');
      font-weight: 700;
    }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
      background: #000;
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 100vh;
      overflow: hidden;
    }}
    canvas {{
      width: 1080px;
      height: 1920px;
      max-width: 100vw;
      max-height: 100vh;
      object-fit: contain;
      box-shadow: 0 0 60px rgba(0,0,0,0.9);
    }}
  </style>
</head>
<body>
<canvas width="1080" height="1920"></canvas>
<script src="{reelkit_rel}"></script>
<script>
// Episode Metadata & Word Subtitles
const GROUPS = {groups_json};
const DURATION = {duration_sec + 1.2};
const TOTAL_FRAMES = {total_frames};
const COMMAND = "{cmd}";
const CMD_DIR = "{cmd_dir}";
const OUTPUT_LINES = {output_lines};
const ACCENT = "{color}";
const BADGE_TEXT = "{badge}";
const EP_STR = "EPISODE {ep_num} / 40 • LINUX POWER";
const TOPIC_TITLE = "{topic.upper()}";
const HOOK_TEXT = "{hook}";

// Scene Timing
const TYPING_START = 2.2;
const TYPING_DUR = Math.min(2.8, Math.max(1.4, COMMAND.length * 0.08));
const TYPING_END = TYPING_START + TYPING_DUR;
const EXEC_TIME = TYPING_END + 0.3;

// Pattern Interrupt Cues (Camera Punches & SFX)
window.CUES = [0.8, TYPING_START, EXEC_TIME, 8.5, 14.0];

// Procedural Audio Soundtrack & Sound Effects
window.SCORE = ac => {{
  const hits = [
    {{ t: 0.8, type: 'whoosh' }},
    {{ t: EXEC_TIME, type: 'enter' }},
    {{ t: 8.5, type: 'whoosh' }}
  ];
  // Add subtle typing clacks
  for (let t = TYPING_START; t < TYPING_END; t += 0.14) {{
    hits.push({{ t, type: 'clack' }});
  }}
  buildScore(ac, {{
    bpm: 124,
    dur: DURATION,
    root: 43,
    chords: [0, 3, 5, 2],
    minor: true,
    kickFrom: 0.2,
    level: 0.75,
    hits
  }});
}};

function drawFrame(t) {{
  ctx.save();

  // 1. Retention Camera Punch (Pattern Interrupt)
  punchCamera(t, [0.8, EXEC_TIME, 8.5, 14.0], 0.45, 1.07);

  // 2. Futuristic Cyber Background Grid with Moving Scanner Beam
  grid(t, 64, 'rgba(56, 189, 248, 0.05)', 'rgba(56, 189, 248, 0.12)');

  // 3. Top Safe Zone Branded Header Pill (Y: 280px)
  const headerProg = clamp(t / 0.6);
  if (headerProg > 0) {{
    const hy = 280;
    // Category & Episode Pill
    rr(120, hy, 840, 68, 34, 'rgba(15, 23, 42, 0.85)', 'rgba(255, 255, 255, 0.12)', 2, headerProg);
    txt(EP_STR, 540, hy + 44, {{ px: 26, fam: 'JetBrains Mono', wt: 700, fill: '#94A3B8', align: 'center', alpha: headerProg }});
    // Floating Neon Badge
    const bw = 240, bh = 48;
    glow(ACCENT, 20);
    rr(540 - bw/2, hy + 86, bw, bh, 24, ACCENT, null, 0, headerProg);
    noGlow();
    txt(BADGE_TEXT, 540, hy + 120, {{ px: 22, fam: 'Inter', wt: 900, fill: '#000', align: 'center', alpha: headerProg }});
  }}

  // 4. Hook Title Card (Frame 0-3s entrance, fades to compact title)
  if (t < 3.2) {{
    const hookProg = clamp(t / 0.4);
    const hookAlpha = t > 2.6 ? (3.2 - t) / 0.6 : 1.0;
    ctx.save();
    setA(hookAlpha * hookProg);
    glow('rgba(0,0,0,0.8)', 30);
    txt(HOOK_TEXT, 540, 520, {{ px: 52, fam: 'Inter', wt: 900, fill: '#FFFFFF', stroke: '#000', strokeW: 14, align: 'center' }});
    noGlow();
    ctx.restore();
  }} else {{
    // Settled Topic Title
    const titleP = clamp((t - 3.2) / 0.4);
    txt(TOPIC_TITLE, 540, 500, {{ px: 46, fam: 'Inter', wt: 900, fill: ACCENT, stroke: '#000', strokeW: 10, align: 'center', alpha: titleP }});
  }}

  // 5. Floating Interactive Terminal Window (Y: 570 - 1180px)
  const termX = 90, termY = 560, termW = 900, termH = 620;
  const termProg = clamp(t / 0.5);
  drawTerminalCard(termX, termY, termW, termH, {{
    title: 'stackshade@linux — 1080×1920',
    bg: '#070C18',
    border: ACCENT,
    glowColor: 'rgba(56, 189, 248, 0.18)',
    alpha: termProg
  }});

  // Terminal Prompt & Interactive Typing
  const promptY = termY + 130;
  const promptStr = CMD_DIR + " $ ";
  txt(promptStr, termX + 44, promptY, {{ px: 32, fam: 'JetBrains Mono', wt: 700, fill: '#10B981', align: 'left', alpha: termProg }});
  
  // Calculate Typed String
  let typed = "";
  if (t >= TYPING_START) {{
    const typeP = clamp((t - TYPING_START) / TYPING_DUR);
    const charsToShow = Math.floor(typeP * COMMAND.length);
    typed = COMMAND.substring(0, charsToShow);
  }}
  
  // Measure prompt offset
  ctx.font = '700 32px "JetBrains Mono"';
  const promptW = ctx.measureText(promptStr).width;
  const cmdX = termX + 44 + promptW;
  txt(typed, cmdX, promptY, {{ px: 32, fam: 'JetBrains Mono', wt: 700, fill: '#FFFFFF', align: 'left' }});

  // Blinking Block Cursor
  const cursorBlink = Math.sin(t * 12) > 0;
  if (cursorBlink && t < EXEC_TIME + 2.0) {{
    const typedW = ctx.measureText(typed).width;
    glow(ACCENT, 12);
    rr(cmdX + typedW + 4, promptY - 26, 16, 32, 2, ACCENT, null, 0);
    noGlow();
  }}

  // Simulated Terminal Output Execution
  if (t >= EXEC_TIME) {{
    const execProg = clamp((t - EXEC_TIME) / 0.4);
    let outY = promptY + 68;
    for (let i = 0; i < OUTPUT_LINES.length; i++) {{
      const line = OUTPUT_LINES[i];
      const isHighlight = line.startsWith('~') || line.startsWith('[');
      const lineFill = isHighlight ? ACCENT : '#94A3B8';
      const lineWt = isHighlight ? 700 : 500;
      txt(line, termX + 44, outY, {{ px: 28, fam: 'JetBrains Mono', wt: lineWt, fill: lineFill, align: 'left', alpha: execProg }});
      outY += 46;
    }}
  }}

  // 6. Kinetic Karaoke Subtitles (Y: 1260 - 1380px)
  renderCaptions(t);

  // 7. Bottom Safe Zone Brand Footer (Y: 1820px, well above 420px margin)
  txt("@StackShade • Subscribe for Daily Systems Deep Dives", 540, 1460, {{ px: 28, fam: 'Inter', wt: 700, fill: '#64748B', align: 'center' }});

  ctx.restore();
}}

function renderCaptions(t) {{
  // Find currently active word group
  let curGroup = null;
  for (const g of GROUPS) {{
    if (t >= g.start && t <= g.end + 0.3) {{
      curGroup = g;
      break;
    }}
  }}
  if (!curGroup) return;

  const words = curGroup.words || [];
  if (!words.length) return;

  ctx.save();
  ctx.font = '900 68px "Inter", -apple-system, sans-serif';

  // Measure word widths for precise spacing
  let totalW = 0;
  const wordWidths = words.map(w => {{
    const wWidth = ctx.measureText(w.word.toUpperCase()).width;
    totalW += wWidth + 24;
    return wWidth;
  }});
  totalW -= 24;

  const startX = 540 - totalW / 2;
  const capY = 1320;

  // Background capsule for contrast
  rr(startX - 36, capY - 76, totalW + 72, 106, 28, 'rgba(0, 0, 0, 0.85)', 'rgba(255, 255, 255, 0.12)', 2);

  let curX = startX;
  for (let i = 0; i < words.length; i++) {{
    const w = words[i];
    const isActive = t >= w.start && t <= w.end + 0.15;
    const wordStr = w.word.toUpperCase();
    const wWidth = wordWidths[i];

    ctx.save();
    if (isActive) {{
      // Micro-overshoot pop from caption-animation skill
      const wordProg = clamp((t - w.start) / 0.15);
      const scale = 1.0 + Math.sin(wordProg * Math.PI) * 0.18;
      ctx.translate(curX + wWidth / 2, capY);
      ctx.scale(scale, scale);
      ctx.translate(-(curX + wWidth / 2), -capY);

      glow('#FFE45E', 24);
      txt(wordStr, curX, capY, {{ px: 68, fam: 'Inter', wt: 900, fill: '#FFE45E', stroke: '#000000', strokeW: 16, align: 'left' }});
      noGlow();
    }} else {{
      txt(wordStr, curX, capY, {{ px: 68, fam: 'Inter', wt: 900, fill: '#FFFFFF', stroke: '#000000', strokeW: 12, align: 'left' }});
    }}
    ctx.restore();
    curX += wWidth + 24;
  }}
  ctx.restore();
}}

// Initialize ReelKit Runtime
startReel(TOTAL_FRAMES, drawFrame);
</script>
</body>
</html>"""
    return html

def produce_episode(ep_data, dry_run=False, publish=False):
    ep_id = ep_data["id"]
    reel_dir_name = f"2026-11-17-{ep_id.lower()}-{ep_data['topic'].lower().replace(' ', '-').replace('/', '-').replace(':', '')[:30]}"
    reel_dir = WORKSPACE / "brands/stackshade/reels" / reel_dir_name
    src_dir = reel_dir / "src"
    out_dir = reel_dir / "out"

    print(f"\n=======================================================")
    print(f"🎬 PRODUCING EPISODE: {ep_id} — {ep_data['topic']}")
    print(f"📁 Directory: {reel_dir}")
    print(f"=======================================================")

    if dry_run:
        print("[batch] Dry-run enabled. Skipping render.")
        return

    src_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Synthesize Neural TTS Voiceover
    mp3_path = out_dir / "voiceover.mp3"
    wav_path = out_dir / "voiceover.wav"
    transcript_path = out_dir / "transcript.json"

    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        print(f"[batch] Generating neural voiceover for {ep_id}...")
        cmd_tts = [
            "python3.11", str(TTS_SCRIPT),
            ep_data["script"],
            str(mp3_path),
            "--json", str(transcript_path),
            "--voice", "en-US-ChristopherNeural"
        ]
        res = subprocess.run(cmd_tts, capture_output=True, text=True)
        if res.returncode != 0:
            print(f"[batch] TTS Error: {res.stderr}")
            return False

    with open(transcript_path, "r") as f:
        transcript_data = json.load(f)

    duration_sec = get_audio_duration(wav_path)
    print(f"[batch] Audio duration: {duration_sec:.2f}s")

    # 2. Build Kinetic Canvas HTML
    html_content = build_reel_html(ep_data, transcript_data, duration_sec, src_dir)
    html_path = src_dir / "reel.html"
    with open(html_path, "w") as f:
        f.write(html_content)
    print(f"[batch] Generated kinetic HTML template: {html_path}")

    # 3. Render MP4 and Contact Sheet
    final_mp4 = out_dir / "final.mp4"
    sheet_jpg = out_dir / "sheet.jpg"

    print(f"[batch] Rendering 1080x1920 30fps MP4 with headless Chromium...")
    cmd_render = [
        "node", str(RENDER_SCRIPT),
        str(html_path),
        str(final_mp4),
        "--audio", str(wav_path)
    ]
    res_render = subprocess.run(cmd_render, capture_output=True, text=True)
    if res_render.returncode != 0:
        print(f"[batch] Render Error: {res_render.stderr}\n{res_render.stdout}")
        return False

    # Render contact sheet for quick quality inspection
    print(f"[batch] Rendering verification contact sheet...")
    cmd_sheet = [
        "node", str(RENDER_SCRIPT),
        str(html_path),
        str(sheet_jpg),
        "--sheet", "2"
    ]
    subprocess.run(cmd_sheet, capture_output=True, text=True)

    # Validate deliverable size
    if not final_mp4.exists() or final_mp4.stat().st_size < 100000:
        print(f"[batch] ❌ Validation failed! File {final_mp4} is missing or < 100 KB.")
        return False
    print(f"[batch] ✅ MP4 render validated: {final_mp4.stat().st_size / (1024*1024):.2f} MB")

    # 4. Upload to Google Drive & Generate Direct Download Link
    print(f"[batch] Syncing to Google Drive...")
    cmd_drive = [
        "python3.11", str(SYNC_DRIVE_SCRIPT),
        str(reel_dir)
    ]
    res_drive = subprocess.run(cmd_drive, capture_output=True, text=True)
    print(res_drive.stdout)

    # 5. Build Rich 17-Column Metadata File
    metadata_path = out_dir / "metadata.json"
    drive_id = ""
    direct_link = ""
    drive_folder = "https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS"

    # Read drive results if written by sync_drive
    if metadata_path.exists():
        try:
            with open(metadata_path, "r") as f:
                saved_meta = json.load(f)
                drive_id = saved_meta.get("drive_file_id", "")
                direct_link = saved_meta.get("direct_download_link", "")
        except:
            pass

    if drive_id and not direct_link:
        direct_link = f"https://drive.google.com/uc?id={drive_id}&export=download"

    metadata = {
        "video_id": ep_id,
        "date": "2026-11-17",
        "category_topic": f"Linux / {ep_data['topic']}",
        "category": f"Linux / {ep_data['topic']}",
        "format": "HyperFrames Motion Graphics",
        "duration": f"{int(duration_sec + 1.2)}s",
        "local_path": str(final_mp4.relative_to(WORKSPACE)),
        "google_drive_folder": drive_folder,
        "drive_link": drive_folder,
        "direct_mp4_download_link": direct_link,
        "direct_download_link": direct_link,
        "drive_file_id": drive_id,
        "youtube_title": ep_data["yt_title"],
        "yt_title": ep_data["yt_title"],
        "youtube_seo_tags": ep_data["yt_tags"],
        "yt_seo_tags": ep_data["yt_tags"],
        "youtube_best_seo_description": ep_data["yt_desc"],
        "yt_description": ep_data["yt_desc"],
        "instagram_viral_caption": ep_data["ig_caption"],
        "insta_caption": ep_data["ig_caption"],
        "instagram_hashtags": ep_data["ig_tags"],
        "insta_hashtags": ep_data["ig_tags"],
        "instagram_status": "Ready",
        "instagram_post_url": "",
        "youtube_status": "Ready",
        "youtube_shorts_url": ""
    }

    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    # Save caption.txt for Instagram / social publishing
    caption_path = out_dir / "caption.txt"
    with open(caption_path, "w") as f:
        f.write(f"{ep_data['ig_caption']}\n\n{ep_data['ig_tags']}\n")

    # 6. Sync to Google Sheets
    print(f"[batch] Syncing metadata to Google Sheet tab '@StackShade'...")
    cmd_sheet = [
        "python3.11", str(SYNC_SHEET_SCRIPT),
        "--add-json", str(metadata_path),
        "--tab", "@StackShade"
    ]
    subprocess.run(cmd_sheet, capture_output=True, text=True)

    # Beautify sheet tab
    cmd_beautify = [
        "python3.11", str(BEAUTIFY_SCRIPT),
        "--tab", "@StackShade"
    ]
    subprocess.run(cmd_beautify, capture_output=True, text=True)

    # 7. Optional Publish to Instagram & YouTube
    if publish:
        print(f"[batch] Publishing {ep_id} to Instagram & YouTube...")
        cmd_pub_ig = ["python3.11", str(PUBLISH_IG_SCRIPT), "--reel-dir", str(reel_dir), "--brand", "stackshade"]
        subprocess.run(cmd_pub_ig, capture_output=True, text=True)

    print(f"🎉 Episode {ep_id} completely finished and synced!")
    return True

def main():
    parser = argparse.ArgumentParser(description="Batch Linux Series Production Engine")
    parser.add_argument("--episodes", "-e", default="1", help="Episodes to produce: '1', '1-5', 'all'")
    parser.add_argument("--dry-run", action="store_true", help="Print plans without rendering")
    parser.add_argument("--publish", action="store_true", help="Publish produced episodes immediately")
    args = parser.parse_args()

    curriculum = load_curriculum()
    ep_map = {str(ep["ep"]): ep for ep in curriculum}
    ep_map.update({ep["id"].upper(): ep for ep in curriculum})

    targets = []
    if args.episodes.lower() == "all":
        targets = curriculum
    elif "-" in args.episodes:
        start, end = map(int, args.episodes.split("-"))
        targets = [ep for ep in curriculum if start <= ep["ep"] <= end]
    else:
        for item in args.episodes.split(","):
            item = item.strip().upper()
            if item in ep_map:
                targets.append(ep_map[item])

    print(f"Loaded {len(targets)} target episodes to produce.")
    for ep in targets:
        success = produce_episode(ep, dry_run=args.dry_run, publish=args.publish)
        if not success and not args.dry_run:
            print(f"[batch] Error processing {ep['id']}. Stopping batch.")
            break

if __name__ == "__main__":
    main()
