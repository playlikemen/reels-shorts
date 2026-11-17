# Reels & Shorts Automated Production Engine

Automated programmatic video production and daily publishing pipeline for vertical short-form video (Instagram Reels & YouTube Shorts), supporting:
- **StackShade** ([@stackshade](https://www.instagram.com/stackshade/) / [@StackShade](https://www.youtube.com/@StackShade/shorts)): Computer engineering, system design, and AI tech alerts.
- **IndexFast** ([@indexfast](https://www.instagram.com/indexfast/) / [indexfast.co](https://indexfast.co)): Google indexing automation, crawl budget optimization, and programmatic SEO.

---

## ⚡ Core Capabilities

- **Code-Driven Video Generation**: 1080x1920 @ 30 FPS vertical video rendered frame-by-frame using HTML5 Canvas, GSAP, and Headless Chrome.
- **27 Installed Motion Skills**: Full library of motion graphics, kinetic typography, camera punches, sound design, and retention grammar from [`iart-ai/motion-skills`](https://github.com/iart-ai/motion-skills).
- **Studio Sound Design & Openverse Integration**: Multi-track audio mixing combining Neural voiceovers (`edge-tts`), procedural electronic synth beds (`window.SCORE`), studio terminal sound effects (keyboard clacks, enter bells, sub-bass whooshes), and Openverse CC0 asset retrieval.
- **Strict Video Verification**: Enforces local binary size validation ($> 100\text{ KB}$) and verified Google Drive byte upload to prevent 0 KB files.
- **Direct 1-Click MP4 Downloads**: Generates modified Google Drive direct streaming links (`https://drive.google.com/uc?id={file_id}&export=download`).
- **Comprehensive 17-Column Sheet Tracking**: Includes separated YouTube SEO tags, best SEO description, viral Instagram captions & hashtags.
- **Automated Sheet Beautification**: Dark Obsidian frozen header (`#0F172A`), bold white typography, custom column widths, and text wrapping.
- **Daily Multi-Brand Publishing Engine**: Automated scheduler selecting 2–3 reels daily (1 architecture + 1 news/trend + 1 SaaS growth) via Composio.

---

## 📂 Live Integrations & Trackers

- **Google Spreadsheet**: [Reels or Shorts Tracker](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit)
  - Tab `@StackShade`: Active engineering & AI alerts tracker
  - Tab `@indexfast`: Active SEO & indexing automation tracker
- **Google Drive Storage**: [Archive Folder](https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS) (Folder ID: `1upAISpZAnmyDDYki_FH9tK-FVh_djqLS`)
- **Instagram Channels**:
  - StackShade: [https://www.instagram.com/stackshade/](https://www.instagram.com/stackshade/) (`instagram_create-beta`)
  - IndexFast: [https://www.instagram.com/indexfast/](https://www.instagram.com/indexfast/) (`instagram_dam-hinder`)
- **YouTube Shorts**:
  - StackShade: [https://www.youtube.com/@StackShade/shorts](https://www.youtube.com/@StackShade/shorts) (`youtube_run-retin`)

---

## 🐧 40-Part Linux Shorts Series

A 40-part vertical video curriculum teaching Linux fundamentals, systems engineering, performance tuning, and kernel internals.

Full syllabus and documentation available at [brands/stackshade/series/linux-40/README.md](file:///home/kunalkashyap8024/sop/scrap/reels-shorts/brands/stackshade/series/linux-40/README.md).

- **Module 1**: Terminal Navigation & Daily Superpowers (Episodes 1–8)
- **Module 2**: Process Control, Signals & Memory (Episodes 9–16)
- **Module 3**: Filesystem, Permissions & Storage Wizardry (Episodes 17–24)
- **Module 4**: Networking, Sockets & Remote Power (Episodes 25–32)
- **Module 5**: Kernel, Containers, Automation & Dark Arts (Episodes 33–40)

---

## 🎬 Live Deliverables

| Video ID | Brand | Category | Title | Duration | File Size | Direct MP4 Download | Status / Live URL |
|---|---|---|---|---|---|---|---|
| **LNX-001** | StackShade | Linux Navigation | *Stop Typing cd ../.. Five Times in Linux!* | 17s | 2.73 MB | [Direct Download](https://drive.google.com/uc?id=1543dsDs-ZiP3WeB-Yd695r9_tEDj6fgv&export=download) | [Live Instagram Reel](https://www.instagram.com/reel/Df2OtPQk2n-/) |
| **LNX-002** | StackShade | Linux Permissions | *You've Been Using 'ls' Wrong in Linux!* | 19s | 3.04 MB | [Direct Download](https://drive.google.com/uc?id=1NYNLJHifqw2OHm655PHzXBjgEYga0_vw&export=download) | Verified & Ready in Sheet |
| **LNX-003** | StackShade | Terminal Hacks | *The Ctrl+R Linux Trick Senior Devs Never Share* | 18s | 2.86 MB | [Direct Download](https://drive.google.com/uc?id=1ENHCtfpEXUb7eg3kQtrzy9xqo7dTaiqj&export=download) | Verified & Ready in Sheet |
| **SS-001** | StackShade | System Design | *Why Redis is 100x Faster Than MySQL* | 31s | 4.50 MB | [Direct Download](https://drive.google.com/uc?id=16LAOb0mHWVAJzPZ-W-deCqd_ExmJuZiQ&export=download) | [Live Instagram Reel](https://www.instagram.com/reel/Df2LsnVFRXt/) |
| **SS-002** | StackShade | AI Engineering | *How AI Agents Actually Code (ReAct Loop)* | 38s | 4.82 MB | [Direct Download](https://drive.google.com/uc?id=1gd0oequGsF6swsJWw__vwRXNCLfRDVWr&export=download) | Verified & Ready in Sheet |
| **SS-003** | StackShade | News & Cyber Alert | *3 Critical AI Security Hacks Exposed This Week* | 37s | 4.54 MB | [Direct Download](https://drive.google.com/uc?id=154Z40NBwTCxqNbaNOlGVhbs2n6Q0thBc&export=download) | Verified & Ready in Sheet |
| **IF-001** | IndexFast | SEO Automation | *Why Google Takes 3 Weeks to Index (24h Fix)* | 34s | 4.04 MB | [Direct Download](https://drive.google.com/uc?id=10DoA-nBo5o-BoBmzc1nKahsXxIvvrfcZ&export=download) | [Live Instagram Reel](https://www.instagram.com/reel/Df2LyjNhwC3/) |

---

## 🚀 Commands Reference

```bash
# 1. Produce Linux Series Episodes (Neural Voiceover + Kinetic HTML + MP4 + Drive + Sheets)
npm run series:produce -- --episodes 1          # Produce Episode 1
npm run series:produce -- --episodes 1-5        # Produce Batch 1-5
npm run series:produce -- --episodes all        # Produce all 40 episodes

# 2. Preview contact sheet (visual QA)
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/sheet.jpg --sheet 2

# 3. Render final MP4
npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/final.mp4

# 4. Stream binary video to Google Drive (resumable upload, verification & direct link generation)
npm run drive:sync -- brands/stackshade/reels/<reel_dir>

# 5. Sync metadata to Google Sheet with strict file validation
npm run sheet:sync -- --add-json brands/stackshade/reels/<reel_dir>/out/metadata.json --tab "@StackShade"

# 6. Beautify Google Sheet tabs
npm run sheet:beautify -- --tab "@StackShade"
npm run sheet:beautify -- --tab "@indexfast"

# 7. Daily automated scheduler
npm run schedule:dry-run
npm run schedule:publish
```
