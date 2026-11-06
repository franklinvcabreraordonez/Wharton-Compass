import datetime, io, json, re, sys, time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")
try:
    import pypdf  # noqa: F401
except ImportError:
    sys.exit("The pypdf package is missing. In this same terminal run:  python -m pip install pypdf   then run this script again.")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "course_attributes.json"
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
LOCAL = RAW / "attributes"          # PDFs you save by hand from the catalog
LOCAL.mkdir(parents=True, exist_ok=True)

# Penn's course attributes decide what a course counts for in the Wharton degree.
PDF = "https://catalog.upenn.edu/attributes/{0}/{0}.pdf"
PAGE = "https://catalog.upenn.edu/attributes/{}/"
ATTRS = {
    "WUHM": "Humanities",
    "WUNM": "Natural Science, Math & Engineering",
    "WUSS": "Social Science",
    "WUCN": "Cross-Cultural Perspectives, non-U.S.",
    "WUCU": "Cross-Cultural Perspectives, U.S. cultural diversity",
    "WUGE": "Global Economy, Business & Society",
    "WUTI": "Technology, Innovation & Analytics",
    "WUCP": "Senior Capstone",
}
# Wharton's liberal arts course list. Its page fills its table from this data address.
REPORT_DATA = "https://apps.wharton.upenn.edu/reports/2737/data/?&course_dept=all&req_satisfied=all&ccp_flag=all"
# Wharton's own pages, used only if a catalog list cannot be read.
WHARTON_PAGES = {
    "WUGE": "https://undergrad-inside.wharton.upenn.edu/global-economy-business-society/",
    "WUTI": "https://undergrad-inside.wharton.upenn.edu/technology-innovation-analytics/",
    "WUCP": "https://undergrad-inside.wharton.upenn.edu/senior-capstone/",
}

OURS = {"User-Agent": "WhartonCompass-prototype (student project)"}
CODE_AT_START = re.compile(r"^\s*([A-Z]{2,5})\s*-?\s*(\d{3,4})\b")
CODE_LINE = re.compile(r"(?m)^\s*([A-Z]{2,5})\s+(\d{4})[A-Z]?\b")
CODE_ANY = re.compile(r"\b([A-Z]{2,5})\s?(\d{4})\b")
WORDS = [("CDUS", r"cdus|u\.?s\.? cultural"), ("CCP", r"\bccp\b|cross-?cultural"), ("NSME", r"nsme|natural sci"),
         ("SS", r"\bss\b|social sci"), ("H", r"\bh\b|humanit"), ("FGE", r"\bfge\b|flex"), ("URE", r"\bure\b|unrestricted")]


def norm(dept, num):
    return f"{dept} {num.zfill(4)}"


def get(url, timeout=90):
    """Try our own identification first, then the library default. Returns (response or None, note)."""
    note = ""
    for headers in (OURS, {}):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            note = f"status {r.status_code}, {len(r.content)} bytes, {r.headers.get('content-type', '?')}"
            if r.status_code == 200 and r.content:
                return r, note
        except Exception as e:
            note = "request failed: " + str(e)[:60]
    return None, note


def codes_from_text(text, pattern=CODE_LINE):
    return {norm(m.group(1), m.group(2)) for m in pattern.finditer(text)}


def parse_pdf(content):
    from pypdf import PdfReader
    text = "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(content)).pages)
    m = re.search(r"(\d{4}-\d{2}) Catalog \| Generated (\d\d/\d\d/\d\d)", text)
    return codes_from_text(text), (m.group(0) if m else None)


def parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    codes = set()
    for tr in soup.select("table tr"):
        cells = tr.find_all(["td", "th"])
        if cells:
            m = CODE_AT_START.match(cells[0].get_text(" ", strip=True).upper())
            if m:
                codes.add(norm(*m.groups()))
    return codes or codes_from_text(soup.get_text("\n"))


