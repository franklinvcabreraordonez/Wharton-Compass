import datetime, io, json, re, sys, collections
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
FOLDERS = {"concentration": ROOT / "data" / "raw" / "concentrations", "minor": ROOT / "data" / "raw" / "minors"}
OUT = ROOT / "data" / "programs.json"

CODE = re.compile(r"^([A-Z]{2,5})\s+(\d{4})[A-Z]?\b\s*(.*)$")
OR_CODE = re.compile(r"^or\s+([A-Z]{2,5})\s+(\d{4})[A-Z]?\b\s*(.*)$", re.I)
SELECT = re.compile(r"^(?:Select|Choose|Take|Complete|Pick)\b(.*)$", re.I)
HOME_BY_NAME = {"accounting": "ACCT", "finance": "FNCE", "management": "MGMT", "marketing": "MKTG", "operations": "OIDD",
                "retailing": "MKTG", "real estate": "REAL", "health care": "HCMG", "legal studies": "LGST", "statistics": "STAT",
                "business economics": "BEPP", "behavioral": "BEPP", "entrepreneurship": "MGMT", "business analytics": "OIDD"}
WORDNUM = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
CONNECTORS = ("and", "of", "the", "for", "in", "to", "with", "a", "an", "on", "or", "&")


def norm(dept, num):
    return f"{dept} {num}"


def clean_lines(text):
    out = []
    for l in text.split("\n"):
        l = re.sub(r"\s+", " ", l).strip()
        if l:
            out.append(l)
    return out


def program_name(lines, fallback):
    for l in lines[:8]:
        m = re.match(r"^(.*?),\s*(?:BS|BA|BSE|Minor)\b(.*)$", l)
        if m:
            rest = re.sub(r"\s+\d+$", "", m.group(2)).strip()
            return (m.group(1).strip() + (" " + rest if rest.startswith(":") else "")).replace(" :", ":")
    return fallback


def parse_program(text, fallback_name="", keep=False):
    lines = clean_lines(text)
    name = program_name(lines, fallback_name)
    ends = [i for i, l in enumerate(lines) if l.startswith("Other Wharton Requirements")]
    if ends:
        end = ends[-1]
    else:
        totals = [i for i, l in enumerate(lines) if l.startswith("Total")]
        end = totals[-1] if totals else len(lines)
    starts = [i for i in range(0, end) if lines[i].startswith("Code Title Course")]
    start = starts[-1] if starts else 0
    body = lines[start + 1:end]
    if body and body[0].lower() == "units":
        body = body[1:]

    groups, cur, last, heading = [], None, None, ""

    def add_group(kind, title, need):
        g = {"kind": kind, "title": title, "need": need, "courses": []}
        groups.append(g)
        return g

    for idx, l in enumerate(body):
        nxt = body[idx + 1] if idx + 1 < len(body) else ""
        m = SELECT.match(l)
        if m and re.search(r"following|list|from|of the", m.group(1), re.I):
            rest = m.group(1)
            word = re.search(r"\b(one|two|three|four|five|six|seven|eight)\b", rest, re.I)
            after = rest.split(":", 1)[1] if ":" in rest else rest
            nums = re.findall(r"\d+(?:\.\d+)?", after)
            cu = float(nums[-1]) if nums else float(WORDNUM[word.group(1).lower()] if word else 1)
            cur = add_group("pick", heading, cu)
            last, heading = None, ""
            continue
        m = OR_CODE.match(l)
        if m and last is not None:
            last["alts"].append(norm(m.group(1), m.group(2)))
            continue
        m = CODE.match(l)
        if m:
            title = m.group(3)
            cu = None
            tm = re.search(r"\s(\d(?:\.\d)?)$", title)
            if tm and (cur is None or cur["kind"] != "pick" or cur["courses"]):
                if cur is None or cur["kind"] == "pick":
                    cur = add_group("required", heading, 0)
                    heading = ""
                cu = float(tm.group(1))
                title = title[:tm.start()].strip()
            elif cur is None:
                cur = add_group("required", heading, 0)
                heading = ""
            course = {"code": norm(m.group(1), m.group(2)), "title": title, "alts": []}
            if cur["kind"] == "required":
                course["cu"] = cu if cu is not None else 1.0
                cur["need"] += course["cu"]
            cur["courses"].append(course)
            last = course
            continue
        # a line that is neither a course nor a Select line: a heading, or the wrapped end of a title
        words = l.split()
        looks_heading = (len(words) >= 2 and l[0].isupper() and words[-1].lower() not in CONNECTORS
                         and (SELECT.match(nxt) or CODE.match(nxt)))
        if looks_heading and SELECT.match(l):
            looks_heading = False
        if looks_heading:
            heading = l
        elif last is not None and len(last["title"]) < 110:
            last["title"] = (last["title"] + " " + l).strip()

    groups = [g for g in groups if g["courses"]]
    notes, tail, cur_note = [], lines[end + 1:], None
    for l in tail:
        if l.startswith("Course Title") or re.match(r"^(First|Second|Third|Fourth) Year", l) or "Catalog |" in l:
            if cur_note:
                notes.append(cur_note)
                cur_note = None
            if "Catalog |" in l or l.startswith("Course Title"):
                break
            continue
        nm = re.match(r"^(\d)\s+([A-Z].*)$", l)
        if nm:
            if cur_note:
                notes.append(cur_note)
            cur_note = nm.group(2)
        elif cur_note:
            cur_note += " " + l
    if cur_note:
        notes.append(cur_note)

    codes = [c["code"] for g in groups for c in g["courses"]] + [a for g in groups for c in g["courses"] for a in c["alts"]]
    depts = collections.Counter(c.split()[0] for c in codes)
    home = depts.most_common(1)[0][0] if depts else ""
    if not home:
        low = name.lower()
        home = next((v for k, v in HOME_BY_NAME.items() if low.startswith(k)), "")
    total = sum(g["need"] for g in groups)
    review, review_note = False, ""
    if not groups:
        review = True
        review_note = "Compass could not read the course list for this program. Open its catalog page to see the requirements."
        total = 0
    elif total not in (4, 8) or any(g["kind"] == "required" and len(g["courses"]) > 8 for g in groups):
        review = True
        uniq, seen = [], set()
        for c in codes:
            if c not in seen:
                seen.add(c)
                uniq.append({"code": c, "title": next((x["title"] for g in groups for x in g["courses"] if x["code"] == c), ""), "alts": []})
        groups = [{"kind": "pick", "title": "Courses on the concentration list", "need": 4.0, "courses": uniq}]
        total = 4.0
        review_note = "The catalog splits this concentration into required and elective courses. Compass shows which of your courses are on its list, but not the exact structure. Check the catalog page for what is required."
    out = {"name": name, "groups": groups, "notes": notes[:4], "home": home, "cu": total}
    if review:
        out["review"] = True
        out["review_note"] = review_note
    if keep:
        out["_section"] = body
    return out


