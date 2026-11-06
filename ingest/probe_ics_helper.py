import re, sys
from pathlib import Path
from bs4 import BeautifulSoup
sys.stdout.reconfigure(encoding="utf-8")

html = (Path(__file__).resolve().parent.parent / "data" / "raw" / "ics_helper.html").read_text(encoding="utf-8", errors="ignore")
soup = BeautifulSoup(html, "html.parser")

def mask(h):
    return re.sub(r"[0-9a-fA-F]{16,}", "<token>", h)

links = [a for a in soup.find_all("a", href=True) if "ical" in a["href"].lower() or ".ics" in a["href"].lower()]
print("calendar links found:", len(links))

rows = soup.find_all("tr")
print("table rows:", len(rows))

shown = 0
for tr in rows:
    if not any(("ical" in a["href"].lower() or ".ics" in a["href"].lower()) for a in tr.find_all("a", href=True)):
        continue
    cells = [re.sub(r"\s+", " ", td.get_text(" ", strip=True)) for td in tr.find_all("td")]
    hrefs = [mask(a["href"])[:110] for a in tr.find_all("a", href=True)
             if "ical" in a["href"].lower() or ".ics" in a["href"].lower()]
    print("\nCELLS:", cells[:3])
    print("LINKS:", hrefs)
    shown += 1
    if shown >= 6:
        break

types = re.findall(r"(Undergraduate Student Clubs|MBA Student Clubs|Other MBA Groups|Executive MBA[^<\n]{0,40}|Doctoral[^<\n]{0,40}|Staff[^<\n]{0,40})", html)
from collections import Counter
print("\ngroup type labels found:", Counter(types).most_common(10))