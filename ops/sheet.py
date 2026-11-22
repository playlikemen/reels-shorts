"""Google Sheet mirror: one row per video, keyed by Video ID. The studio store is the source of truth; studio.sync
pushes rows here (write_row). Other agents read the Sheet; nothing reads it back automatically.

  python3.11 ops/sheet.py --beautify            # header, widths, wrapping on both tabs
  python3.11 ops/sheet.py --show                # print id, statuses and schedule of every row
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K

LAST = chr(ord("A") + len(K.HEADERS) - 1)


def col(name):
    return chr(ord("A") + K.HEADERS.index(name))


def rows(tab):
    """All data rows as dicts, each with `_row` = its sheet row number."""
    # read in 10-row pages: Composio replaces responses over ~8k tokens with a preview (see composio.execute)
    values, start, PAGE = [], 1, 10
    while start <= 500:
        data = C.execute("GOOGLESHEETS_VALUES_GET", {"spreadsheet_id": K.SPREADSHEET_ID, "range": f"'{tab}'!A{start}:{LAST}{start + PAGE - 1}",
                                                      "major_dimension": "ROWS"}, K.SHEETS_ACCOUNT)
        page = data.get("values") or (data.get("valueRanges") or [{}])[0].get("values") or []
        page += [[]] * (PAGE - len(page))          # keep row numbers aligned when trailing rows are blank
        values += page
        if not any(r and str(r[0]).strip() for r in page):
            break
        start += PAGE
    out = []
    for n, r in enumerate(values[1:], start=2):
        if not r or not str(r[0]).strip():
            continue
        d = {h: (r[i] if i < len(r) else "") for i, h in enumerate(K.HEADERS)}
        d["_row"] = n
        out.append(d)
    return out


def _write(tab, rng, values):
    C.execute("GOOGLESHEETS_VALUES_UPDATE", {"spreadsheet_id": K.SPREADSHEET_ID, "range": f"'{tab}'!{rng}",
                                             "value_input_option": "RAW", "values": values}, K.SHEETS_ACCOUNT)


def ensure_header(tab):
    _write(tab, f"A1:{LAST}1", [K.HEADERS])


def upsert(tab, record):
    """Insert or replace the row whose Video ID matches. `record` maps header names to values."""
    ensure_header(tab)
    existing = rows(tab)
    hit = next((r for r in existing if r["Video ID"] == record["Video ID"]), None)
    n = hit["_row"] if hit else (max([r["_row"] for r in existing], default=1) + 1)
    merged = {h: (hit or {}).get(h, "") for h in K.HEADERS}
    merged.update({k: v for k, v in record.items() if k in K.HEADERS})
    _write(tab, f"A{n}:{LAST}{n}", [[str(merged[h]) for h in K.HEADERS]])
    return n


def write_row(tab, row_number, record):
    """Write one whole row (the studio's mirror push)."""
    _write(tab, f"A{row_number}:{LAST}{row_number}", [[str(record.get(h, "")) for h in K.HEADERS]])


def video_id_at(tab, row_number):
    data = C.execute("GOOGLESHEETS_VALUES_GET", {"spreadsheet_id": K.SPREADSHEET_ID, "range": f"'{tab}'!A{row_number}:A{row_number}",
                                                  "major_dimension": "ROWS"}, K.SHEETS_ACCOUNT)
    v = data.get("values") or (data.get("valueRanges") or [{}])[0].get("values") or []
    return str(v[0][0]).strip() if v and v[0] else ""


def set_cells(tab, row_number, updates):
    for name, value in updates.items():
        _write(tab, f"{col(name)}{row_number}", [[str(value)]])


def beautify(tab):
    sid = K.TAB_SHEET_IDS[tab]
    n = len(K.HEADERS)
    reqs = [
        {"updateSheetProperties": {"properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 1, "frozenColumnCount": 1}},
                                   "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": n},
                        "cell": {"userEnteredFormat": {"backgroundColor": {"red": 0.059, "green": 0.09, "blue": 0.165},
                                                       "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
                                                       "verticalAlignment": "MIDDLE", "wrapStrategy": "WRAP"}},
                        "fields": "userEnteredFormat(backgroundColor,textFormat,verticalAlignment,wrapStrategy)"}},
        {"repeatCell": {"range": {"sheetId": sid, "startRowIndex": 1, "endRowIndex": 500, "startColumnIndex": 0, "endColumnIndex": n},
                        "cell": {"userEnteredFormat": {"wrapStrategy": "CLIP", "verticalAlignment": "TOP"}},
                        "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
    ]
    for i, w in enumerate(K.COL_WIDTHS):
        reqs.append({"updateDimensionProperties": {"range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
                                                   "properties": {"pixelSize": w}, "fields": "pixelSize"}})
    r = C.proxy("googlesheets", f"https://sheets.googleapis.com/v4/spreadsheets/{K.SPREADSHEET_ID}:batchUpdate", "POST", body={"requests": reqs})
    if r.get("status") != 200:
        raise RuntimeError(f"beautify failed: {str(r)[:300]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--beautify", action="store_true"); ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    for b in K.brands():
        tab = b["sheet_tab"]
        if a.beautify:
            ensure_header(tab); beautify(tab); print("beautified", tab)
        if a.show:
            for r in rows(tab):
                print(tab, r["Video ID"], "| IG:", r["Instagram Status"], "| YT:", r["YouTube Status"], "| at:", r["Scheduled Time (IST)"])
