---
name: kinetic-explainer-video
description: Make kinetic-typography explainer videos (YouTube Shorts, Reels or long-form) with AI voice, word-synced motion graphics, music and SFX, plus a ready-to-paste YouTube title, description and tags. Use for short, reel or explainer video requests and StackShade videos.
---

# Kinetic explainer videos

Two house styles, both rendered frame-exact from one JSON spec:

| style | look | best for |
|---|---|---|
| `brutal` | Numbered chapters (`01 PRICE`), flat violet/mint/pink/black/paper backgrounds that change per chapter, condensed caps, highlighter tags, paper cards with hard offset shadows, giant outlined chapter word at the bottom. Elements pop in on their cue word. Quiet pulse music. | news, launches, reports, numbers |
| `clean` | Off-white canvas, captions revealed word by word as they are spoken (grey to black), soft-shadow app tiles, dashed connector trees, starred check lists, orange accent rings, brand watermark. Upbeat bed. | tools, tutorials, "how it works", hype shorts |

Output: 1080x1920 (`"format":"short"`) or 1920x1080 (`"format":"long"`), 30 fps, H.264, AAC, -14 LUFS, plus `captions.srt` and `thumb.jpg`.

## 1. Get the engine

The engine is a folder: `engine/` (build.py, tts.py, audio.py, render.cjs, check.py, runtime.js, icons.js, fonts, styles/). Find it in this order:
1. Next to this SKILL.md (`<skill dir>/engine/`). This package bundles it, with example specs in `<skill dir>/specs/`.
2. Otherwise fetch it from the published engine artifact https://claude.ai/artifact/1GStrduxLshxmGkv1isa7G with the Artifact tool:
   `Artifact(action="read", url=https://claude.ai/artifact/1GStrduxLshxmGkv1isa7G, paths=[...every path in MANIFEST.txt...], out_dir="<workdir>/kv")`
   (read `MANIFEST.txt` first with `path="MANIFEST.txt"`). Files land at `<workdir>/kv/<path>`. The artifact is private: it opens only for its owner and people it was shared with.
3. If neither works, stop and say the engine is unavailable. Do not rebuild it from memory.

The skill folder can be read-only, and renders write next to the engine. Copy it to a writable work folder first and call that copy `<kv>`:
```bash
mkdir -p <workdir>/kv && cp -r <skill dir>/engine <skill dir>/specs <workdir>/kv/
```

Setup (once per container):
```bash
pip install --break-system-packages -q edge-tts faster-whisper numpy
cd <kv>/engine && ls fonts/*.woff2 >/dev/null 2>&1 || python3 fetch_fonts.py   # fonts are bundled; this only runs if they are missing
node -e "require('playwright')"   # Chromium + Playwright are preinstalled in Claude cloud workspaces
# If that fails: npm i -g playwright && npx playwright install --with-deps chromium
```
Network: the voice step calls Microsoft's speech service (edge-tts), and `check.py --transcribe` downloads a Whisper model once. If the sandbox blocks those hosts, say so and ask the user to allow network access for the session. If a TLS proxy is in front of the network, export `SSL_CERT_FILE=<its CA bundle>` before building.

## 2. Research and script

- Facts come from sources you opened this session (a primary source when one exists). Every number on screen must be in the source, with the same meaning. Keep the source URL for the description.
- Shorts: 45-60 s, 120-150 spoken words, 7-10 scenes. Long-form: 3-8 min, 6-12 chapters of 2-5 scenes, 16:9.
- Scene 1 is the hook: the most surprising concrete fact or promise in under 2 s. Its elements use negative cues (`"at": -0.3`) so frame 1 is already full.
- One idea per scene, one sentence or two. Write numbers the way they should be spoken ("seventeen point nine billion"); put the digits on screen.
- End with a single CTA ("Follow <channel> for more"). Never promise a giveaway, guide or reply that does not exist.

## 3. Write the spec

