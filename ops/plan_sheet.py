#!/usr/bin/env python3.11
"""Mirror a brand's content plan and every reel script into its own Google Sheet ("<Brand> · Reels plan").

  python3.11 ops/plan_sheet.py craftlayer            # create the sheet once (id saved in brand.json), then refresh all tabs

Source of truth stays in the repo: brands/<brand>/plan.json and specs/<brand>/*.json. The sheet is rebuilt from them
each run, so edit the files, not the sheet. Tabs: Overview, Made, Scripts, Calendar, Businesses, Features, Formats.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K

TABS = ["Overview", "Made", "Scripts", "Calendar", "Businesses", "Features", "Formats"]


def create(title):
    r = C.execute("GOOGLESHEETS_CREATE_GOOGLE_SHEET1", {"title": title}, K.SHEETS_ACCOUNT)
    sid = r.get("spreadsheetId") or r.get("spreadsheet_id") or (r.get("response_data") or {}).get("spreadsheetId")
    if not sid:
        raise SystemExit(f"could not create sheet: {str(r)[:300]}")
    return sid


def api(sid, body):
    return C.proxy("googlesheets", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}:batchUpdate", "POST", body=body)


def tab_ids(sid):
    r = C.proxy("googlesheets", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}", "GET", params={"fields": "sheets.properties"})
    return {s["properties"]["title"]: s["properties"]["sheetId"] for s in (r.get("data") or r)["sheets"]}


def write(sid, tab, rows):
    C.proxy("googlesheets", f"https://sheets.googleapis.com/v4/spreadsheets/{sid}/values/'{tab}'!A1:Z2000:clear", "POST", body={})
    C.execute("GOOGLESHEETS_VALUES_UPDATE", {"spreadsheet_id": sid, "range": f"'{tab}'!A1", "values": rows,
                                             "value_input_option": "RAW"}, K.SHEETS_ACCOUNT)


def scripts(brand):
    """One row per scene per reel: Hindi voice, Roman caption, English voice."""
    rows = [["Video", "Scene", "Chapter", "Hindi voice (Devanagari + English words)", "Caption (Roman Hinglish)", "English voice"]]
    for f in sorted((K.ROOT / "specs" / brand).glob("*.json")):
        spec = json.load(open(f))
        for i, sc in enumerate(spec["scenes"]):
            say, show = sc.get("say", {}), sc.get("show", {})
            say = say if isinstance(say, dict) else {"en": say}
            show = show if isinstance(show, dict) else {}
            rows.append([spec["meta"]["id"], i, sc.get("chapter", ""), say.get("hi", ""), (show.get("hi") or "").replace("*", ""), say.get("en", "").replace("*", "")])
    return rows


def main(brand):
    b = K.brand(brand)
    plan = json.load(open(K.ROOT / "brands" / brand / "plan.json"))
    sid = b.get("plan_sheet")
    if not sid:
        sid = create(f"{b['name']} · Reels plan")
        bj = K.ROOT / "brands" / brand / "brand.json"
        data = json.load(open(bj)); data["plan_sheet"] = sid
        bj.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        print("created", sid)
    have = tab_ids(sid)
    adds = [{"addSheet": {"properties": {"title": t, "index": i}}} for i, t in enumerate(TABS) if t not in have]
    if adds:
        api(sid, {"requests": adds})
        have = tab_ids(sid)
    extra = [have[t] for t in have if t not in TABS]
    if extra:
        api(sid, {"requests": [{"deleteSheet": {"sheetId": x}} for x in extra]})

    overview = [["CraftLayer Studio · Reels plan", ""],
                ["Updated", plan["updated"]],
                ["Instagram", b["instagram"]["handle"]],
                ["Posting", "1 reel a day at 19:30 IST, English voice (Kokoro). Hindi paused until a better Hindi voice is available"],
                ["Publishing sheet", f"https://docs.google.com/spreadsheets/d/{K.SPREADSHEET_ID} (tab {b['sheet_tab']})"],
                ["Source of truth", "reels-shorts repo: brands/craftlayer/plan.json, playbook.md, specs/craftlayer/*.json"],
                ["Formula", "Hook in 3 s, then problem and fix three times, then a checklist, then a comment keyword or DM"],
                ["Honesty", "Concept demos carry a CONCEPT DEMO badge. No invented clients, metrics or testimonials."],
                ["Ranking signals", "Watch time, likes per reach, sends per reach (Instagram). Originality is favoured."],
                ["Contact CTA", "DM @craftlayer.studio or email sh20raj@gmail.com"]]
    made = [["Video", "Series", "Topic", "Hindi", "English"]] + [[m["id"], m["series"], m["topic"], m["hi"], m["en"]] for m in plan["made"]]
    cal = [["Date", "Time (IST)", "Series", "Topic", "Language", "Status"]] + [[c["date"], c["time"], c["series"], c["topic"], c["lang"], c["status"]] for c in plan["calendar"]]
    biz = [["Business", "Hook (Hinglish)", "Hook (English)", "Problem 1", "Fix 1", "Problem 2", "Fix 2", "Problem 3", "Fix 3", "Comment keyword", "Concept demo"]]
    for x in plan["businesses"]:
        row = [x["business"], x["hook_hi"], x["hook_en"]]
        for p in x["problems"]:
            row += [p["problem"], p["fix"]]
        biz.append(row + [x["keyword"], x["demo"] or "none yet"])
    feats = [["Feature", "Hook (Hinglish)", "Hook (English)", "Source"]] + [[f["feature"], f["hook_hi"], f["hook_en"], f["source"]] for f in plan["features"]]
    forms = [["Format", "What it is", "Style", "CTA"]] + [[f["name"], f["what"], f["style"], f["cta"]] for f in plan["formats"]]
    for tab, rows in [("Overview", overview), ("Made", made), ("Scripts", scripts(brand)), ("Calendar", cal), ("Businesses", biz), ("Features", feats), ("Formats", forms)]:
        write(sid, tab, rows)

    # look: dark header row, frozen header, wrapped text, sensible widths, banded rows
    reqs = []
    ink, band = {"red": 0.063, "green": 0.094, "blue": 0.157}, {"red": 0.95, "green": 0.96, "blue": 1}
    for t in TABS:
        g = have[t]
        reqs += [
            {"updateSheetProperties": {"properties": {"sheetId": g, "gridProperties": {"frozenRowCount": 1}}, "fields": "gridProperties.frozenRowCount"}},
            {"repeatCell": {"range": {"sheetId": g, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"backgroundColor": ink, "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "verticalAlignment": "MIDDLE"}},
                            "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment)"}},
            {"repeatCell": {"range": {"sheetId": g, "startRowIndex": 1}, "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
            {"updateDimensionProperties": {"range": {"sheetId": g, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 12},
                                           "properties": {"pixelSize": 230 if t in ("Scripts", "Businesses", "Overview") else 170}, "fields": "pixelSize"}},
        ]
    try:
        api(sid, {"requests": reqs})
    except Exception as e:
        print("formatting skipped:", str(e)[:200])
    print(f"OK https://docs.google.com/spreadsheets/d/{sid}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "craftlayer")
