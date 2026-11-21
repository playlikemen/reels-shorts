# SFX bank

Takes for the engine's cue kinds (`whoosh`, `pop`, `tick`, `ding`, `riser`, `stamp`), used when a spec or brand style
sets `"sfx_pack": "<folder>"`. Each cue rotates through `<kind>_1.wav`, `<kind>_2.wav`, ... so repeated pops do not
sound identical. Missing kinds fall back to the synthesized cue in `engine/audio.py`. Levels are matched to the
synthesized cue, so `sfx_db` keeps working.

`earshot/` was rendered on the CPU with [earshot](https://github.com/Leonxlnx/earshot) (MIT; the sounds it renders are
the user's to use):

```bash
python3.11 -m pip install --user "earshot @ git+https://github.com/Leonxlnx/earshot"
earshot make "three variations of a fast short whoosh for a motion graphics transition" -o whoosh.wav
earshot make "three variations of a soft bubbly interface pop" -o pop.wav
earshot make "three variations of a crisp short ui tick" -o tick.wav
earshot make "three variations of a bright success chime" -o ding.wav
earshot make "three variations of a short tension riser" -o riser.wav   # then trimmed to 1.6 s around the peak
earshot make "three variations of a punchy impact hit" -o stamp.wav
```
