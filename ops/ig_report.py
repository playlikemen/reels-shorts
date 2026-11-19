"""Weekly Instagram numbers for a brand: every reel's views, reach, shares, saves and watch time.

  python3.11 ops/ig_report.py campusloop            # print the ranking
  python3.11 ops/ig_report.py campusloop --sheet    # also write it to the brand's insights tab

Shares per 1,000 views is the number to watch: it is what moves a reel to people who do not follow the account.
"""
import argparse, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import composio as C
import config as K

METRICS = ["reach", "views", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"]
COLUMNS = ["Date", "Views", "Reach", "Shares", "Shares per 1k views", "Saves", "Interactions", "Avg watch (s)", "Caption", "URL"]


def media(account, pages=8):
    items, after = [], None
    for _ in range(pages):
        args = {"ig_user_id": "me", "limit": 10, "fields": "id,media_product_type,permalink,timestamp,caption"}
        if after:
            args["after"] = after
        m = C.execute("INSTAGRAM_GET_IG_USER_MEDIA", args, account)
        items += m.get("data") or []
        after = ((m.get("paging") or {}).get("cursors") or {}).get("after")
        if not after or not m.get("data"):
            break
    return [i for i in items if i.get("media_product_type") == "REELS"]


def report(brand_key):
    account = K.brand(brand_key)["instagram"]["account"]
    rows = []
    for i in media(account):
        try:
            ins = C.execute("INSTAGRAM_GET_IG_MEDIA_INSIGHTS", {"ig_media_id": i["id"], "metric": METRICS}, account)
            v = {d["name"]: (d.get("values") or [{}])[0].get("value") or 0 for d in ins.get("data", [])}
        except Exception as e:
            print("skip", i["permalink"], str(e)[:80]); continue
        views = v.get("views", 0)
        rows.append([i["timestamp"][:10], views, v.get("reach", 0), v.get("shares", 0),
                     round(1000 * v.get("shares", 0) / views, 1) if views else 0, v.get("saved", 0),
                     v.get("total_interactions", 0), round(v.get("ig_reels_avg_watch_time", 0) / 1000, 1),
                     (i.get("caption") or "").replace("\n", " ")[:90], i["permalink"]])
    rows.sort(key=lambda r: -r[1])
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("brand"); ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args()
    rows = report(a.brand)
    for label, part in (("TOP 3", rows[:3]), ("BOTTOM 3", rows[-3:])):
        print(label)
        for r in part:
            print(f"  {r[0]}  views {r[1]:>6}  shares {r[3]:>4}  ({r[4]}/1k)  watch {r[7]}s  {r[8][:60]}")
    print(f"{len(rows)} reels, {sum(r[1] for r in rows)} views, {sum(r[3] for r in rows)} shares")
    if a.sheet:
        tab = K.brand(a.brand).get("insights_tab")
        if not tab:
            raise SystemExit("brand.json has no insights_tab")
        values = [COLUMNS] + [[str(c) for c in r] for r in rows]
        C.execute("GOOGLESHEETS_VALUES_UPDATE", {"spreadsheet_id": K.SPREADSHEET_ID, "range": f"'{tab}'!A1:J{len(values)}",
                                                 "values": values, "value_input_option": "RAW"}, K.SHEETS_ACCOUNT)
        print("written to", tab)
