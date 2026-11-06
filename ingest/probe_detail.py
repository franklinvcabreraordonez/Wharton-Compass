import requests, json, sys
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "raw" / "clubs.json").read_text(encoding="utf-8"))
code = next(c["code"] for c in raw if c["is_wharton"])
d = requests.get(f"https://pennclubs.com/api/clubs/{code}/", timeout=30).json()

print(code)
for k, v in d.items():
    print(k, "->", str(v)[:120].replace("\n", " "))