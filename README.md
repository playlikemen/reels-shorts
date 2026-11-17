# StackShade Reels & Shorts Production Engine

Automated programmatic video production pipeline for high-retention technical Instagram Reels and YouTube Shorts for **StackShade** ([@stackshade](https://www.instagram.com/stackshade/) & [@StackShade](https://www.youtube.com/@StackShade/shorts)).

---

## ⚡ Features

- **Code-Driven Video Generation**: 1080x1920 @ 30 FPS vertical video rendered frame-by-frame using HTML5 Canvas, GSAP, and Headless Chrome.
- **Synthesized Audio Bed**: Built-in Web Audio synthesis generating custom techno electronic beats, kicks, and scene drops with zero licensing risk.
- **Direct Cloud Integration via Composio**:
  - **Google Sheets Tracker**: Automatically logs video IDs, hooks, topics, Drive URLs, and live upload statuses.
  - **Google Drive Archival**: Direct upload of reel directories and metadata to the dedicated Drive storage folder.
  - **Social Publishing**: Programmatic publishing to Instagram Reels and YouTube Shorts.
- **Safe Area Enforcement**: Designed specifically for Instagram and YouTube Shorts interfaces (top 250px and bottom 420px margins respected).

---

## 📂 Live Integrations

- **Google Sheet**: [Reels or Shorts Sheet](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit) (Tab: `@StackShade`)
- **Google Drive Folder**: [Reels & Shorts Archive](https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS)
- **Instagram**: [https://www.instagram.com/stackshade/](https://www.instagram.com/stackshade/)
- **YouTube Shorts**: [https://www.youtube.com/@StackShade/shorts](https://www.youtube.com/@StackShade/shorts)

---

## 🚀 Quick Start

### 1. Render a Reel

```bash
# 1. Preview contact sheet (1 frame every 2 seconds)
npm run render -- brands/stackshade/reels/2026-11-17-redis-vs-mysql/src/reel.html brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/sheet.jpg --sheet 2

# 2. Render final MP4
npm run render -- brands/stackshade/reels/2026-11-17-redis-vs-mysql/src/reel.html brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/final.mp4
```

### 2. Archive to Google Drive

```bash
npm run drive:sync -- brands/stackshade/reels/2026-11-17-redis-vs-mysql
```

### 3. Log to Google Sheet

```bash
npm run sheet:sync -- --add-json brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/metadata.json
```

### 4. Check Google Sheet Status

```bash
npm run sheet:sync -- --list
```

---

## 🎬 Current Production Reels

1. **SS-001**: *Why Redis is 100x Faster Than MySQL (RAM vs Disk)*
   - **Topic**: System Design & Architecture
   - **Duration**: 15s (1080x1920 @ 30fps)
   - **Drive Folder**: [View on Google Drive](https://drive.google.com/drive/folders/1RHQ73lS1kmfo8uGTT6QDlChstP5Q7S0U)
   - **Status**: Ready in Google Sheet

2. **SS-002**: *How AI Agents Actually Code (The ReAct Loop)*
   - **Topic**: AI Engineering & Modern Tools
   - **Duration**: 15s (1080x1920 @ 30fps)
   - **Drive Folder**: [View on Google Drive](https://drive.google.com/drive/folders/1r0nqW3PAHOkm6d_ES0QdZyj4ynPZ4SPA)
   - **Status**: Ready in Google Sheet
