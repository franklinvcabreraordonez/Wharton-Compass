import requests, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "courses_sample.json"
URL = "https://penncourseplan.com/api/base/current/search/courses/?search=FNCE"

r = requests.get(URL, timeout=60)
print("status:", r.status_code, "| content-type:", r.headers.get("content-type"))
try:
    data = r.json()
except Exception:
    print(r.text[:600])
    sys.exit()

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print("type:", type(data).__name__)
if isinstance(data, list):
    print("items:", len(data))
    print(json.dumps(data[0], indent=2, ensure_ascii=False)[:2500])
else:
    print("keys:", list(data.keys()))
    print(json.dumps(data, indent=2, ensure_ascii=False)[:2500])