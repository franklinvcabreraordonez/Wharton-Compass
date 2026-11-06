import datetime, json, re, sys, collections, random
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "courses_all.json"
OUT_UG = ROOT / "data" / "courses_ug.json"
OUT_GRAD = ROOT / "data" / "courses_grad.json"
META = ROOT / "data" / "meta.json"

# Starting guesses at what each department is about. Departments not listed here
# still get labels from keywords in the title and description.
DEPT = {
    "ACCT": ["finance"], "BEPP": ["finance", "policy"], "FNCE": ["finance"], "REAL": ["finance"],
    "HCMG": ["health"], "LGST": ["policy"], "MGMT": ["consulting", "entre"], "MKTG": ["consulting"],
    "OIDD": ["tech", "consulting"], "STAT": ["tech", "science"], "ECON": ["finance", "policy"],
    "MATH": ["science", "tech"], "CIS": ["tech"], "CIT": ["tech"], "ESE": ["tech"], "EAS": ["tech"],
    "MEAM": ["tech"], "ENM": ["tech"], "NETS": ["tech", "impact"], "CBE": ["science", "tech"],
    "MSE": ["science", "tech"], "BE": ["health", "tech"], "PSYC": ["science", "health"],
    "BIOL": ["science", "health"], "NRSC": ["science", "health"], "CHEM": ["science"], "PHYS": ["science"],
    "GEOL": ["science", "climate"], "ENVS": ["climate", "science"], "COGS": ["science", "tech"],
    "LING": ["science", "writing"], "NURS": ["health"], "HSOC": ["health", "culture"],
    "WRIT": ["writing"], "ENGL": ["writing", "arts"], "COMM": ["arts", "writing"], "PHIL": ["writing"],
    "HIST": ["culture", "writing"], "COML": ["writing", "culture"], "CLST": ["culture", "writing"],
    "PSCI": ["policy"], "PPE": ["policy", "finance"], "CRIM": ["policy", "impact"], "SOCI": ["impact", "science"],
    "STSC": ["science", "policy"], "CPLN": ["policy", "impact"], "URBS": ["policy", "impact"],
    "EDUC": ["edu", "impact"], "ANTH": ["culture"], "AFRC": ["culture"], "ASAM": ["culture"],
    "LALS": ["culture"], "JWST": ["culture"], "RELS": ["culture"], "GSWS": ["culture"], "NELC": ["culture"],
    "EALC": ["culture"], "SAST": ["culture"], "REES": ["culture"], "GRMN": ["culture"], "FREN": ["culture"],
    "SPAN": ["culture"], "ITAL": ["culture"], "CHIN": ["culture"], "JPAN": ["culture"], "KORN": ["culture"],
    "ARAB": ["culture"], "HEBR": ["culture"], "PORT": ["culture"], "RUSS": ["culture"], "LATN": ["culture"],
    "GREK": ["culture"], "ARTH": ["arts", "culture"], "FNAR": ["arts"], "MUSC": ["arts"], "THAR": ["arts"],
    "CINE": ["arts"], "DSGN": ["arts"], "ARCH": ["arts"], "CIMS": ["arts"],
    "LAW": ["policy"], "DENT": ["health"], "SWRK": ["impact"], "MELC": ["culture"],
}
KW = {
    "climate": r"climate|environment|energy|sustainab",
    "edu": r"education|teaching|pedagog",
    "sports": r"\bsports?\b|athlet",
    "entre": r"entrepreneur|startup|venture",
    "impact": r"nonprofit|social impact|poverty|inequality|community",
    "arts": r"\bmusic\b|\bfilm\b|\bart\b|\barts\b|design",
    "policy": r"policy|government|politic",
    "health": r"health|medic|clinical",
    "tech": r"machine learning|data science|software|programming|\bai\b",
    "finance": r"invest|financ|valuation|trading",
}

# "REQUIRED Prerequisites: MATH 1080 OR MATH 1410 ---" and similar lines inside the description
PRE_RE = re.compile(r"(?i)\b(required|recommended)?\s*prerequisites?\s*:\s*([^\n]+?)\s*(?:-{3,}|\n|$)")
DASHES = re.compile(r"-{3,}")

def split_prereq(text):
    """Return (description without prerequisite lines, prerequisite text or None)."""
    text = text or ""
    required, recommended = [], []
    for m in PRE_RE.finditer(text):
        body = re.sub(r"\s+", " ", m.group(2)).strip(" .;")
        body = re.sub(r"\b([A-Z]{2,5})(\d{4})\b", r"\1 \2", body)
        if not body:
            continue
        (recommended if (m.group(1) or "").lower() == "recommended" else required).append(body)
    clean = PRE_RE.sub(" ", text)
    clean = DASHES.sub(" ", clean)
    pre = None
    if required:
        pre = "; ".join(required)
    elif recommended:
        pre = "Recommended: " + "; ".join(recommended)
    if pre and len(pre) > 170:
        pre = pre[:167].rsplit(" ", 1)[0] + "..."
    return clean, pre

def short(text, n=240):
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if len(text) <= n:
        return text
    return text[:n].rsplit(" ", 1)[0] + "..."

src = json.loads(SRC.read_text(encoding="utf-8"))
out = []
for c in src:
    n = c.get("number")
    if n is None:
        continue
    rt = c.get("ratings") or {}
    r = [rt.get("quality"), rt.get("instructor"), rt.get("difficulty"), rt.get("workload")]
    r = [round(v, 2) if v is not None else None for v in r]
    title = c["title"].split(": ", 1)[-1]
    desc_clean, pre = split_prereq(c.get("description"))
    text = (title + " " + desc_clean).lower()
    interests = list(DEPT.get(c["dept"], []))
    for k, pat in KW.items():
        if k not in interests and re.search(pat, text):
            interests.append(k)
    code = c["id"].replace("course-", "", 1)
    rec = {
        "id": code, "dept": c["dept"], "num": n, "title": title,
        "desc": short(desc_clean), "credits": c.get("credits"),
        "sems": (c.get("semesters") or [])[-3:], "r": r, "interests": interests[:4],
    }
    if pre:
        rec["pre"] = pre
    out.append(rec)

out.sort(key=lambda x: (x["dept"], x["num"]))
ug = [c for c in out if c["num"] < 5000]
grad = [c for c in out if c["num"] >= 5000]
OUT_UG.write_text(json.dumps(ug, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
OUT_GRAD.write_text(json.dumps(grad, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

meta = json.loads(META.read_text(encoding="utf-8")) if META.exists() else {}
meta["courses_updated"] = datetime.date.today().isoformat()
META.write_text(json.dumps(meta), encoding="utf-8")

unlabeled = [c for c in ug if not c["interests"]]
with_pre = [c for c in ug if c.get("pre")]
print("courses written:", len(out), "of", len(src), "(courses without a numeric course number are skipped)")
print("undergraduate file:", len(ug), "courses,", OUT_UG.stat().st_size // 1024, "KB")
print("graduate file:", len(grad), "courses,", OUT_GRAD.stat().st_size // 1024, "KB")
print("undergraduate with difficulty and workload ratings:", sum(1 for c in ug if c["r"][2] is not None and c["r"][3] is not None))
print("undergraduate with no interest label:", len(unlabeled))
print("undergraduate courses with a prerequisite line:", len(with_pre), "of", len(ug))
print("\nprerequisite examples (check these look right):")
random.seed(1)
for c in random.sample(with_pre, min(10, len(with_pre))):
    print(f"  {c['dept']} {c['num']:04d}: {c['pre']}")