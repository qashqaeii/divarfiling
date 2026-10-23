import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def idx(items):
    return {int(x["id"]): x for x in items if isinstance(x, dict) and "id" in x}


def districts_under(items, city_id):
    i = idx(items)
    return {int(k): i[k] for k in i if str(i[k].get("type")) == "4" and int(i[k].get("parent") or 0) == city_id}


def main():
    old = json.loads((REPO / "_win-repo-check" / "config" / "places-web.json").read_text(encoding="utf-8"))
    new = json.loads((REPO / "config" / "places-web.json").read_text(encoding="utf-8"))
    o = districts_under(old, 1)
    n = districts_under(new, 1)
    added_names = sorted(n[i]["name"] for i in set(n) - set(o))
    removed_names = sorted(o[i]["name"] for i in set(o) - set(n))
    print("TEHRAN parent=1 district ids: old", len(o), "new", len(n))
    print("\nNEW under Tehran (by id):", len(added_names))
    for name in added_names:
        print(" +", name)
    print("\nNO LONGER under Tehran (by id):", len(removed_names))
    for name in removed_names:
        print(" -", name)

    # parent 1763 -> 1 only
    oi, ni = idx(old), idx(new)
    moved = []
    for pid in sorted(set(oi) & set(ni)):
        if oi[pid].get("parent") == 1763 and ni[pid].get("parent") == 1:
            moved.append((pid, ni[pid].get("name")))
    print("\nMOVED from city Rey(1763) to Tehran(1):", len(moved))
    for pid, name in moved:
        print(f"  id={pid} {name}")


if __name__ == "__main__":
    main()
