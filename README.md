# reels-shorts

Spec in, published short out. A JSON spec is turned into a narrated, word-synced motion-graphics video by the Kinetic Video Engine, checked, archived to Google Drive, recorded in a Google Sheet and posted to Instagram and YouTube at its scheduled time.

- Channels: StackShade (`@stackshade`) and IndexFast (`@indexfast`).
- Two looks: `brutal` (bold chapters and numbers) and `clean` (word-by-word captions and diagrams), recoloured per brand.
- 76 agent skills for motion design, video tooling and distribution in `skills/` (see `skills/INDEX.md`).

Quick start:

```bash
npm install && npx playwright install chromium-headless-shell
python3.11 -m pip install edge-tts faster-whisper numpy
python3.11 ops/make.py specs/stackshade/SS-101.json --stills 0.3,7,14   # preview
python3.11 ops/make.py specs/stackshade/SS-101.json --no-sync           # render + verify
```

Read `SKILL.md` for the full workflow and `AGENTS.md` for accounts, commands and rules.

Credits: engine from the Kinetic Video Engine artifact; fonts are Google Fonts under the OFL; third-party skills keep their own licenses, listed in `skills/INDEX.md`.
