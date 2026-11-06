import datetime, json, statistics, sys, time, collections
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "courses_all.json"
BASE = "https://penncourseplan.com/api/base"
SEMS = ["2027A", "2026C", "2026A"]
WHARTON = ["ACCT", "BEPP", "FNCE", "HCMG", "LGST", "MGMT", "MKTG", "OIDD", "REAL", "STAT", "WHCP"]
OTHER = ["ECON", "MATH", "CIS", "PSYC", "WRIT", "PSCI", "PHIL", "HIST", "SOCI", "BIOL", "CHEM", "PHYS", "ENGL", "COMM", "COGS", "LING", "ANTH"]
DEPTS = WHARTON + OTHER
RK = ("course_quality", "instructor_quality", "difficulty", "work_required")

session = requests.Session()
by_id = {}
skipped_youth = 0

for sem in SEMS:
    for dept in DEPTS:
        data = None
        for attempt in range(3):
            try:
                r = session.get(f"{BASE}/{sem}/search/courses/", params={"search": dept}, timeout=60)
                r.raise_for_status()
                data = r.json()
                break
            except Exception as e:
                print("retry", sem, dept, str(e)[:60])
                time.sleep(2)
        if not isinstance(data, list):
            continue
        for c in data:
            cid = c.get("id") or ""
            if not cid.startswith(dept + "-"):
                continue
            desc = (c.get("description") or "").strip()
            low = desc.lower()
            if "pre-baccalaureate" in low or "wharton global youth" in low:
                skipped_youth += 1
                continue
            rec = by_id.setdefault(cid, {"id": cid, "dept": dept, "title": c.get("title"), "description": desc,
                                         "credits": c.get("credits"), "semesters": set(),
                                         **{k: None for k in RK}})
            rec["semesters"].add(sem)
            if len(desc) > len(rec["description"]):
                rec["description"] = desc
            for k in RK:
                if rec[k] is None and c.get(k) is not None:
                    rec[k] = c[k]
        time.sleep(0.3)
    print("finished semester", sem, "| courses so far:", len(by_id))

today = datetime.date.today().isoformat()
items = []
for cid, c in sorted(by_id.items()):
    num = int(cid.split("-")[1]) if cid.split("-")[1].isdigit() else None
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
print("with all four ratings:", sum(1 for i in items if all(v is not None for v in i["ratings"].values())))
print("\ncourses per department:", dict(collections.Counter(i["dept"] for i in items)))
print("\nrating ranges (min / median / max):")
for k in ("quality", "instructor", "difficulty", "workload"):
    v = [i["ratings"][k] for i in items if i["ratings"][k] is not None]
    if v:
        print(f"  {k:10} {min(v):.2f} / {statistics.median(v):.2f} / {max(v):.2f}  (n={len(v)})")
print("\ncourse levels (first digit of number):",
      dict(sorted(collections.Counter(i["number"] // 1000 for i in items if i["number"] is not None).items())))
print("\nsample:")
for i in items[:3]:
    print("-", i["title"], i["ratings"], i["semesters"])