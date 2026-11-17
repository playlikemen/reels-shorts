# Agent Context & Operation Manual (reels-shorts)

This repository automates vertical video production (Instagram Reels & YouTube Shorts) for tech educational brands, specifically **StackShade** (`@stackshade` / `@StackShade`).

---

## 1. Brand Profiles & Accounts

| Brand | Platform | Handle / URL | Composio Account ID | Notes |
|---|---|---|---|---|
| **StackShade** | Instagram | [@stackshade](https://www.instagram.com/stackshade/) | `instagram_create-beta` | Alias: `stackshade`, Active |
| **StackShade** | YouTube | [@StackShade/shorts](https://www.youtube.com/@StackShade/shorts) | `youtube_run-retin` | Channel: `@StackShade`, Active |
| **Google Sheets** | Tracker | [Spreadsheet](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit) | `googlesheets_louse-token` | Tab: `@StackShade` |
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
│   └── stackshade/
│       ├── brand.md           # Brand positioning, voice, typography, safe areas
│       ├── calendar.csv       # Content programming schedule
│       ├── assets/            # Logos, icons, badges
│       └── reels/             # Reel production folders
│           ├── 2026-11-17-redis-vs-mysql/
│           │   ├── brief.md
│           │   ├── src/reel.html
│           │   └── out/ (final.mp4, sheet.jpg, caption.txt, metadata.json)
│           └── 2026-11-17-how-ai-agents-code/
│               ├── brief.md
│               ├── src/reel.html
│               └── out/ (final.mp4, sheet.jpg, caption.txt, metadata.json)
├── shared/
│   ├── fonts/                 # WOFF2 fonts (Inter 700/900, JetBrains Mono 700)
│   └── scripts/
│       ├── reelkit.js         # Canvas/HyperFrames animation framework
│       ├── render.mjs         # Headless browser frame capture & MP4 muxing
│       ├── sync_sheet.py      # Composio Google Sheets synchronization
│       ├── sync_drive.py      # Composio Google Drive archival
│       ├── publish_instagram.py # Instagram Reels publisher
│       └── publish_youtube.py # YouTube Shorts publisher
└── pipeline/
    ├── RUNBOOK.md             # Standard Operating Procedure
    └── publish-log.jsonl      # Audit trail & status tracking
```

---

## 3. Core Commands

```bash
# 1. Render a contact sheet (check layout & text before full render)
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/sheet.jpg --sheet 2

# 2. Render the full MP4 video (with code-synthesized audio)
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/final.mp4

# 3. Upload artifacts to Google Drive
npm run drive:sync -- brands/stackshade/reels/<reel_dir>

# 4. Sync metadata to Google Sheet (@StackShade tab)
npm run sheet:sync -- --add-json brands/stackshade/reels/<reel_dir>/out/metadata.json

# 5. List current Google Sheet rows
npm run sheet:sync -- --list

# 6. Publish to Instagram (when public video URL is deployed)
npm run publish:instagram -- brands/stackshade/reels/<reel_dir> --url <public_video_url>

# 7. Publish to YouTube
npm run publish:youtube -- brands/stackshade/reels/<reel_dir>
```

---

## 4. Engineering & Aesthetic Rules

- **Resolution & Aspect**: Always `1080x1920` (9:16 vertical).
- **Framerate**: Exactly `30 fps`.
- **Top Safe Area**: **250 px** top margin. No text or crucial elements inside 0-250px.
- **Bottom Safe Area**: **420 px** bottom margin. No text or crucial elements inside 1500-1920px.
- **Color Palette**: Dark mode obsidian `#070a12`, Cyan `#38bdf8`, Emerald `#10b981`, Amber `#f59e0b`, Purple `#a855f7`.
- **Audio**: Deterministic Web Audio synthesizer in `window.SCORE` or licensed lossless audio. Never commit unlicensed music files.
- **Factuality**: Accurate engineering facts, numbers, and diagrams. Never hallucinate fake benchmark numbers.
