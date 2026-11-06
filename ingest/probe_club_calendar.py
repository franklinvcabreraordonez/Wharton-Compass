import json, sys
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
BASE = "https://pennclubs.com/api"
HEADERS = {"User-Agent": "WhartonCompass-prototype (student project)"}

clubs = json.loads((ROOT / "data" / "raw" / "clubs.json").read_text(encoding="utf-8"))
wh = [c["code"] for c in clubs if c["is_wharton"]][:5]
codes = wh + ["pennlabs"]


def show(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=40)
    except Exception as e:
        print("  request failed:", str(e)[:70])
        return
    print(f"  status {r.status_code}, {len(r.content)} bytes")
    if r.status_code != 200 or not r.content:
        return
    try:
        d = r.json()
    except Exception:
        print("  not JSON:", r.text[:120].replace("\n", " "))
        return
    items = d if isinstance(d, list) else d.get("results", d) if isinstance(d, dict) else None
    if isinstance(items, list):
        print(f"  list of {len(items)}")
        if items:
            print("  fields:", list(items[0].keys()) if isinstance(items[0], dict) else items[0])
            print("  first:", json.dumps(items[0], ensure_ascii=False)[:500])
    else:
        print("  object:", json.dumps(d, ensure_ascii=False)[:400])


print("== club fairs ==")
for path in ("/clubfairs/", "/fairs/"):
    print(BASE + path)
    show(BASE + path)

print("\n== application windows, per club ==")
for code in codes:
    for path in (f"/clubs/{code}/applications/", f"/clubs/{code}/events/"):
        print(BASE + path)
        show(BASE + path)

print("\n== events: how many upcoming, by type ==")
try:
    ev = requests.get(BASE + "/events/", headers=HEADERS, timeout=60).json()
    ev = ev if isinstance(ev, list) else ev.get("results", [])
    print("total events listed:", len(ev), "| event types seen:", sorted({str(e.get("type")) for e in ev}))
except Exception as e:
    print("could not read events:", str(e)[:80])