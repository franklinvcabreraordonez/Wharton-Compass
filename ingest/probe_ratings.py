import json, sys, time
from pathlib import Path
import requests
sys.stdout.reconfigure(encoding="utf-8")

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
BASE = "https://penncourseplan.com/api/base"

def get(url):
    try:
        r = requests.get(url, timeout=60)
    except Exception as e:
        return None, None
    try:
        return r, r.json()
    except Exception:
        return r, None

print("== ratings coverage (courses with a value / courses found) ==")
depts = ["ACCT", "FNCE", "MGMT", "MKTG", "OIDD", "STAT", "ECON", "MATH", "CIS", "PSYC"]
store = {}
for sem in ["current", "2026C", "2026A"]:
    for d in depts:
        r, data = get(f"{BASE}/{sem}/search/courses/?search={d}")
        if not isinstance(data, list):
            print(f"{sem:8} {d:5} -> status {getattr(r, 'status_code', 'failed')}, no list")
            continue
        store.setdefault(sem, {})[d] = data
        n = len(data)
        c = lambda k: sum(1 for x in data if x.get(k) is not None)
        print(f"{sem:8} {d:5} {n:4} courses | difficulty {c('difficulty'):3} | work {c('work_required'):3} | quality {c('course_quality'):3}")
        time.sleep(0.3)
(RAW / "courses_by_semester.json").write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")

print("\nexample rated course:")
for sem in store:
    for d, data in store[sem].items():
        hit = next((x for x in data if x.get("difficulty") is not None), None)
        if hit:
            print(sem, d, json.dumps({k: hit[k] for k in ("id", "title", "course_quality", "instructor_quality", "difficulty", "work_required", "recommendation_score")}))
            break
    else:
        continue
    break

print("\n== degree endpoint variants ==")
for url in [
    "https://penncourseplan.com/api/degree/degrees",
    "https://penncoursereview.com/api/degree/degrees",
    "https://penncoursereview.com/api/degree/degrees/",
]:
    r, data = get(url)
    print(url, "->", getattr(r, "status_code", "failed"), "|", (r.headers.get("content-type") if r is not None else ""))
    if isinstance(data, (list, dict)):
        print("   json:", json.dumps(data, ensure_ascii=False)[:300])