```json
{
  "title": "...", "slug": "file_name", "style": "brutal", "format": "short",
  "series": "OCTOVERSE 2026",            // brutal: header label right
  "brand": "stackshade",                  // clean: watermark
  "voice": {"engine": "edge", "name": "en-US-AndrewNeural", "rate": "+7%"},
  "music": "pulse", "music_db": -22, "sfx_db": -10, "gap": 0.14,
  "scenes": [ { "chapter": "01 AGENTS", "bg": "black", "say": "...", "els": [ ... ] } ]
}
```
Voices (free, word timestamps built in): `en-US-AndrewNeural` (warm news), `en-US-BrianNeural` (casual hype, use rate +12..+18%), `en-US-ChristopherNeural` / `en-US-GuyNeural` (anchor), `en-US-AvaNeural` / `en-US-EmmaNeural` (female), `en-IN-PrabhatNeural` / `en-IN-NeerjaNeural` (Indian English). A recorded or ElevenLabs file per scene: `"voice_file": "path.mp3"` on the scene (timed with Whisper).
Music: `pulse` (quiet electronic), `bright` (upbeat), `none`. Everything is synthesised, so there is nothing to license.

**Cues.** Every element takes `at`: a phrase copied from that scene's `say` ("ten times", "Python"); `"phrase#2"` for its 2nd occurrence; or a number of seconds from the scene's first word. A cue word must be a whole spoken token: "thirty-eight" is one token, so cue "point three" instead of "eight point three". The build prints `WARN cue ... not found` with the scene's words; fix every warning.

### brutal elements (`els`)
Backgrounds `bg`: purple, mint, pink, black, paper. Colours: mint, pink, purple, black, white, paper, yellow. Text markup: `[[accent]]`, `{{highlight box}}`, `**bold**`, `\n`.
- `kicker {text}` small caps line · `note {text}` · `headline {text,size?,color?}` condensed display, auto-fits width · `stat {text,size?,color?,count:{from,to,decimals,prefix,suffix}}` big number that counts up
- `tag {text,color,size?,rot?}` highlighter label · `tags {items:[{text,color,at}],quote?}` stacked labels · `stamp {text,color,size,rot,burst?}` tilted stamp
- `label {text,variant:dark|mint|pink}` small paper label · `serif {text}` paper card in serif
- `bigmono {text,from?}` mono number that scrambles from `from` · `type {text,prefix?}` typed code
- `bars {items:[{label,value,text,color,big?,ghost?,at}],max,h,bw}` · `chart {series:[{name,color,pts:[[x,y,"label"]]}],ymin,ymax,yticks}` line chart card (label invented curves "ILLUSTRATIVE")
- `table {rows:[{k,v,sub?,at}],w}` · `timeline {items:[{date,title,chips,at}]}` · `tree {root,items:[{small,text,color,icon,at}]}` · `grid {items:[{title,icon,at}]}` 2x2 · `segmented {items,active,moveTo,moveAt,note}` · `vs {left:{small,value},right:{small,value,at},sym}`
- `collage {w,h,tiles:[{x,y,w,h,kind:sunset|ember|spheres|yellow|violet|mint|grain|paper,rot}]}` abstract textures · `icon {name,size,bg,color}` · `badge {text}` · `squiggle` · `magnifier`
- Layout: `row {children,gap,align}`, `col {children}`, `spacer {h}`; any element: `mt`, `ml`, `rot`, `w`, `abs:[x,y]` (portrait only).
Scenes sharing a `chapter` cut; a new chapter slides in with a whoosh.

### clean scenes
`cap`: caption segments `{text,size:s|m|l|xl,pos:top|bottom,style:"pill"?,color:"accent"?,upper?}`; their words must follow `say` in order (they are timed word by word). `"cap": []` = no captions. `vis`: visuals in the middle:
`icon {icon,tile:dark|light|orange|blue|none,size,label?,fillAt?}` · `tiles {items:[{text|icon,tile,at}],size,wrap?}` · `tree {root:{icon|text,tile},items:[...]}` dashed tree · `bridge {from,items}` lines to a column · `checklist {items:[{text,at}],size}` · `card {title}` dark README card · `ocard {title,sub,icons}` · `book {title,sub}` (`*word*` = accent) · `pages` · `big {text,color}` · `label {text}` · `row {children}`. Scene `splash`: "tl,br" orange rings in corners.
Icons (generic, both styles): terminal branch cloud bolt code chip globe check bookmark cursor spark doc users shield router layers book star lock gauge trend server eye search play pr.

