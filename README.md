# Reels & Shorts Automated Production Engine

Automated programmatic video production and daily publishing pipeline for vertical short-form video (Instagram Reels & YouTube Shorts), supporting:
- **StackShade** ([@stackshade](https://www.instagram.com/stackshade/) / [@StackShade](https://www.youtube.com/@StackShade/shorts)): Computer engineering, system design, and AI tech alerts.
- **IndexFast** ([@indexfast](https://www.instagram.com/indexfast/) / [indexfast.co](https://indexfast.co)): Google indexing automation, crawl budget optimization, and programmatic SEO.

---

## ⚡ Core Capabilities

- **Code-Driven Video Generation**: 1080x1920 @ 30 FPS vertical video rendered frame-by-frame using HTML5 Canvas, GSAP, and Headless Chrome.
- **Synthesized Audio Bed**: Built-in Web Audio synthesis generating techno beats, kicks, and scene drops with zero licensing risk.
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

## 🎬 Current Deliverables

| Video ID | Brand | Category | Title | Duration | File Size | Direct MP4 Download | Status |
|---|---|---|---|---|---|---|---|
| **SS-001** | StackShade | System Design | *Why Redis is 100x Faster Than MySQL* | 15s | 2.06 MB | [Direct Download](https://drive.google.com/uc?id=1jHBDMuIZe1ypmkxJqPBrX7vU93bfGOfb&export=download) | Verified & Synced |
| **SS-002** | StackShade | AI Engineering | *How AI Agents Actually Code (ReAct Loop)* | 15s | 1.95 MB | [Direct Download](https://drive.google.com/uc?id=1FvVUeOlOfC9N6DvtgOkZlkdD2q_um9gX&export=download) | Verified & Synced |
| **SS-003** | StackShade | News & Cyber Alert | *3 Critical AI Security Hacks Exposed This Week* | 15s | 2.14 MB | [Direct Download](https://drive.google.com/uc?id=1B94hhK6SIyI0r07ETefXxeKbvtWKnPnC&export=download) | Verified & Synced |
| **IF-001** | IndexFast | SEO Automation | *Why Google Takes 3 Weeks to Index (24h Fix)* | 15s | 1.98 MB | [Direct Download](https://drive.google.com/uc?id=1VsnKYyVzthj952M0CDa5bXcvtR94WTxT&export=download) | Verified & Synced |

---

## 🚀 Commands Reference

```bash
# 1. Preview contact sheet
npm run render -- brands/stackshade/reels/2026-11-17-redis-vs-mysql/src/reel.html brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/sheet.jpg --sheet 2

# 2. Render final MP4
npm run render -- brands/stackshade/reels/2026-11-17-redis-vs-mysql/src/reel.html brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/final.mp4

# 3. Stream binary video to Google Drive (resumable upload, verification & direct link generation)
npm run drive:sync -- brands/stackshade/reels/2026-11-17-redis-vs-mysql

# 4. Sync metadata to Google Sheet with strict file validation
npm run sheet:sync -- --add-json brands/stackshade/reels/2026-11-17-redis-vs-mysql/out/metadata.json --tab "@StackShade"

# 5. Beautify Google Sheet tabs (frozen headers, dark theme, column widths)
npm run sheet:beautify -- --tab "@StackShade"
npm run sheet:beautify -- --tab "@indexfast"

# 6. Run daily scheduler dry-run (checks queue and planned slots)
npm run schedule:dry-run

# 7. Execute daily publishing cycle (publishes to Instagram via Composio and updates sheets)
npm run schedule:publish
```
