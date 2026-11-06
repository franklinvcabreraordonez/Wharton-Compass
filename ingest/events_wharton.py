import hashlib, html, json, re, sys, time
from collections import Counter
from datetime import datetime, time as dtime, timezone
from pathlib import Path
import requests
from icalendar import Calendar

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "data" / "raw" / "ics_helper.html"        # your saved page (local only, never committed)
GROUPS_FILE = ROOT / "data" / "event_groups.json"       # group names and public calendar links (safe to commit)
FEEDS = ROOT / "data" / "raw" / "event_feeds"
OUT = ROOT / "data" / "events_normalized.json"
UG = "Undergraduate Student Clubs"


def load_groups():
    """Use the saved group list if it exists. Otherwise read it from the saved CampusGroups page and save it."""
    if GROUPS_FILE.exists():
        return [tuple(g) for g in json.loads(GROUPS_FILE.read_text(encoding="utf-8"))]
    if not PAGE.exists():
        sys.exit("Need data/event_groups.json or data/raw/ics_helper.html. See the setup steps.")
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(PAGE.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    found = []
    for tr in soup.find_all("tr"):
        cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all("td")]
        if not cells or not cells[0].endswith(UG):
            continue
        link = next((a["href"] for a in tr.find_all("a", href=True)
                     if a["href"].startswith("https://groups.wharton.upenn.edu/ical/") and a["href"].endswith(".ics")), None)
        if link:
            found.append((cells[0][:-len(UG)].strip(), link))
    GROUPS_FILE.write_text(json.dumps(found, ensure_ascii=False, indent=1), encoding="utf-8")
    print("saved", len(found), "groups to", GROUPS_FILE)
    return found


groups = load_groups()
print("undergraduate groups:", len(groups))

INTEREST_BY_CAT = {"Healthcare": "health", "Entrepreneurship": "entre", "Athletic/Sports": "sports",
                   "Cultural": "culture", "Wellness": "health"}
INTEREST_WORDS = {
    "finance": r"invest|financ|trading|equity|valuation|\bdcf\b|hedge|real estate|capital",
    "consulting": r"consult|\bcase\b",
    "tech": r"\bai\b|machine learning|\bdata\b|software|quant|\btech",
    "entre": r"startup|venture|founder|pitch|entrepreneur",
    "policy": r"policy|government|politic|\blaw\b",
    "arts": r"\bart\b|\barts\b|music|film|dance|media|theat",
    "climate": r"climate|sustainab|energy",
    "sports": r"sports|athlet",
    "health": r"health|medic|biotech",
    "impact": r"social impact|nonprofit|community service|volunteer",
    "writing": r"writing|journalis|publication",
    "edu": r"teaching|tutor|education",
}
ACTIVITY_BY_CAT = {"Networking": "career_prep", "Career(s)": "career_prep",
                   "Training/Workshop": "learning_workshops", "Presentation/Speaker(s)": "learning_workshops",
                   "Case/Pitch Competition": "competition", "Social": "social_events", "Community": "social_events"}


def text(v):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(v or "")))).strip()


def to_dt(v):
    if v is None:
        return None
    v = v.dt
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.combine(v, dtime.min, tzinfo=timezone.utc)


def cats(c):
    x = c.get("CATEGORIES")
    if x is None:
        return []
    out = []
    for i in (x if isinstance(x, list) else [x]):
        out += [str(s) for s in getattr(i, "cats", [i])]
    return out


FEEDS.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc)
today = now.date().isoformat()
items, seen = [], set()
failed, long_dropped, per_group = [], 0, Counter()

for name, url in groups:
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        cal = Calendar.from_ical(r.content)
    except Exception as e:
        failed.append(name)
        print("failed:", name, str(e)[:80])
        time.sleep(1)
        continue
    (FEEDS / url.rsplit("/", 1)[-1]).write_bytes(r.content)

    for c in cal.walk("VEVENT"):
        s, e = to_dt(c.get("DTSTART")), to_dt(c.get("DTEND"))
        e = e or s
        title = text(c.get("SUMMARY"))
        if not s or not title or e < now:
            continue
        if (e - s).days >= 1:
            long_dropped += 1
            continue
        link = str(c.get("URL") or "")
        m = re.search(r"id=(\d+)", link)
        uid = "event-" + (m.group(1) if m else hashlib.md5((str(c.get("UID")) + str(s)).encode()).hexdigest()[:12])
        if uid in seen:
            continue
        seen.add(uid)

        cs = cats(c)
        hay = (title + " " + " ".join(cs) + " " + name).lower()
        interests = {INTEREST_BY_CAT[x] for x in cs if x in INTEREST_BY_CAT}
        interests |= {k for k, p in INTEREST_WORDS.items() if re.search(p, hay)}
        activities = sorted({ACTIVITY_BY_CAT[x] for x in cs if x in ACTIVITY_BY_CAT})
        loc = text(c.get("LOCATION"))
        if not loc or "sign in" in loc.lower():
            loc = None
        desc = text(c.get("DESCRIPTION"))

        items.append({
            "id": uid, "type": "event", "title": title,
            "summary": f"Hosted by {name}. {desc}"[:240],
            "interests": sorted(interests), "activities": activities,
            "commitment": "unknown", "beginner_friendly": "unknown",
            "keywords": [x.lower() for x in cs],
            "tags": cs, "category": None, "is_wharton": True,
            "accepting_members": False, "member_count": 0, "favorite_count": 0,
            "start": s.isoformat(), "end": e.isoformat(), "location": loc,
            "organizer": name, "url": link or url, "source": "wharton-campusgroups",
            "updated": today,
        })
        per_group[name] += 1
    time.sleep(0.5)

items.sort(key=lambda x: x["start"])
OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

print("\nfeeds failed:", len(failed))
print("upcoming single-day events:", len(items))
print("multi-day listings skipped:", long_dropped)
print("groups with upcoming events:", len(per_group), "of", len(groups))
print("\nnext 5 events:")
for i in items[:5]:
    print("-", i["title"][:70], "|", i["organizer"], "|", i["start"][:16])