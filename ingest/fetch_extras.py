import json, re, sys, time, html
from datetime import datetime, timezone
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
BASE = "https://pennclubs.com/api/clubs/"
SOC = RAW / "club_socials.json"
FIELDS = ("instagram", "facebook", "linkedin", "twitter", "youtube", "github", "listserv", "website")

def tidy(key, v):
    v = (v or "").strip()
    if not v:
        return ""
    if v.lower().startswith(("http://", "https://")):
        return v
    if key == "instagram" and re.fullmatch(r"@?[\w.]+", v):
        return "https://instagram.com/" + v.lstrip("@")
    if key == "listserv" and "@" in v and " " not in v:
        return "mailto:" + v
    return ""

# ---------- part A: social links ----------
clubs = json.loads((RAW / "clubs.json").read_text(encoding="utf-8"))
socials = json.loads(SOC.read_text(encoding="utf-8")) if SOC.exists() else {}
todo = [c["code"] for c in clubs if c["code"] not in socials]
print(f"{len(socials)} clubs already done, {len(todo)} to fetch")

session = requests.Session()
for n, code in enumerate(todo, 1):
    try:
        r = session.get(f"{BASE}{code}/", timeout=30)
        r.raise_for_status()
        d = r.json()
        socials[code] = {k: tidy(k, d.get(k)) for k in FIELDS}
    except Exception as e:
        print("failed:", code, str(e)[:60])
        time.sleep(2)
        continue
    if n % 25 == 0:
        SOC.write_text(json.dumps(socials, indent=1), encoding="utf-8")
        print(f"{n}/{len(todo)} done")
    time.sleep(0.4)
SOC.write_text(json.dumps(socials, indent=1), encoding="utf-8")

print("\nclubs with each link type:")
for k in FIELDS:
    print(f"{sum(1 for v in socials.values() if v.get(k)):4d}  {k}")
print("clubs with at least one social/listserv link:",
      sum(1 for v in socials.values() if any(v.get(k) for k in ("instagram", "linkedin", "listserv", "facebook"))))

# ---------- part B: Penn Clubs events ----------
events = json.loads((RAW / "events.json").read_text(encoding="utf-8"))
wharton = {c["code"] for c in clubs if c["is_wharton"]}
now = datetime.now(timezone.utc)
today = now.date().isoformat()

def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()

def parse(s):
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

GBM = re.compile(r"\b(gbm|general body|general meeting|info session|information session|interest meeting|kickoff|kick-off)\b", re.I)
WORDS = {
    "finance": r"invest|financ|trading|equity|valuation|hedge|real estate",
    "consulting": r"consult|\bcase\b",
    "tech": r"\bai\b|machine learning|\bdata\b|software|quantum|\btech",
    "entre": r"startup|venture|founder|pitch|entrepreneur",
    "policy": r"policy|government|politic|\blaw\b|assembly",
    "arts": r"\bart\b|\barts\b|music|film|dance|theat|craft",
    "health": r"health|medic|biotech",
    "climate": r"climate|sustainab|energy",
    "sports": r"sports|athlet",
    "culture": r"cultur|heritage|shabbat|\bdance\b",
}

out = []
for e in events:
    shows = []
    for s in e.get("showings", []):
        st, en = parse(s.get("start_time")), parse(s.get("end_time"))
        if st and (en or st) >= now:
            shows.append((st, en or st, s))
    shows.sort(key=lambda x: x[0])
    for st, en, s in shows[:3]:
        title = clean(e.get("name"))
        desc = clean(e.get("description"))
        hay = (title + " " + desc).lower()
        et = e.get("type")
        kind = "meeting" if (et == 2 or GBM.search(title + " " + desc[:200])) else "event"
        event_type = {0: "Other", 1: "Recruitment", 2: "GBM", 3: "Speaker", 4: "Fair", 5: "Social", 6: "Career"}.get(et)
        loc = clean(s.get("location")) if s.get("location_visible_to_public") else ""
        out.append({
            "id": f"pcevent-{e['id']}-{s['id']}", "type": "event", "kind": kind,
            "title": title,
            "summary": f"Hosted by {e.get('club_name')}. {desc}"[:240],
            "interests": sorted(k for k, p in WORDS.items() if re.search(p, hay)),
            "activities": ["social_events"] if kind == "meeting" else [],
            "commitment": "unknown", "beginner_friendly": "unknown",
            "keywords": [], "tags": [], "category": None,
            "is_wharton": e.get("club") in wharton,
            "accepting_members": False, "member_count": 0, "favorite_count": 0,
            "start": st.isoformat(), "end": en.isoformat(), "location": loc or None,
            "organizer": e.get("club_name"), "club_code": e.get("club"),
            "url": e.get("url") or f"https://pennclubs.com/club/{e.get('club')}",
            "source": "pennclubs", "updated": today,
            "event_type": event_type,
        })

out.sort(key=lambda x: x["start"])
(ROOT / "data" / "events_pennclubs_normalized.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("\nPenn Clubs upcoming event showings:", len(out))
print("labeled as meetings or info sessions:", sum(1 for i in out if i["kind"] == "meeting"))
print("from Wharton clubs:", sum(1 for i in out if i["is_wharton"]))
for i in out[:8]:
    print("-", i["title"][:60], "|", i["organizer"], "|", i["start"][:16], "|", i["kind"])