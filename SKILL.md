---
name: reels-shorts-studio
description: Make a narrated motion-graphics Reel or Short for StackShade or IndexFast with the Kinetic Video Engine in this repo, then archive it to Drive, record it in the Google Sheet and schedule it for automatic publishing. Use for any request to create, re-render, schedule or publish a video for these channels, or to add a new channel.
---

# Reels and Shorts studio

One video = one spec file. Follow the steps in order. `AGENTS.md` has the accounts, commands and rules; `skills/kinetic-explainer-video/SKILL.md` is the full element reference for the engine.

## 1. Pick the topic and the brand

Read `brands/<brand>/brand.md`. Check `python3.11 ops/sheet.py --show` so the topic and the Video ID are new. IDs are `<PREFIX>-<number>`: `SS-104`, `IF-103`.

## 2. Research

Open a primary source (official docs, the spec, the vendor's own page) and keep the URL. Write down the exact numbers and sentences you will use. Anything you cannot find in a source stays out of the video.

## 3. Script

- 40 to 60 seconds, 105 to 150 spoken words, 7 to 10 scenes, one idea per scene.
- Scene 1 is the hook: the most surprising concrete fact or promise, readable in the first second. Its elements use negative cues (`"at": -0.3`) so frame 1 is already full.
- Write numbers the way they are spoken ("ten thousand"); put the digits on screen.
- Last scene: one call to action from `brand.json` (`cta`). Never promise something that does not exist.
- For hook, pacing and caption craft read `skills/motion/short-form-video`, `skills/motion/kinetic-typography`, `skills/motion/caption-animation` and `skills/marketing/social/references/short-form-video.md`.

## 4. Write the spec

Save to `specs/<brand>/<ID>.json`. Copy the closest existing spec and edit it.

```json
{
  "title": "...", "style": "brutal", "format": "short", "series": "HEADER LABEL",
  "meta": {
    "id": "SS-104", "brand": "stackshade", "topic": "Category / Topic", "schedule": "2026-11-23 19:00",
    "yt_title": "... #shorts", "yt_tags": ["...", "..."], "yt_description": "hook line + bullets + hashtags",
    "ig_caption": "hook + emoji bullets + CTA + 'Voiceover is AI-generated.'", "ig_hashtags": ["#..."],
    "sources": ["https://..."]
  },
  "scenes": [ { "chapter": "00 HOOK", "bg": "purple", "say": "...", "els": [ ... ] } ]
}
```

- `style`: `showcase` (dark or `"light": true` product demo: phones, tablets, browser, floor plan, QR, chips, checklist, orbit, net/water metaphors; Roman captions over any voice language; used by CraftLayer; read `engine/styles/showcase.js` for element and screen-block options), `brutal` (numbered chapters, flat colour, condensed caps; best for numbers, news, comparisons) or `clean` (word-by-word captions, app tiles, diagrams; best for how-it-works). Alternate between them so the feed does not look the same every day.
- Voice, music and colours come from `brands/<brand>/brand.json`. Set `voice`, `music` or `theme` in the spec only to override them for one video.
- `meta.schedule` is IST, `YYYY-MM-DD HH:MM`. Use the brand's `slots_ist` and the next free day.
- Every element has `at`: a phrase copied from that scene's `say`, or seconds from the scene start. A cue must be whole spoken words.
- Titles: 100 characters or fewer, keyword first. Tags: 10 to 15. `make.py` appends the sources and the AI-voice line to the YouTube description.

Layout notes learned from this repo's videos:
- `brutal` `vs` cards fit about 6 characters in `value`; longer words are clipped.
- `brutal` `serif` cards fit about 26 characters on one line.
- `clean` `card` draws a fake repository README with buttons; use `big`, `label` or an `icon` with `label` for code snippets instead.
- In `clean`, a caption can show digits while the voice says words, but its words must stay in spoken order.

## 5. Look before rendering

```bash
python3.11 ops/make.py specs/<brand>/<ID>.json --stills 0.3,7,14,21,28,35,42
```
Read the `still_*.jpg` files in `out/<brand>/<ID>/`. Fix clipping, overlap, an empty first frame, wrong order. Repeat until clean.

## 6. Render and verify

```bash
python3.11 ops/make.py specs/<brand>/<ID>.json --no-sync
```
It renders (about 2 minutes), writes `contact.jpg`, and checks resolution, frame rate, codecs, duration, size and loudness. Read `contact.jpg`. For a first video in a new voice, also run `engine/check.py <mp4> --transcribe` and compare the transcript with the script.

## 7. Archive, record, schedule

```bash
python3.11 ops/make.py specs/<brand>/<ID>.json --sync-only
```
Uploads the MP4 to a new Drive folder, then writes the sheet row with status `Ready` and the schedule time. The cron job posts it when the time comes. Check with `python3.11 ops/sheet.py --show` and `python3.11 ops/scheduler.py --dry-run`.

## 8. Commit

Commit the spec and `out/<brand>/<ID>/` (MP4, thumb, captions, contact sheet). Report the Video ID, schedule time, Drive link and the YouTube title, description and tags.

## Reels Studio

Everything above can also be done in the web dashboard (`studio/README.md`): the Library shows each reel's row, player, stills and contact sheet; Jobs runs `make.py` (stills, render, sync) and `gen_reels.py` with a live log; the Calendar reschedules by drag; Publish posts one reel now through the scheduler. Agents use the same JSON API with a bearer token, for example `curl -H "Authorization: Bearer $TOKEN" http://127.0.0.1:4820/api/reels?brand=craftlayer`. Step 5 (looking at the stills) still applies: open them in the reel's drawer or in `out/`.

## Bilingual specs (Hindi + English)

Add `"langs": {"hi": {}, "en": {}}`. Any value can then be `{"hi": ..., "en": ...}` (say, titles, captions, schedule). For Hindi, `say` is Devanagari with English product words in Latin script, and `show` is the same sentence in Roman Hinglish with exactly the same number of words; captions show `show`, timed to the Hindi audio. Mark accent words with `*stars*`. Cue visuals with `"at": "40%"` of the scene's voice so both languages line up. Build each with `--lang hi` / `--lang en`; the brand's `voices` picks the voice per language.

## Other formats

- 16:9 long-form: `"format": "long"`, 3 to 8 minutes, chapters of 2 to 5 scenes. `make.py` skips the short-duration check.
- A look the engine cannot draw (3D, footage, maps): see `skills/INDEX.md` for the HyperFrames, Remotion, Manim and ffmpeg skills, render there, then use `ops/drive.py`, `ops/sheet.py` and the publishers directly.
