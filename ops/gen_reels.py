#!/usr/bin/env python3.11
"""Turn compact "3 problems" reel scripts into full showcase specs.

  python3.11 ops/gen_reels.py brands/craftlayer/scripts/*.json        # writes specs/craftlayer/<id>.json
  python3.11 ops/gen_reels.py ... --start "2026-11-23 19:30"           # schedule one a day from this slot

Script format and writing rules: brands/craftlayer/reel_schema.md. The generator picks devices, tilts, chip
positions and theme so consecutive reels never look the same: phone and tablet for problems, phone and browser
for fixes, every third reel on the light theme.
"""
import argparse, datetime as dt, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
BAD, GOOD = "#FF6B4A", "#465FFF"


def words(s):
    return len(re.sub(r"[*]", "", s).split())


def chip(t, ic, at, left, dark=False):
    return {"type": "chips", **({"dark": True} if dark else {}),
            "items": [{"t": t, "ic": ic, "x": 30 if left else 400, "y": 600 if left else 560, "at": at}]}


def screen_problem(p, demo):
    head = {"k": "head", "kick": demo, "t": p["head"]}
    if p.get("screen") == "chat":
        n = len(p["chat"])
        msgs = [{"t": m["t"], **({"me": True} if m.get("me") else {}), "at": f"{10 + i * (55 // max(1, n - 1 or 1))}%"} for i, m in enumerate(p["chat"])]
        return {"bg": "#EFE9E1", "blocks": [head, {"k": "chat", "msgs": msgs}]}
    items = [{"t": r["t"], "s": r.get("s", ""), **({"v": r["v"]} if r.get("v") else {}), "ic": r.get("ic", "users"),
              **({"c": BAD} if r.get("bad") else {})} for r in p["rows"]]
    return {"blocks": [head, {"k": "rows", "stagger": 0.18, "items": items}]}


def screen_fix(f, domain):
    items = [{"t": r["t"], "s": r.get("s", ""), **({"v": r["v"]} if r.get("v") else {}), "ic": r.get("ic", "check"), "c": r.get("c", GOOD)}
             for r in f.get("rows", [])]
    blocks = [{"k": "head", "kick": domain, "t": f["head"], **({"s": f["sub"]} if f.get("sub") else {})}]
    if items:
        blocks.append({"k": "rows", "stagger": 0.15, "items": items})
    if f.get("btn"):
        blocks.append({"k": "btn", "t": f["btn"], "grow": True})
    return {"blocks": blocks}


