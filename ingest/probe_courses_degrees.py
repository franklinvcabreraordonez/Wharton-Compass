import json, sys
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

def probe(name, url):
    print("\n==", name, "==")
    print(url)
    try:
        r = requests.get(url, timeout=60)
    except Exception as e:
        print("request failed:", e)
        return
    print("status:", r.status_code, "|", r.headers.get("content-type"))
    try:
        d = r.json()
    except Exception:
        print(r.text[:300])
        return
    (RAW / f"{name}_sample.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")
    items = d if isinstance(d, list) else (d.get("results") if isinstance(d, dict) else None)
    print("type:", type(d).__name__, "| items:", len(items) if isinstance(items, list) else "n/a")
    first = items[0] if isinstance(items, list) and items else d
    if isinstance(first, dict):
        print("fields:", list(first.keys()))
    print(json.dumps(first, indent=1, ensure_ascii=False)[:1800])

probe("courses", "https://penncourseplan.com/api/base/current/search/courses/?search=FNCE")
probe("degrees", "https://penncourseplan.com/api/degree/degrees/")