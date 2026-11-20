# CraftLayer Studio: Instagram playbook

Account: `@craftlayer.studio` (Composio `instagram_hinoki-scrape`). Sheet tab: `@craftlayer`. Plan and scripts: `brands/craftlayer/plan.json`, mirrored to the "CraftLayer · Reels plan" Google Sheet by `ops/plan_sheet.py`.

Goal: local business owners in India see a reel about their own problem, believe we can fix it, and send a DM, comment a keyword or email. Followers matter less than enquiries.

## What the three reference reels taught us

Three WebSoln Labs reels (Hindi voiceover, product-demo style) were analysed. Frames and transcripts are in `reference/websolnlabs/`, which is git-ignored.

| Reel | Length | Structure | Why it works |
|---|---|---|---|
| Restaurant software | 93 s | Hook ("your waiter can't be at every table, your website can"), then 10 short chapters, one screen each, then a "comment SOFTWARE" CTA | One concrete promise in the first 3 s. Every chapter shows a real screen. The comment keyword turns viewers into leads. |
| Cafe Instagram | 55 s | "If I handled your cafe's Instagram, day one would look like this", then a checklist | A personal "if I did it for you" frame and a visible checklist. Ends on a WhatsApp number. |
| Website is a net | 49 s | A contrarian truth from a web agency ("a website alone won't bring customers"), a net-and-water metaphor, then "comment 'pata nahi'" | Honesty earns trust. The metaphor is easy to retell. The comment answer is easy to type. |

Common pattern: Hinglish voiceover, short Roman-script captions shown word by word, one accent colour, a small chapter label, the brand mark always visible, and an easy comment or DM ask at the end.

## How Instagram ranks reels (what we can act on)

Instagram's head, Adam Mosseri, has said the main signals for reels are watch time, likes per reach and sends per reach. Original content is favoured over reposts. Nobody can promise that a reel goes viral, so we work on the signals we control:

| Signal | What we do |
|---|---|
| First 3 seconds | Frame 1 already shows the hook as big text plus a visual. Never a logo intro. |
| Watch time and completion | 35 to 60 s for most reels. One idea per chapter, 4 to 7 s each. Every chapter changes the visual. |
| Sends | Name one business type, so viewers think of a friend who owns one. Add "send this to a gym owner you know" in captions. |
| Comments | A one-word keyword CTA (DEMO, GYM, GOLD). Reply to every comment within the first hour and DM the person. |
| Saves | Checklists and "3 problems" lists are worth saving. |
| Originality | Everything is our own render, voice and script. Never repost someone else's video or audio. |
| Search | Keyword-first captions ("gym management software", "restaurant QR menu") and 5 to 8 relevant hashtags. |

Manual steps that the API cannot do:
- Pin the best 3 reels.
- Use Trial Reels for the English versions, so they reach non-followers first.
- Add a location tag.
- Answer comments.
- Set the bio link to `https://craftlayer-studio.github.io/`.

## The reel formula

1. **Hook (0 to 3 s).** The owner's pain in their own words, as a question or a surprising line, with a big text card on frame 1.
2. **Problem, then fix, three times.** Show the problem as a screen or chat, then the fix as a screen.
3. **Recap checklist.** Three to five ticks.
4. **CTA.** A comment keyword, a DM, or email `sh20raj@gmail.com`. Optionally add "send this to a ___ owner".

Voice and pacing (since 2026-11-20, after owner feedback that the edge-tts Hindi voice was slow and flat):
- English narration with Kokoro-82M, voice `af_heart` at speed 1.2. That is about 3.3 words a second, with no dead air between scenes (gap 0.05 s).
- Captions show 2 or 3 words at a time, in uppercase. Each word pops in as it is spoken, and the live word is in the accent colour.
- Every accent word gives the camera a short punch-in. Scenes change with a 0.16 s whip zoom, and nothing takes longer than 0.32 s to enter.
- Hindi stays possible in the engine. It needs a better voice first: ElevenLabs (needs a key) or Kokoro Hindi (needs espeak-ng, which this host cannot load).

## Honesty rules (from the studio's brand guidelines)

- Concept demos (Juniper Kitchen, Brightwater Coffee, Forge Fitness and the rest) carry the "CONCEPT DEMO" badge. Never call them clients.
- No invented clients, testimonials, metrics, follower counts or "trusted by".
- Prices on screen belong to the fictional demo business. Market data (gold rates and similar) stays masked (`₹ ••,•••`).
- Say "we can build this". Never say "our software is used by".
- Every caption ends with "Voiceover is AI-generated."

## Cadence

- 1 reel a day at 19:30 IST (`max_reels_per_day: 1`). The scheduler enforces it. `ops/scheduler.py --publish --now <ids>` overrides it when the owner asks to post now.
- Rotate formats so the feed never looks the same two days running: 3 problems, then system walkthrough, then a feature reel.
- Weekly: run `python3.11 ops/ig_report.py craftlayer --sheet` (after adding an insights tab), keep what gets sends and comments, and cut what does not.

## Making a reel

```bash
# 1. copy the closest spec (CR-104 for "3 problems") and edit say/show/vis
# 2. preview
python3.11 ops/make.py specs/craftlayer/CR-106.json --lang hi --stills 0.3,6,12,18,24
# 3. render, check, Drive + sheet row (status Ready, posted by cron at meta.schedule)
python3.11 ops/make.py specs/craftlayer/CR-106.json --lang hi
python3.11 ops/make.py specs/craftlayer/CR-106.json --lang en
```

In the Hindi `say` text, English product words stay in Latin script ("website", "WhatsApp"). The `show` text is the same sentence in Roman Hinglish with the same number of words. Wrap accent words in `*stars*`. Visual cues use `"at": "40%"` (a share of the scene's voice), so one spec drives both languages.
