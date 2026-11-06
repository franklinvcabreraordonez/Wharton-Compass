import json, sys, time
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
CODE = "STAT-4300"   # change this to check another course, for example "FNCE-1010"
dept, num = CODE.split("-")

print("looking for", CODE)
for name in ("courses_all.json", "courses.json"):
    f = ROOT / "data" / name
    if not f.exists():
        print(f"{name}: file missing")
        continue
    data = json.loads(f.read_text(encoding="utf-8"))
    hit = [c for c in data if c.get("id") in (CODE, "course-" + CODE)]
    print(f"{name}: {'FOUND' if hit else 'not found'} ({len(data)} courses in file)")
    if hit:
        print("   ", json.dumps(hit[0], ensure_ascii=False)[:400])

BASE = "https://penncourseplan.com/api/base"
print("\nasking the course API directly:")
for sem in ["2027A", "2026C", "2026A", "2025C", "2025A", "2024C", "2024A"]:
    for q in (CODE, dept + " " + num, dept):
        try:
            r = requests.get(f"{BASE}/{sem}/search/courses/", params={"search": q}, timeout=60)
            data = r.json()
        except Exception as e:
            print(f"{sem} search={q!r}: failed ({str(e)[:50]})")
            continue
        ids = [c.get("id") for c in data] if isinstance(data, list) else []
        print(f"{sem} search={q!r}: {len(ids)} results | contains {CODE}: {CODE in ids}")
        if CODE in ids:
            c = next(c for c in data if c["id"] == CODE)
            print("    ", {k: c.get(k) for k in ("title", "course_quality", "difficulty", "work_required")})
        time.sleep(0.3)