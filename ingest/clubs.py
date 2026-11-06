import requests, json, collections, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

URL = "https://pennclubs.com/api/clubs/"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "clubs.json"

r = requests.get(URL, timeout=60)
r.raise_for_status()
clubs = r.json()

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(clubs, indent=2), encoding="utf-8")
print("saved", len(clubs), "clubs to", OUT)

active = [c for c in clubs if c["active"] and c["approved"]]
wharton = [c for c in clubs if c["is_wharton"]]
print("active and approved:", len(active))
print("is_wharton:", len(wharton))

print("\nWharton clubs:")
for c in wharton:
    print("-", c["name"], "|", [t["name"] for t in c["tags"]])

tag_counts = collections.Counter(t["name"] for c in clubs for t in c["tags"])
print("\nAll tags:")
for name, n in tag_counts.most_common():
    print(f"{n:4d}  {name}")

print("\napplication_required:", collections.Counter(c["application_required"] for c in clubs))
print("recruiting_cycle:", collections.Counter(c["recruiting_cycle"] for c in clubs))