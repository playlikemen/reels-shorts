# Daily Reel & Short Runbook (@StackShade)

This runbook documents the daily autonomous pipeline to generate, render, verify, archive to Google Drive, record in Google Sheets, and publish high-retention video reels for **StackShade** on Instagram and YouTube Shorts.

---

## 1. Topic & Script Selection

1. Review `brands/stackshade/calendar.csv` and `brands/stackshade/brand.md`.
2. Pick an unproduced hook from the content calendar or propose a high-value engineering concept (System Design, Backend, AI Engineering, DSA).
3. Verify that the hook is readable within the first **0.8 seconds**.
4. Check that all facts, metrics, and diagrams are technically accurate and follow the guidelines in `brands/stackshade/brand.md`.

---

## 2. Reel Authoring & Composition

1. Create a reel directory under `brands/stackshade/reels/<YYYY-MM-DD>-<slug>/`:
   - `brief.md`: Hook, target audience, technical breakdown, timeline cues.
   - `src/reel.html`: Canvas/GSAP/HyperFrames visual composition driven by `draw(t)`.
   - `out/caption.txt`: Hook line, 3-4 bullet explanation, CTA, and 8-12 relevant hashtags.
   - `out/metadata.json`: Video ID, title, topic, duration, status flags.
2. Ensure layout adheres strictly to safe areas:
   - **Top 250 px**: Keep clear of titles and primary text (UI overlay).
   - **Bottom 420 px**: Keep clear of key graphics and captions (audio & profile overlay).
   - **Resolution**: Exactly `1080x1920` (9:16 vertical).
   - **Duration**: 12 to 30 seconds (360 to 900 frames @ 30 fps).

---

## 3. Rendering & Verification

1. **Generate Contact Sheet**:
   ```bash
   npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/sheet.jpg --sheet 2
   ```
2. **Review Contact Sheet**:
   - Verify text contrast, no clipping inside safe zones, no typos.
3. **Render Full MP4 + Soundtrack**:
   ```bash
   npm run render -- brands/stackshade/reels/<reel_dir>/src/reel.html brands/stackshade/reels/<reel_dir>/out/final.mp4
   ```
4. **Probe Deliverable Specs**:
   - Format: H.264 (`yuv420p` or `yuvj420p`), AAC audio, faststart enabled, file size < 30 MB.

---

## 4. Google Drive Archival

1. Upload the reel directory artifacts (metadata, captions, notes) to Google Drive folder `1upAISpZAnmyDDYki_FH9tK-FVh_djqLS`:
   ```bash
   npm run drive:sync -- brands/stackshade/reels/<reel_dir>
   ```
2. The script returns the public Google Drive folder link and updates `out/metadata.json`.

---

## 5. Google Sheets Sync

1. Append or update the reel row in the shared tracking spreadsheet:
   - Spreadsheet: [Reels or Shorts](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit)
   - Tab: `@StackShade`
   ```bash
   npm run sheet:sync -- --add-json brands/stackshade/reels/<reel_dir>/out/metadata.json
   ```
2. Verify row status is recorded (`Ready` / `Pending`).

---

## 6. Publishing (Instagram & YouTube)

1. **Instagram Reel**:
   - Host `final.mp4` on a public HTTPS URL (e.g. GitHub raw repo release or cloud storage).
   - Run:
     ```bash
     npm run publish:instagram -- brands/stackshade/reels/<reel_dir> --url <public_video_url>
     ```
   - Target Composio account: `instagram_create-beta` (alias: `stackshade`).
   - Retrieves published permalink and updates Google Sheet status to `Published`.

2. **YouTube Short**:
   - Run:
     ```bash
     npm run publish:youtube -- brands/stackshade/reels/<reel_dir>
     ```
   - Target Composio account: `youtube_run-retin` (alias: `https://www.youtube.com/@StackShade`).
   - Retrieves YouTube video URL and updates Google Sheet status to `Published`.

3. **Log & Audit**:
   - Append execution record to `pipeline/publish-log.jsonl`.
