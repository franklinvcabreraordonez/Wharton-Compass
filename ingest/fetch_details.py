import requests, json, re, time, sys, html
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "clubs.json"
OUT = ROOT / "data" / "raw" / "club_details.json"
BASE = "https://pennclubs.com/api/clubs/"

def clean(s):
    if not s:
        return ""
    s = re.sub(r"(?i)<br\s*/?>|</p>|</li>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()

def label(x):
    if isinstance(x, dict):
        for k in ("name", "label", "text"):
            if x.get(k):
                return str(x[k])
        return str(x)
    return str(x)

def labels(lst):
    return [label(x) for x in (lst or [])]

def save(details):
    OUT.write_text(json.dumps(details, indent=2, ensure_ascii=False), encoding="utf-8")

clubs = json.loads(RAW.read_text(encoding="utf-8"))
details = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
todo = [c["code"] for c in clubs if c["code"] not in details]
print(f"{len(details)} already saved, {len(todo)} to fetch")

session = requests.Session()
failed = []

for n, code in enumerate(todo, 1):
    try:
        r = session.get(f"{BASE}{code}/", timeout=30)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        failed.append(code)
        print("failed:", code, e)
        time.sleep(2)
        continue

    details[code] = {
        "name": d.get("name"),
        "description": clean(d.get("description")),
        "how_to_get_involved": clean(d.get("how_to_get_involved")),
        "signature_events": clean(d.get("signature_events")),
        "category": label(d["category"]) if d.get("category") else None,
        "classification": label(d["classification"]) if d.get("classification") else None,
        "badges": labels(d.get("badges")),
        "target_majors": labels(d.get("target_majors")),
        "target_years": labels(d.get("target_years")),
        "target_schools": labels(d.get("target_schools")),
        "student_types": labels(d.get("student_types")),
        "website": d.get("website"),
    }

    if n % 25 == 0:
        save(details)
        print(f"{n}/{len(todo)} done")
    time.sleep(0.4)

save(details)

lengths = sorted(len(v["description"]) for v in details.values())
print("\nsaved:", len(details), "| failed:", len(failed))
print("empty descriptions:", sum(1 for L in lengths if L == 0))
print("under 100 characters:", sum(1 for L in lengths if 0 < L < 100))
print("median description length:", lengths[len(lengths) // 2])
if "witg" in details:
    print("\nexample (witg):")
    print(json.dumps(details["witg"], indent=2, ensure_ascii=False)[:1500])