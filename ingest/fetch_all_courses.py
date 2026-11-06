import datetime, json, statistics, sys, time, collections
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "courses_all.json"
BASE = "https://penncourseplan.com/api/base"
# Newest first, so the newest title and ratings win. A = spring, B = summer, C = fall.
YEAR = datetime.date.today().year
SEMS = [f"{y}{t}" for y in range(YEAR + 1, YEAR - 4, -1) for t in "CBA"]
WHARTON = ["ACCT", "BEPP", "FNCE", "HCMG", "LGST", "MGMT", "MKTG", "OIDD", "REAL", "STAT", "WHCP"]
RK = ("course_quality", "instructor_quality", "difficulty", "work_required")

session = requests.Session()
by_id, per_sem, skipped_youth = {}, {}, 0

for sem in SEMS:
    data = None
    for attempt in range(3):
        try:
            r = session.get(f"{BASE}/{sem}/search/courses/", timeout=240)
            r.raise_for_status()
            data = r.json()
            break
        except Exception as e:
            print(f"{sem}: attempt {attempt + 1} failed ({str(e)[:70]})")
            time.sleep(3)
    if not isinstance(data, list) or not data:
        print(f"{sem}: no courses returned")
        per_sem[sem] = 0
        continue
    per_sem[sem] = len(data)
    for c in data:
        cid = c.get("id") or ""
        if "-" not in cid:
            continue
        dept = cid.split("-")[0]
        desc = (c.get("description") or "").strip()
        low = desc.lower()
        if "pre-baccalaureate" in low or "wharton global youth" in low:
            skipped_youth += 1
            continue
        rec = by_id.setdefault(cid, {"id": cid, "dept": dept, "title": c.get("title"), "description": desc,
                                     "credits": c.get("credits"), "semesters": set(), **{k: None for k in RK}})
        rec["semesters"].add(sem)
        if len(desc) > len(rec["description"]):
            rec["description"] = desc
        for k in RK:
            if rec[k] is None and c.get(k) is not None:
                rec[k] = c[k]
    print(f"{sem}: {len(data)} courses returned | unique so far: {len(by_id)}")
    time.sleep(1)

today = datetime.date.today().isoformat()
items = []
for cid, c in sorted(by_id.items()):
    part = cid.split("-", 1)[1]
    num = int(part) if part.isdigit() else None
    items.append({
        "id": "course-" + cid, "type": "course",
        "title": cid.replace("-", " ") + ": " + (c["title"] or ""),
        "summary": c["description"][:240], "description": c["description"][:1500],
        "interests": [], "activities": [], "commitment": "unknown", "beginner_friendly": "unknown",
        "keywords": [], "tags": [c["dept"]], "category": None,
        "is_wharton": c["dept"] in WHARTON, "accepting_members": False,
        "member_count": 0, "favorite_count": 0,
        "dept": c["dept"], "number": num, "credits": c["credits"],
        "semesters": sorted(c["semesters"]),
        "ratings": {"quality": c["course_quality"], "instructor": c["instructor_quality"],
                    "difficulty": c["difficulty"], "workload": c["work_required"]},
        "url": "https://penncoursereview.com/course/" + cid,
        "source": "penncourseplan", "updated": today,
    })
OUT.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")

print("\nunique courses saved:", len(items), "| youth-program courses skipped:", skipped_youth)
print("departments found:", len({i["dept"] for i in items}))
print("with all four ratings:", sum(1 for i in items if all(v is not None for v in i["ratings"].values())))
print("undergraduate (number under 5000):", sum(1 for i in items if i["number"] is not None and i["number"] < 5000))
print("graduate (5000 and up):", sum(1 for i in items if i["number"] is not None and i["number"] >= 5000))
print("largest departments:", collections.Counter(i["dept"] for i in items).most_common(15))
print("courses returned per semester:", per_sem)
for k in ("quality", "instructor", "difficulty", "workload"):
    v = [i["ratings"][k] for i in items if i["ratings"][k] is not None]
    if v:
        print(f"  {k:10} {min(v):.2f} / {statistics.median(v):.2f} / {max(v):.2f}  (n={len(v)})")