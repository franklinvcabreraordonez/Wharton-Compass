import json, re, sys, collections, datetime
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "items.json"

def load(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception as e:
        print("could not read", path.name, "-", e)
        return default

clubs = load(RAW / "clubs.json", [])
details = load(RAW / "club_details.json", {})
ai = load(ROOT / "data" / "ai_tags.json", {})
socials = load(RAW / "club_socials.json", {})

TAG_MAP = {
    "Consulting": "consulting", "Technology": "tech", "Programming": "tech",
    "Engineering": "tech", "Science": "science", "Entrepreneurship": "entre",
    "Community Service": "impact", "Charity": "impact", "Civic engagement": "impact",
    "Advocacy": "impact", "Politics": "policy", "Law": "policy", "Global affairs": "policy",
    "Arts": "arts", "Performing Arts": "arts", "Music": "arts", "Dance": "arts",
    "Theatre": "arts", "A Cappella": "arts", "Comedy": "arts", "Design": "arts",
    "Media": "arts", "Health": "health", "Medicine": "health", "Environmental": "climate",
    "Youth": "edu", "Instructional": "edu", "Club Sports": "sports",
    "Writing": "writing", "Journalism": "writing", "Publication": "writing",
    "Cultural": "culture", "Religious/Spiritual": "culture", "LGBTQ+": "culture",
    "First Generation Low Income (FGLI)": "culture",
}
NAME_PATTERNS = {
    "finance": [r"\binvest(ing|ment|ments|or|ors)?\b", r"\bfinance\b", r"\btrading\b",
                r"\bequity\b", r"\bcapital\b", r"\bhedge fund\b", r"\breal estate\b",
                r"\bactuarial\b", r"\baccounting\b"],
    "sports": [r"\bsports?\b"],
}

def fallback_interests(c):
    s = {TAG_MAP[t["name"]] for t in c["tags"] if t["name"] in TAG_MAP}
    name = c["name"].lower()
    for k, pats in NAME_PATTERNS.items():
        if any(re.search(p, name) for p in pats):
            s.add(k)
    return sorted(s)

today = datetime.date.today().isoformat()
items = []
for c in clubs:
    code = c["code"]
    a = ai.get(code)
    subtitle = (c.get("subtitle") or "").strip()
    links = {k: v for k, v in (socials.get(code) or {}).items() if v}
    items.append({
        "id": "club-" + code,
        "type": "club",
        "title": c["name"],
        "summary": (a["summary"] if a and a.get("summary") else subtitle[:220]),
        "interests": a["interests"] if a else fallback_interests(c),
        "activities": a["activities"] if a else [],
        "commitment": a["commitment"] if a else "unknown",
        "beginner_friendly": a["beginner_friendly"] if a else "unknown",
        "keywords": a["keywords"] if a else [],
        "tags": [t["name"] for t in c["tags"]],
        "category": (details.get(code) or {}).get("category"),
        "is_wharton": c["is_wharton"],
        "accepting_members": c["accepting_members"],
        "member_count": c["membership_count"],
        "favorite_count": c["favorite_count"],
        "ai_tagged": bool(a),
        "links": links,
        "image": c.get("image_url"),
        "application": c.get("application_required"),
        "recruiting": c.get("recruiting_cycle"),
        "size": c.get("size"),
        "url": "https://pennclubs.com/club/" + code,
        "source": "pennclubs",
        "updated": today,
    })

seen = set()
for name in ("events_normalized.json", "events_pennclubs_normalized.json",
             "courses_normalized.json", "manual_normalized.json"):
    extra = load(ROOT / "data" / name, [])
    added = 0
    for e in extra:
        key = ((e.get("title") or "").lower().strip(), (e.get("start") or "")[:16])
        if e.get("type") == "event" and key in seen:
            continue
        seen.add(key)
        items.append(e)
        added += 1
    if extra:
        print("added", added, "items from", name)

OUT.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
print("wrote", len(items), "items to", OUT)
print("AI-tagged clubs:", sum(1 for i in items if i.get("ai_tagged")))
print("clubs with an Instagram link:", sum(1 for i in items if i["type"] == "club" and i.get("links", {}).get("instagram")))

clubs_only = [i for i in items if i["type"] == "club"]
wh = [i for i in clubs_only if i["is_wharton"]]
def open_share(g):
    n = sum(1 for i in g if i.get("application") == 1)
    return f"{n} of {len(g)} ({100 * n / max(1, len(g)):.0f}%)"
print("listed as open membership, Wharton clubs:", open_share(wh))
print("listed as open membership, all clubs:", open_share(clubs_only))

META = ROOT / "data" / "meta.json"
meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
meta["clubs_events_updated"] = datetime.date.today().isoformat()
META.write_text(json.dumps(meta), encoding="utf-8")