**Never draw logos, mascots or brand marks** (company logos, app icons, characters). Use product names as text and the generic icons above.

## 4. Look, then render

```bash
cd <kv>/engine
python3 build.py spec.json --out out/<slug> --stills 0.2,4,9,15 --stills-only   # still_*.jpg in 30-60 s
python3 build.py spec.json --out out/<slug>                                     # full render, ~4 min per video minute
python3 build.py spec.json --out out/<slug> --only 0,3                          # re-render only those scenes (same voice timing)
python3 check.py out/<slug>/<slug>.mp4 --transcribe                             # loudness, contact.jpg, transcript
```
Look at the stills and `contact.jpg` with Read. Fix: overlapping or clipped text, empty first frame, elements appearing in the wrong order, a cue that fires on the wrong word. Check the transcript against the script (Whisper may mis-hear names; trust the larger model).

## 5. Always hand over the YouTube metadata

The user asked (1 Nov 2026) for the title, description and tags with EVERY video, uploaded or not. End every delivery with one ready-to-paste block:
- **Title:** 100 characters or fewer, main keyword first; Shorts end with `#shorts`.
- **Description:** a hook line, the facts as bullets, every source URL, "Voiceover is AI-generated.", then 3-5 hashtags.
- **Tags:** 10-15 comma-separated tags, broad plus long-tail, under 500 characters in total.
- **Category:** Science & Technology (28).

## 6. Publish to YouTube (Composio)

> **Warning (30 Oct 2026):** YouTube deleted every video uploaded to StackShade through Composio's YouTube connection within minutes (25-26 Oct and 30 Oct), while manual uploads stayed up. Unless the user says this is fixed, do NOT upload to YouTube through Composio: send the MP4 plus a ready-to-paste title, description and tags so the user uploads it from the YouTube app. Instagram Reels via Composio work (account id `instagram_give-oii`, @indexfast, ig_user_id 29263285359956214: presigned slot -> INSTAGRAM_POST_IG_USER_MEDIA with media_type REELS and video_file s3key -> INSTAGRAM_POST_IG_USER_MEDIA_PUBLISH; write hashtags as %23tag).

The account ids in this section belong to the StackShade owner's Composio. In any other Claude account, use only the Composio connections that account has, and never assume these ids exist.

1. Find the channel account: `COMPOSIO_SEARCH_TOOLS` for "upload a video to youtube"; the YouTube toolkit lists accounts. StackShade = account id `youtube_run-retin` (channel UCEoKWUYSnfJw6as6vl9MeBQ, @stackshade). Always pass `account`.
2. Put the file in Composio storage. In `COMPOSIO_REMOTE_WORKBENCH` run:
   ```python
   import os, requests
   r = requests.post(os.environ.get("BACKEND_URL","https://backend.composio.dev") + "/api/v3/tool_router/internal/presigned_url", json={"operation":"upload"})
   print(r.json())   # upload_url (1 h) + key
   ```
   then from the local shell: `curl -sS -X PUT -H "Content-Type: video/mp4" --upload-file <mp4> "<upload_url>"` (expect 200).
3. `YOUTUBE_UPLOAD_VIDEO` with `videoFilePath: {name, mimetype:"video/mp4", s3key:<key>}`, `title` (<=100 chars, add `#shorts` for Shorts), `description` (facts as bullets, the source URL, "Voiceover is AI-generated.", hashtags), `tags`, `categoryId:"28"` (Science & Technology), `privacyStatus:"public"`.
4. A 429 `Video Uploads per day` error is Composio's shared Google quota; it resets at midnight Pacific (12:30 IST). Retry once with `YOUTUBE_MULTIPART_UPLOAD_VIDEO`; if it fails too, schedule a retry after the reset and tell the user. Report the video URL `https://youtube.com/shorts/<id>` (or `watch?v=`) when it succeeds.
