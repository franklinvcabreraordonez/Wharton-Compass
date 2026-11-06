import os, sys, collections
from datetime import datetime, date, time, timezone
from pathlib import Path
import requests
from dotenv import load_dotenv
from icalendar import Calendar

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
url = os.getenv("WHARTON_ICS_URL")
if not url:
    sys.exit("No WHARTON_ICS_URL found. Check that .env is saved in the project root.")

r = requests.get(url, timeout=90)
print("status:", r.status_code, "| type:", r.headers.get("content-type"), "| bytes:", len(r.content))
if r.status_code != 200 or b"BEGIN:VCALENDAR" not in r.content[:3000]:
    print("Not a calendar file. First 300 characters:")
    print(r.text[:300])
    sys.exit()

out = ROOT / "data" / "raw" / "wharton_events.ics"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(r.content)

cal = Calendar.from_ical(r.content)
events = list(cal.walk("VEVENT"))
now = datetime.now(timezone.utc)

def to_dt(v):
    if v is None:
        return None
    v = v.dt
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.combine(v, time.min, tzinfo=timezone.utc)

def cats(c):
    x = c.get("CATEGORIES")
    if x is None:
        return []
    items = x if isinstance(x, list) else [x]
    out = []
    for i in items:
        out += [str(s) for s in getattr(i, "cats", [i])]
    return out

rows = []
for c in events:
    s, e = to_dt(c.get("DTSTART")), to_dt(c.get("DTEND"))
    rows.append((s, e or s, c))

upcoming = sorted([x for x in rows if x[1] and x[1] >= now], key=lambda x: x[0])
long_ones = [x for x in upcoming if x[1] and x[0] and (x[1] - x[0]).days >= 1]

print("\ntotal events in feed:", len(events))
print("with recurrence rule (RRULE):", sum(1 for c in events if c.get("RRULE")))
print("upcoming (not yet ended):", len(upcoming))
print("upcoming lasting a day or longer:", len(long_ones))
dates = [x[0] for x in rows if x[0]]
print("date range:", min(dates).date(), "to", max(dates).date())

for f in ("SUMMARY", "LOCATION", "DESCRIPTION", "URL", "CATEGORIES", "ORGANIZER"):
    print(f"upcoming with {f}:", sum(1 for _, _, c in upcoming if c.get(f)))

cc = collections.Counter(t for _, _, c in upcoming for t in cats(c))
print("\ntop categories among upcoming:", cc.most_common(15))

print("\nnext 10 upcoming:")
for s, e, c in upcoming[:10]:
    print("-", str(c.get("SUMMARY"))[:80])
    print("   ", s, "->", e, "|", str(c.get("LOCATION") or "")[:50])
    print("    cats:", cats(c), "| org:", str(c.get("ORGANIZER") or "")[:60])
    print("    url:", str(c.get("URL") or "")[:100])