def read_pdf(path):
    from pypdf import PdfReader
    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def main():
    try:
        import pypdf  # noqa: F401
    except ImportError:
        sys.exit("The pypdf package is missing. In this terminal run:  python -m pip install pypdf")
    programs, stamp, dump = [], None, []
    for kind, folder in FOLDERS.items():
        folder.mkdir(parents=True, exist_ok=True)
        files = sorted(folder.glob("*.pdf"))
        print(f"{kind}s: {len(files)} PDF files in {folder.relative_to(ROOT)}")
        for f in files:
            try:
                text = read_pdf(f)
            except Exception as e:
                print(f"  {f.name}: could not read ({str(e)[:60]})")
                continue
            m = re.search(r"(\d{4}-\d{2}) Catalog \| Generated (\d\d/\d\d/\d\d)", text)
            stamp = stamp or (m.group(0) if m else None)
            p = parse_program(text, f.stem.replace("-", " ").title(), keep=True)
            dump.append("=" * 70 + "\n" + f.name + "\n" + "\n".join(p.pop("_section", [])))
            p.update({"id": re.sub(r"[^a-z0-9]+", "-", f.stem.lower()).strip("-"), "kind": kind, "file": f.name,
                      "catalog": m.group(0) if m else None})
            programs.append(p)
            flag = "   [simplified to one list]" if p.get("review") and p["groups"] else ("" if p["groups"] else "   <-- nothing parsed")
            print(f"  {p['name']}: {len(p['groups'])} groups, {p['cu']:g} CU, home {p['home'] or '?'}{flag}")
            for g in p["groups"]:
                label = f"select {g['need']:g} CU" if g["kind"] == "pick" else "required"
                print(f"      {g['title'] or '(untitled)'}: {label} from {len(g['courses'])} courses")
    (ROOT / "data" / "raw" / "program_sections.txt").write_text("\n\n".join(dump), encoding="utf-8")
    OUT.write_text(json.dumps({"updated": datetime.date.today().isoformat(), "catalog": stamp, "programs": programs},
                              ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print("\nprograms written:", len(programs), "| catalog version:", stamp or "unknown")
    print("file size (KB):", OUT.stat().st_size // 1024)


if __name__ == "__main__":
    main()