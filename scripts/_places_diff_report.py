import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def idx(items):
    return {int(x["id"]): x for x in items if isinstance(x, dict) and "id" in x}


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    new = load(REPO / "config" / "places-web.json")
    old_candidates = [
        REPO / "_win-repo-check" / "config" / "places-web.json",
        REPO / "DIVAR-SCRAPER" / "config" / "places-web.json",
    ]
    old = None
    for p in old_candidates:
        if p.is_file() and idx(load(p)) != idx(new):
            old = load(p)
            print("OLD from", p)
            break
    if old is None:
        raise SystemExit("no old snapshot found")

    a, b = idx(old), idx(new)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = []
    for i in sorted(set(a) & set(b)):
        if a[i] != b[i]:
            keys = sorted(set(a[i]) | set(b[i]))
            diffs = {k: (a[i].get(k), b[i].get(k)) for k in keys if a[i].get(k) != b[i].get(k)}
            changed.append((i, a[i], b[i], diffs))

    lines = [f"=== REMOVED ({len(removed)}) ==="]
    for i in removed:
        n = a[i]
        lines.append(
            f"id={i} | name={n.get('name')} | type={n.get('type')} | parent={n.get('parent')} | slug={n.get('slug')}"
        )
    lines.append(f"\n=== ADDED ({len(added)}) ===")
    for i in added:
        n = b[i]
        lines.append(
            f"id={i} | name={n.get('name')} | type={n.get('type')} | parent={n.get('parent')} | slug={n.get('slug')}"
        )
    lines.append(f"\n=== CHANGED ({len(changed)}) ===")
    for i, orec, nrec, diffs in changed:
        lines.append(f"--- id={i} type={orec.get('type')} parent={orec.get('parent')} ---")
        for k, (ov, nv) in diffs.items():
            lines.append(f"  {k}: {ov!r} -> {nv!r}")

    out = Path(__file__).with_name("_places_diff_report.txt")
    out.write_text("\n".join(lines), encoding="utf-8")
    print("written", out)
    print("removed", len(removed), "added", len(added), "changed", len(changed))


if __name__ == "__main__":
    main()
