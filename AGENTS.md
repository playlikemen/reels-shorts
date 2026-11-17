# Agent Context & Operation Manual (reels-shorts)

This repository automates vertical video production (Instagram Reels & YouTube Shorts) for tech educational and SaaS brands:
1. **StackShade** (`@stackshade` / `@StackShade`): Deep engineering, system design, and AI trend breakdowns.
2. **IndexFast** (`@indexfast` / `indexfast.co`): Google indexing automation, crawl budget hacks, and programmatic SEO.

---

## 1. Brand Profiles & Accounts

| Brand | Platform | Handle / URL | Composio Account ID | Notes |
|---|---|---|---|---|
| **StackShade** | Instagram | [@stackshade](https://www.instagram.com/stackshade/) | `instagram_create-beta` | Alias: `stackshade`, Active |
| **StackShade** | YouTube | [@StackShade/shorts](https://www.youtube.com/@StackShade/shorts) | `youtube_run-retin` | Channel: `@StackShade`, Active |
| **IndexFast** | Instagram | [@indexfast](https://www.instagram.com/indexfast/) | `instagram_dam-hinder` | Name: `Indexfast.co`, Active |
| **Google Sheets** | Tracker | [Spreadsheet](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit) | `googlesheets_louse-token` | Tabs: `@StackShade`, `@indexfast` |
| **Google Drive** | Archive | [Drive Folder](https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS) | `googledrive_footle-khir` | Folder ID: `1upAISpZAnmyDDYki_FH9tK-FVh_djqLS` |

---

## 2. Directory Layout

```
reels-shorts/
├── AGENTS.md                  # This operational manual
├── README.md                  # Human-friendly documentation
├── package.json               # NPM scripts & dependencies
├── node_modules               # Symlinked from videos-skill
├── brands/
│   ├── stackshade/
│   │   ├── brand.md           # Brand positioning, voice, typography, safe areas
│   │   ├── series/
│   │   │   └── linux-40/      # 40-part Linux Masterclass curriculum & README
│   │   └── reels/
│   │       ├── 2026-11-17-lnx-001-cd---&-directory-jumping/ (LNX-001, Published)
│   │       ├── 2026-11-17-lnx-002-ls--lah-&-hidden-inodes/ (LNX-002, Ready)
│   │       ├── 2026-11-17-lnx-003-ctrl+r-&-reverse-search/ (LNX-003, Ready)
│   │       ├── 2026-11-17-redis-vs-mysql/ (SS-001, Published)
│   │       ├── 2026-11-17-how-ai-agents-code/ (SS-002, Ready)
│   │       └── 2026-11-17-ai-security-alerts/ (SS-003, Ready)
│   └── indexfast/
│       ├── brand.md           # SEO positioning, crawl budget automation
│       └── reels/
│           └── 2026-11-17-google-indexing-in-24h/ (IF-001, Published)
├── shared/
│   ├── fonts/                 # WOFF2 fonts (Inter 700/900, JetBrains Mono 700)
│   ├── assets/audio/          # Studio sound effects (keyboard clacks, enter beeps, sub whooshes)
│   └── scripts/
│       ├── reelkit.js         # Canvas/HyperFrames animation framework & camera punches
│       ├── render.mjs         # Headless browser frame capture & multi-track audio muxing
│       ├── tts_engine.py      # Edge Neural TTS & word-boundary caption timing generator
│       ├── sfx_library.py     # Studio SFX synthesizer
│       ├── openverse_client.py# Openverse CC0 asset client
│       ├── sync_sheet.py      # Composio Google Sheets sync & beautification
│       ├── sync_drive.py      # Google Drive resumable upload & direct links
│       ├── publish_instagram.py # Instagram Reels multi-brand publisher
│       └── publish_youtube.py # YouTube Shorts publisher
├── skills/                    # 27 Motion Graphics Skills from iart-ai/motion-skills
│   ├── short-form-video/      # Hook grammar, pattern interrupts, retention curve
│   ├── caption-animation/     # Kinetic karaoke captions with active-word pop
│   ├── kinetic-typography/    # Expressive text reveals & typography in motion
│   ├── soundtrack/            # Procedural Web Audio score & SFX synthesis
│   └── ...                    # 23 additional motion graphics skills
├── tools/verify/              # Video verification scripts (probe-mp4, contact-sheet, seek-shot)
└── pipeline/
    ├── batch_linux_engine.py  # 40-part automated batch generator & renderer
    ├── build_linux_curriculum.py # Master syllabus generator
    ├── daily_scheduler.py     # Automated daily 3-reel scheduling engine
    └── publish-log.jsonl      # Audit trail & status tracking
```

---

## 3. Core Commands

```bash
# 1. Produce Linux Series Episodes (Neural Voiceover + Kinetic HTML + MP4 + Drive + Sheets)
npm run series:produce -- --episodes 1          # Produce Episode 1
npm run series:produce -- --episodes 1-5        # Produce Batch 1-5
npm run series:produce -- --episodes all        # Produce all 40 episodes

# 2. Render a contact sheet (check layout & text before full render)
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/sheet.jpg --sheet 2

# 3. Render the full MP4 video (with code-synthesized audio)
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/final.mp4

# 4. Upload artifacts to Google Drive (guarantees size > 100KB, generates direct download link)
npm run drive:sync -- brands/stackshade/reels/<reel_dir>

# 5. Sync metadata to Google Sheet & auto-beautify tab
npm run sheet:sync -- --add-json brands/stackshade/reels/<reel_dir>/out/metadata.json --tab "@StackShade"

# 6. Beautify Google Sheet tabs (frozen header, Obsidian header #0F172A, column widths, text wrapping)
npm run sheet:beautify -- --tab "@StackShade"
npm run sheet:beautify -- --tab "@indexfast"

# 7. Publish to Instagram
python3.11 shared/scripts/publish_instagram.py brands/stackshade/reels/<reel_dir>

# 8. Daily scheduler live execution
npm run schedule:publish
```

---

## 4. Google Sheet Structure (17 Columns)

Both `@StackShade` and `@indexfast` tabs maintain 17 columns:
1. `Video ID`: Unique identifier (`SS-001`, `IF-001`, `LNX-001`)
2. `Date`: Creation / scheduled post date
3. `Category / Topic`: Primary content pillar
4. `Format`: Production engine (`HyperFrames Motion Graphics`, etc.)
5. `Duration`: Video duration (`15s`, `17s`, `30s`)
6. `Local Path`: Relative path to MP4 deliverable
7. `Google Drive Folder`: Shareable Drive folder link
8. `Direct MP4 Download Link`: Direct one-click stream link (`https://drive.google.com/uc?id={file_id}&export=download`)
9. `YouTube Title`: Catchy hook + `#shorts`
10. `YouTube SEO Tags (Separated)`: Comma-separated high-volume search tags
11. `YouTube Best SEO Description`: Full SEO description with timestamps, summary, and links
12. `Instagram Viral Caption`: Hook, emoji bullet breakdown, and CTA
13. `Instagram Hashtags`: Curated hashtag group
14. `Instagram Status`: `Draft`, `Ready`, `Published`
15. `Instagram Post URL`: Live Instagram permalink
16. `YouTube Status`: `Draft`, `Ready`, `Published`
17. `YouTube Shorts URL`: Live Shorts permalink

---

## 5. Engineering & Aesthetic Rules

- **Resolution & Aspect**: Always `1080x1920` (9:16 vertical).
- **Framerate**: Exactly `30 fps`.
- **Top Safe Area**: **250 px** top margin. No text or crucial elements inside 0-250px.
- **Bottom Safe Area**: **420 px** bottom margin. No text or crucial elements inside 1500-1920px.
- **Strict Validation**: Video files must exist and be $> 100\text{ KB}$ before any Google Drive upload or Google Sheet entry. Never add 0 KB files.
- **Color Palette**:
  - StackShade: Dark obsidian `#070a12`, Cyan `#38bdf8`, Emerald `#10b981`, Amber `#f59e0b`.
  - IndexFast: Emerald Obsidian `#060d0a`, Neon Emerald `#10b981`, Cyan `#06b6d4`.
- **Sound Design**: Multi-track mix of Edge Neural TTS voiceover (`[1:a]volume=1.15`), Web Audio procedural techno bed (`[2:a]volume=0.12`), and studio sound effects (keyboard typing clacks, enter bleeps, and sub-bass whooshes).
