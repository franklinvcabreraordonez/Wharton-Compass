import collections, datetime, json, sys, time
from pathlib import Path
import requests

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "applications.json"
META = ROOT / "data" / "meta.json"
BASE = "https://pennclubs.com/api/clubs/{}/applications/"
HEADERS = {"User-Agent": "WhartonCompass-prototype (student project)"}

clubs = json.loads((RAW / "clubs.json").read_text(encoding="utf-8"))
# Clubs that recruit by audition, tryout, application, or interview, plus every Wharton club.
targets = [c for c in clubs if c.get("application_required") in (2, 3, 4, 5) or c.get("is_wharton")]
print("clubs to check:", len(targets))

out, failed, session = {}, [], requests.Session()
for n, c in enumerate(targets, 1):
    code = c["code"]
    data = None
    for attempt in range(3):
        try:
            r = session.get(BASE.format(code), headers=HEADERS, timeout=60)
            if r.status_code == 200:
                data = r.json()
                break
            if r.status_code in (403, 404):
                break
        except Exception:
            time.sleep(2)
    if not isinstance(data, list):
        failed.append(code)
        time.sleep(0.3)
        continue
    wins = []
    for a in data:
        # Keep only the dates, names, and links. Application questions and email templates are not copied.
        if not a.get("application_start_time") or not a.get("application_end_time"):
            continue
        wins.append({
            "cycle": a.get("cycle") or "",
            "name": a.get("name") or "",
            "start": a["application_start_time"],
            "end": a["application_end_time"],
            "result": a.get("result_release_time"),
            "active": bool(a.get("active")),
            "url": a.get("external_url") or "",
            "committees": [x.get("name") for x in (a.get("committees") or []) if x.get("name")][:12],
        })
    if wins:
        out[code] = sorted(wins, key=lambda w: w["start"])
    if n % 25 == 0:
        print(f"{n}/{len(targets)} checked")
    time.sleep(0.4)

today = datetime.date.today().isoformat()
OUT.write_text(json.dumps({"updated": today, "clubs": out}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
meta["applications_updated"] = today
META.write_text(json.dumps(meta), encoding="utf-8")

now = datetime.datetime.now(datetime.timezone.utc)
allw = [w for ws in out.values() for w in ws]
parse = lambda s: datetime.datetime.fromisoformat(s)
print("\nclubs with at least one application window:", len(out), "| failed or blocked:", len(failed))
print("windows in total:", len(allw))
print("open right now:", sum(1 for w in allw if parse(w["start"]) <= now <= parse(w["end"])))
print("starting in the future:", sum(1 for w in allw if parse(w["start"]) > now))
print("most common cycle names:", collections.Counter(w["cycle"] for w in allw).most_common(8))
print("file size (KB):", OUT.stat().st_size // 1024)