def parse_report_json(payload):
    recs = payload.get("data") or payload.get("aaData") if isinstance(payload, dict) else payload
    out = {k: set() for k in ("WUHM", "WUSS", "WUNM", "FGE", "URE", "WUCN", "WUCU")}
    n, sample = 0, []
    for rec in recs or []:
        if isinstance(rec, dict):
            dept, num = str(rec.get("course_dept") or "").strip().upper(), str(rec.get("course_number") or "").strip()
            other = {k: v for k, v in rec.items() if k not in ("course_dept", "course_number", "course_title")}
        elif isinstance(rec, (list, tuple)) and len(rec) >= 4:
            dept, num = str(rec[0]).strip().upper(), str(rec[1]).strip()
            other = {str(i): v for i, v in enumerate(rec[3:])}
        else:
            continue
        m = re.match(r"(\d{3,4})", num)
        if not (re.fullmatch(r"[A-Z]{2,5}", dept) and m):
            continue
        code = norm(dept, m.group(1))
        toks = set()
        for k, v in other.items():
            val = re.sub(r"<[^>]+>", " ", str(v or "")).strip()
            if "ccp" in str(k).lower():
                if val and val.lower() not in ("0", "no", "false", "n", "none", "-"):
                    toks.add("CDUS" if ("cdus" in val.lower() or "u.s" in val.lower()) else "CCP")
            else:
                toks |= {name for name, pat in WORDS if re.search(pat, val, re.I)}
        if not toks:
            continue
        n += 1
        if "H" in toks: out["WUHM"].add(code)
        if "SS" in toks: out["WUSS"].add(code)
        if "NSME" in toks: out["WUNM"].add(code)
        if "FGE" in toks: out["FGE"].add(code)
        if "URE" in toks: out["URE"].add(code)
        if "CDUS" in toks: out["WUCU"].add(code)
        elif "CCP" in toks: out["WUCN"].add(code)
    return out, n, len(recs or [])


attrs = {a: set() for a in ATTRS}
attrs.update({"FGE": set(), "URE": set()})
stamp = None
sources = {}

print("== Penn catalog attribute lists ==")
missing_pdfs = []
for a in ATTRS:
    codes, how, note = set(), "", ""
    f = LOCAL / f"{a.lower()}.pdf"
    if f.exists() and f.stat().st_size > 1000:
        try:
            codes, gen = parse_pdf(f.read_bytes())
            how = "saved pdf"
            stamp = stamp or gen
        except Exception as e:
            note = f"could not read {f.name} ({str(e)[:60]})"
    else:
        missing_pdfs.append(a)
        r, note = get(PDF.format(a.lower()))
        if r is not None:
            try:
                codes, gen = parse_pdf(r.content)
                how, stamp = "downloaded pdf", stamp or gen
            except Exception as e:
                note += f"; could not read the PDF ({str(e)[:50]})"
    attrs[a] |= codes
    sources[a] = how or "none"
    print(f"{a}: {len(codes)} courses ({how or 'nothing read'})" + ("" if codes else f"  [{note}]"))
    time.sleep(0.2)
print("catalog version read:", stamp or "unknown")
still = [a for a in ATTRS if not attrs[a]]
if still:
    print("\nPenn's catalog does not answer scripts, so save these PDFs by hand into data/raw/attributes/ using the file names shown:")
    for a in still:
        print(f"  {a.lower()}.pdf   from   {PDF.format(a.lower())}")

print("\n== Wharton liberal arts course list ==")
r, note = get(REPORT_DATA)
if r is None:
    print("could not download:", note)
else:
    try:
        payload = r.json()
        (RAW / "wharton_las_report.json").write_text(json.dumps(payload)[:5_000_000], encoding="utf-8")
        rep, used, total = parse_report_json(payload)
        for k, v in rep.items():
            attrs[k] |= v
        print(f"records: {total}, with a requirement label: {used}")
        recs = payload.get("data") if isinstance(payload, dict) else payload
        for rec in (recs or [])[:3]:
            print("  example record:", json.dumps(rec, ensure_ascii=False)[:300])
        if used == 0:
            print("  none were readable. Send me the example records above.")
    except Exception as e:
        print("downloaded but could not read as data:", str(e)[:80], "|", r.text[:200].replace("\n", " "))

missing = [a for a in ("WUGE", "WUTI", "WUCP") if not attrs[a]]
if missing:
    print("\n== Fallback: Wharton pages for", ", ".join(missing), "(please review these) ==")
    for a in missing:
        r, note = get(WHARTON_PAGES[a])
        if r is None:
            print(f"{a}: could not download ({note})")
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        main = soup.find("main") or soup
        codes = codes_from_text(main.get_text("\n"), CODE_ANY)
        attrs[a] |= codes
        sources[a] = "wharton page"
        print(f"{a}: {len(codes)} course numbers found on the page: {', '.join(sorted(codes))}")

out = {"updated": datetime.date.today().isoformat(), "catalog": stamp, "sources": sources,
       "attrs": {k: sorted(v) for k, v in attrs.items() if v}, "labels": ATTRS}
OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

print("\n== Totals ==")
for k, v in attrs.items():
    print(f"  {k}: {len(v)}")
print("file size (KB):", OUT.stat().st_size // 1024)