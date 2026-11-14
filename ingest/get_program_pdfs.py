import re, shutil, sys, time, webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEST = ROOT / "data" / "raw" / "concentrations"
DOWNLOADS = Path.home() / "Downloads"
URL = "https://catalog.upenn.edu/undergraduate/programs/{0}/{0}.pdf"

# Wharton concentration pages. Some names may have changed since the lists I could see,
# so a tab that says "not found" means that concentration was renamed. Check the live list at
# https://catalog.upenn.edu/undergraduate/wharton/concentrations/ and tell me its address.
SLUGS = [
    "accounting-bs", "behavioral-economics-bs", "business-analytics-bs", "business-economics-public-policy-bs",
    "entrepreneurship-innovation-bs", "finance-bs", "health-care-management-policy-bs",
    "impact-value-sustainable-business-bs", "artificial-intelligence-business-bs", "individualized-bs",
    "legal-studies-business-ethics-bs", "management-general-track-bs", "management-multinational-management-track-bs",
    "management-organizational-effectiveness-track-bs", "management-strategic-management-track-bs",
    "marketing-bs", "marketing-communication-bs", "marketing-operations-management-bs",
    "operations-information-decisions-general-track-bs", "operations-information-decisions-decision-processes-track-bs",
    "operations-information-decisions-information-systems-track-bs",
    "operations-information-decisions-operations-management-science-track-bs",
    "real-estate-bs", "retailing-bs", "leading-across-differences-bs", "statistics-data-science-bs",
]


def open_all():
    print("Before you start, make your browser download PDFs instead of showing them:")
    print("  Chrome: Settings > Privacy and security > Site settings > Additional content settings > PDF documents > Download PDFs")
    print("  Edge:   Settings > Cookies and site permissions > PDF documents > Always download PDF files")
    input("\nPress Enter when that is set. ")
    force = len(sys.argv) > 1 and sys.argv[1] == "all"
    todo = [s for s in SLUGS if force or not (DEST / f"{s}.pdf").exists()]
    if not todo:
        print("Every PDF is already saved. Use  python ingest/get_program_pdfs.py all  to download them again.")
        return
    print(f"Opening {len(todo)} links.")
    batch = 6
    for i in range(0, len(todo), batch):
        for slug in todo[i:i + batch]:
            webbrowser.open(URL.format(slug))
            time.sleep(1.2)
        print(f"Opened {min(i + batch, len(todo))} of {len(todo)}.")
        if i + batch < len(todo):
            input("Press Enter for the next batch. ")
    print("\nWhen the downloads finish, run:  python ingest/get_program_pdfs.py collect")


def first_page_text(path):
    try:
        from pypdf import PdfReader
        return PdfReader(str(path)).pages[0].extract_text() or ""
    except Exception:
        return ""


def slug_from_text(text):
    for line in text.split("\n")[:10]:
        line = re.sub(r"\s+", " ", line).strip()
        m = re.match(r"^(.*?),\s*(?:BS|BA|BSE|Minor)\b(.*)$", line)
        if m:
            rest = re.sub(r"\s+\d+$", "", m.group(2)).strip()
            name = m.group(1) + (" " + rest if rest.startswith(":") else "")
            return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or None
    return None


def collect():
    DEST.mkdir(parents=True, exist_ok=True)
    found, used = [], set()
    # 1. files that kept the catalog's own names
    for slug in SLUGS:
        cands = [p for p in DOWNLOADS.glob("*.pdf") if re.fullmatch(re.escape(slug) + r"(?: \(\d+\))?\.pdf", p.name)]
        if cands:
            newest = max(cands, key=lambda p: p.stat().st_mtime)
            shutil.copy2(newest, DEST / f"{slug}.pdf")
            found.append(slug)
            used.update(cands)
    # 2. recent PDFs with other names: recognise Wharton program PDFs by what is inside them
    recent = [p for p in DOWNLOADS.glob("*.pdf") if p not in used and time.time() - p.stat().st_mtime < 6 * 3600]
    by_content = []
    for p in recent:
        text = first_page_text(p)
        if "Other Wharton Requirements" in text:
            slug = slug_from_text(text) or re.sub(r"[^a-z0-9]+", "-", p.stem.lower()).strip("-")
            shutil.copy2(p, DEST / f"{slug}.pdf")
            by_content.append((p.name, slug))
    print(f"Copied {len(found)} PDFs by file name and {len(by_content)} by what is inside them, into {DEST.relative_to(ROOT)}.")
    for old, new in by_content:
        print(f"   {old}  ->  {new}.pdf")
    have = {f.stem for f in DEST.glob("*.pdf")}
    missing = [s for s in SLUGS if s not in have]
    if missing:
        print(f"\nStill missing ({len(missing)}):")
        for m in missing:
            print("  ", m, "  ->  ", URL.format(m))
    if not found and not by_content:
        print(f"\nNo catalog PDFs were found in {DOWNLOADS}. The 12 newest PDFs there are:")
        pdfs = sorted(DOWNLOADS.glob("*.pdf"), key=lambda p: p.stat().st_mtime, reverse=True)[:12]
        for p in pdfs:
            print("  ", time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime)), p.name)
        if not pdfs:
            print("   (none)")
        print("\nIf the links opened in browser tabs instead of downloading, press Ctrl+S on each tab, or set your browser to download PDFs and run the first command again.")
    print("\nNext:  python ingest/parse_programs.py")


if __name__ == "__main__":
    collect() if len(sys.argv) > 1 and sys.argv[1] == "collect" else open_all()