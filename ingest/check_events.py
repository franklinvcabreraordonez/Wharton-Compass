import json, re, sys, html
from datetime import datetime, timezone
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
events = json.loads((ROOT / "data" / "raw" / "events.json").read_text(encoding="utf-8"))
clubs = json.loads((ROOT / "data" / "raw" / "clubs.json").read_text(encoding="utf-8"))
wharton = {c["code"] for c in clubs if c["is_wharton"]}

now = datetime.now(timezone.utc)

def parse(s):
    try:
        return datetime.fromisoformat(s) if s else None
    except Exception:
        return None

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()

dated = [(parse(e.get("latest_end_time") or e.get("latest_start_time")), e) for e in events]
dated = [(d, e) for d, e in dated if d]
upcoming = sorted([(d, e) for d, e in dated if d >= now], key=lambda x: x[0])

print("total events:", len(events))
print("with a date:", len(dated))
print("earliest:", min(d for d, _ in dated).date(), "| latest:", max(d for d, _ in dated).date())
print("upcoming (not yet ended):", len(upcoming))
print("upcoming from Wharton clubs:", sum(1 for _, e in upcoming if e.get("club") in wharton))
print("upcoming with a URL:", sum(1 for _, e in upcoming if e.get("url")))
print("upcoming with a location:", sum(1 for _, e in upcoming if any(s.get("location") for s in e.get("showings", []))))

print("\nnext 8 upcoming:")
for d, e in upcoming[:8]:
    loc = next((s["location"] for s in e.get("showings", []) if s.get("location")), None)
    print("-", e["name"], "|", e.get("club_name"), "|", e.get("earliest_start_time"), "|", loc)
    print("   ", clean(e.get("description"))[:160])