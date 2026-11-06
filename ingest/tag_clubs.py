import json, os, re, sys, time
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

MODEL = "gemini-3.5-flash-lite"   # keep whatever name worked for you last time
LIMIT = None                      # still the 10-club test
PAUSE = 6.5

DETAILS = ROOT / "data" / "raw" / "club_details.json"
CLUBS = ROOT / "data" / "raw" / "clubs.json"
OUT = ROOT / "data" / "ai_tags.json"

INTERESTS = {
    "finance": "investing, trading, banking, private equity, real estate, accounting",
    "consulting": "case-based or project consulting",
    "tech": "software, AI, data, engineering, programming, robotics",
    "science": "natural or social science, research, lab work",
    "entre": "startups, founding, venture building",
    "impact": "community service, nonprofits, social enterprise, civic work",
    "policy": "government, politics, law, public policy, international affairs",
    "arts": "visual art, music, theater, dance, film, design, media production",
    "health": "medicine, public health, wellness, biotech",
    "climate": "environment, sustainability, energy",
    "edu": "teaching, tutoring, education",
    "sports": "athletics, club sports, sports business",
    "writing": "journalism, publications, creative writing, debate-style writing",
    "culture": "cultural, religious, or identity-based community",
}
ACTIVITIES = {
    "career_prep": "recruiting prep, interview prep, industry networking",
    "competition": "competitions, case contests, tournaments",
    "building_projects": "building products, portfolios, or creative work",
    "learning_workshops": "classes, workshops, skill-building",
    "performance": "performances, shows, concerts, exhibitions",
    "advocacy": "advocacy or organizing",
    "volunteering": "hands-on service",
    "social_events": "social events or community building",
    "mentorship": "mentorship or peer advising",
    "research": "research projects or publishing",
}
COMMIT = ("low", "medium", "high", "unknown")
YNU = ("yes", "no", "unknown")

SYSTEM = f"""You tag Penn student clubs so students can filter them. Use ONLY what the text says.

Return one JSON object and nothing else, with these keys:
- "interests": up to 4 ids from the list below, most relevant first. Empty list if none fit.
- "activities": up to 3 ids from the activity list below, only the club's main activities, not everything mentioned once.
- "commitment": "low", "medium", "high", or "unknown". Choose a level only if the text states meeting frequency, a rehearsal or practice schedule, or a selective multi-step application. Joining instructions, "register on Penn Clubs", or general descriptions do not count. Otherwise "unknown".
- "commitment_evidence": an exact phrase of under 15 words copied from the text that supports your commitment answer, or null if "unknown".
- "beginner_friendly": "yes" only if the text says no prior experience or knowledge is needed, or explicitly welcomes beginners or all skill levels. Being "open to everyone" or "welcoming" is NOT enough. "no" only if the text says auditions, prior experience, or a selective application are required. Otherwise "unknown".
- "beginner_evidence": an exact phrase of under 15 words copied from the text that supports your answer, or null if "unknown".
- "keywords": 5 to 10 specific lowercase phrases a student might search for (for example "equity research", "stage lighting", "debate"). Avoid generic words like "club" or "students".
- "summary": under 25 words, plain language, saying what members actually do.

Tag the club's topic and activities. Do not guess anything about its members' identities beyond what the club says about itself.

Interest ids:
""" + "\n".join(f"- {k}: {v}" for k, v in INTERESTS.items()) + """

Activity ids:
""" + "\n".join(f"- {k}: {v}" for k, v in ACTIVITIES.items())

if not os.getenv("GEMINI_API_KEY"):
    sys.exit("No GEMINI_API_KEY found. Check that .env is in the project root and saved.")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
details = json.loads(DETAILS.read_text(encoding="utf-8"))
clubs = {c["code"]: c for c in json.loads(CLUBS.read_text(encoding="utf-8"))}
tags = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

def build_prompt(code):
    d, c = details[code], clubs.get(code, {})
    return "\n".join([
        f"Club name: {d['name']}",
        f"Category: {d.get('category')}",
        f"Badges: {', '.join(sorted(set(d.get('badges', []))))}",
        f"Officer-chosen tags: {', '.join(t['name'] for t in c.get('tags', []))}",
        f"Description:\n{d['description'][:3000]}",
        f"How to get involved:\n{d['how_to_get_involved'][:600]}",
        f"Signature events:\n{d['signature_events'][:600]}",
    ])

def parse(text):
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0))

def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[\"'“”‘’]", "", s.lower())).strip(" .")

def validate(d):
    commit = d.get("commitment") if d.get("commitment") in COMMIT else "unknown"
    beg = d.get("beginner_friendly") if d.get("beginner_friendly") in YNU else "unknown"
    ce, be = d.get("commitment_evidence"), d.get("beginner_evidence")
    if not ce: commit = "unknown"
    if not be: beg = "unknown"
    return {
        "interests": [x for x in d.get("interests", []) if x in INTERESTS][:4],
        "activities": [x for x in d.get("activities", []) if x in ACTIVITIES][:3],
        "commitment": commit,
        "commitment_evidence": ce if commit != "unknown" else None,
        "beginner_friendly": beg,
        "beginner_evidence": be if beg != "unknown" else None,
        "keywords": [str(k).lower().strip() for k in d.get("keywords", [])][:10],
        "summary": str(d.get("summary", ""))[:200],
    }

def check_evidence(result, code):
    d0 = details[code]
    text = norm(d0["description"] + " " + d0["how_to_get_involved"] + " " + d0["signature_events"])
    for field, ev in (("commitment", "commitment_evidence"), ("beginner_friendly", "beginner_evidence")):
        if result[ev] and norm(result[ev]) not in text:
            result[field], result[ev] = "unknown", None

def save():
    OUT.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")

todo = [c for c in details if c not in tags]
if LIMIT:
    todo = todo[:LIMIT]
print(f"{len(tags)} already tagged, tagging {len(todo)} now")

config = types.GenerateContentConfig(
    system_instruction=SYSTEM,
    response_mime_type="application/json",
    temperature=0.2,
)

failed, hit_limit = [], False

for n, code in enumerate(todo, 1):
    result = None
    for attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=build_prompt(code), config=config)
            result = validate(parse(resp.text))
            break
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
                print("rate limited, waiting 40 seconds...")
                time.sleep(40)
                if attempt == 2:
                    hit_limit = True
            else:
                print("retry", code, type(e).__name__, msg[:150])
                time.sleep(3)
    if hit_limit:
        break
    if result is None:
        failed.append(code)
        continue
    check_evidence(result, code)
    result["model"] = MODEL
    tags[code] = result
    if LIMIT:
        print(f"\n{details[code]['name']}")
        print("  interests:", result["interests"], "| commitment:", result["commitment"], "| beginner:", result["beginner_friendly"])
        print("  evidence:", result["commitment_evidence"], "|", result["beginner_evidence"])
        print("  activities:", result["activities"])
        print("  summary:", result["summary"])
    elif n % 25 == 0:
        print(f"{n}/{len(todo)} done")
    if n % 10 == 0:
        save()
    time.sleep(PAUSE)

save()
print(f"\ndone. tagged total: {len(tags)} | failed: {len(failed)}")
if hit_limit:
    print("Hit the free daily limit. Run this script again tomorrow and it will resume.")