def spec_for(r, n, when):
    demo, domain = r["demo_name"], r.get("domain", "")
    M = {**{"hook": "excited", "problem": "frustrated", "fix": "confident", "recap": "upbeat", "cta": "warm"}, **r.get("moods", {})}
    scenes = [{"chapter": "00 · Hook", "mood": M["hook"], "say": r["hook"]["say"], "vis": [
        {"type": "title", "at": -0.4, "anim": "none", "size": 60, "text": r["hook"]["title"]},
        {"type": "row", "at": -0.4, "gap": 60, "children": [
            {"type": "tile", "ic": t.get("ic", "users"), "size": 170, "label": t["label"],
             **({"c": GOOD} if t.get("hot") else {}), **({"anim": "none"} if i == 0 else {"at": "55%"})}
            for i, t in enumerate(r["hook"]["tiles"][:2])]}]}]
    for i, p in enumerate(r["problems"]):
        side = (i + n) % 2
        tilt = [5, -10, 0] if side else [5, 10, 0]
        if i == 1 and p.get("screen") != "chat":
            dev = {"type": "tablet", "w": 620, "tilt": [10, 0, 0], "at": "0%", "screen": screen_problem(p, demo)}
        else:
            dev = {"type": "phone", "w": 320, "tilt": tilt, "at": "0%", "screen": screen_problem(p, demo)}
        vis = [dev] + ([chip(p["chip"], "bell", "60%", not side, dark=True)] if p.get("chip") else [])
        scenes.append({"chapter": f"0{i + 1} · Problem", "mood": M["problem"], "say": p["say"], "vis": vis})
        f = p["fix"]
        if i == 1:
            dev = {"type": "browser", "w": 560, "url": domain or "yourbusiness.in", "at": "0%", "screen": screen_fix(f, domain)}
        else:
            dev = {"type": "phone", "w": 320, "tilt": [5, 10, 0] if side else [5, -10, 0], "at": "0%", "screen": screen_fix(f, domain)}
        vis = [dev] + ([chip(f["chip"], "check", "65%", side)] if f.get("chip") else [])
        scenes.append({"chapter": f"0{i + 1} · Fix", "mood": M["fix"], "say": f["say"], "vis": vis})
    scenes.append({"chapter": "04 · System", "mood": M["recap"], "say": r["recap_say"], "vis": [
        {"type": "steps", "at": "0%", "title": f"CraftLayer · {r['audience']} system",
         "items": [{"t": x["t"], "s": x.get("s", ""), "at": f"{2 + 24 * j}%"} for j, x in enumerate(r["recap"][:3])]}]})
    kw = r["keyword"]
    scenes.append({"chapter": f"05 · {kw}", "mood": M["cta"], "say": r["cta_say"], "vis": [
        {"type": "logo", "at": "0%", "size": 150, "sub": "Websites · Apps · Systems"},
        {"type": "cta", "at": "25%", "text": kw, "label": f"Comment *{kw}*", "mt": 24}]})
    cap = r["caption"]
    if "AI-generated" not in cap:
        cap += "\n\nVoiceover is AI-generated."
    spec = {"title": r["topic"], "style": "showcase", "format": "short", "badge": "CONCEPT DEMO",
            **({"light": True} if n % 3 == 2 else {}), "langs": {"en": {}},
            "meta": {"id": r["id"], "brand": "craftlayer", "topic": r["topic"], "schedule": {"en": when},
                     "yt_title": {"en": r["hook"]["title"].replace("*", "").replace("\n", " ") + " #shorts"},
                     "yt_tags": r.get("tags", []), "yt_description": {"en": cap.split("\n")[0]},
                     "ig_caption": {"en": cap}, "ig_hashtags": r.get("hashtags", []), "sources": r.get("sources", [])},
            "scenes": scenes}
    if r.get("voice"):
        spec["voice"] = r["voice"]
    if r.get("theme"):
        spec["theme"] = r["theme"]
    return spec


def check(r):
    errs = []
    if len(r.get("problems", [])) != 3:
        errs.append("needs 3 problems")
    says = [r["hook"]["say"], r["recap_say"], r["cta_say"]] + [x for p in r["problems"] for x in (p["say"], p["fix"]["say"])]
    tot = sum(words(s) for s in says)
    if not 95 <= tot <= 155:
        errs.append(f"{tot} spoken words")
    if re.search(r"\d+\s?%", " ".join(says)):
        errs.append("percentage in voice")
    return errs, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--start", default="2026-11-23 19:30")
    ap.add_argument("--now", default="", help="comma-separated ids posted today; the rest fill one slot a day")
    a = ap.parse_args()
    reels = [r for f in a.files for r in json.load(open(f))]
    reels.sort(key=lambda r: r["id"])
    t0 = dt.datetime.strptime(a.start, "%Y-%m-%d %H:%M")
    bad, now, k = 0, set(filter(None, a.now.split(","))), 0
    for n, r in enumerate(reels):
        errs, tot = check(r)
        if r["id"] in now:
            when = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
        else:
            when = (t0 + dt.timedelta(days=k)).strftime("%Y-%m-%d %H:%M"); k += 1
        out = ROOT / "specs" / "craftlayer" / f"{r['id']}.json"
        out.write_text(json.dumps(spec_for(r, n, when), indent=1, ensure_ascii=False) + "\n")
        print(f"{r['id']}  {tot:3d} words  {when}  {r['topic']}" + (f"  !! {'; '.join(errs)}" if errs else ""))
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
