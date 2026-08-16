import json

path = r"d:\MYROBOTS\DIVAR-SCRAPER\django\blog\json-posts\tahlil-agahi-divar-gheymat-mahalle.json"
with open(path, encoding="utf-8") as f:
    data = json.load(f)
c = data["article"]["content"]
idx = c.find("blog-faq")
snippet = c[idx:idx+120]
with open(r"d:\MYROBOTS\DIVAR-SCRAPER\django\blog\json-posts\_snippet.txt", "w", encoding="utf-8") as out:
    out.write(snippet)
    out.write("\n---bytes---\n")
    out.write(repr(snippet))
