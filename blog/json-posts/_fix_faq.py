import json
import re

path = r"d:\MYROBOTS\DIVAR-SCRAPER\django\blog\json-posts\tahlil-agahi-divar-gheymat-mahalle.json"

with open(path, encoding="utf-8") as f:
    data = json.load(f)

c = data["article"]["content"]

# Fix corrupted schema.org itemtype (editor pasted markdown links into attributes)
c = re.sub(
    r'itemtype="\[https://schema\.org/(FAQPage|Question|Answer)\\+">',
    r'itemtype="https://schema.org/\1">',
    c,
)
c = re.sub(
    r'itemtype="\[https://schema\.org/(FAQPage|Question|Answer)\\*">',
    r'itemtype="https://schema.org/\1">',
    c,
)

data["article"]["content"] = c

with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=4)
    f.write("\n")

json.load(open(path, encoding="utf-8"))
if "[https://schema.org" in c:
    raise SystemExit("still corrupted: " + c[c.find("[https"):c.find("[https")+80])
print("OK")
