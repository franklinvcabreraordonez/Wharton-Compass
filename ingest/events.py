import requests, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "events.json"
r = requests.get("https://pennclubs.com/api/events/", timeout=60)
print("status:", r.status_code)
data = r.json()
print("type:", type(data).__name__)

events = data if isinstance(data, list) else data.get("results", data)
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(events, indent=2, ensure_ascii=False), encoding="utf-8")

if isinstance(events, list):
    print("number of events:", len(events))
    print(json.dumps(events[0], indent=2, ensure_ascii=False)[:2500])
else:
    print("keys:", list(events.keys()))