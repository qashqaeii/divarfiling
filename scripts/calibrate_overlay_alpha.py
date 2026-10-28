"""One-off: list transparent regions in PCS overlay PNG/WebP."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image
import numpy as np


def find_bands(proj, thresh=0.25, min_len=20):
    bands = []
    in_band = False
    start = 0
    for i, v in enumerate(proj):
        if v >= thresh and not in_band:
            in_band = True
            start = i
        elif v < thresh and in_band:
            if i - start >= min_len:
                bands.append((start, i - 1))
            in_band = False
    if in_band and len(proj) - start >= min_len:
        bands.append((start, len(proj) - 1))
    return bands


def main():
    path = Path(sys.argv[1])
    im = Image.open(path).convert("RGBA")
    a = np.array(im.split()[-1])
    h, w = a.shape
    transparent = a < 128
    rows = transparent.mean(axis=1)
    cols = transparent.mean(axis=0)
    yb = find_bands(rows, 0.35, 30)
    regions = []
    for y0, y1 in yb:
        slice_t = transparent[y0 : y1 + 1, :]
        col_proj = slice_t.mean(axis=0)
        for x0, x1 in find_bands(col_proj, 0.5, 15):
            area = (y1 - y0 + 1) * (x1 - x0 + 1)
            if area > 8000:
                regions.append(
                    {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "area": area}
                )
    regions.sort(key=lambda r: -r["area"])
    print(f"{path.name} size={w}x{h}")
    for r in regions[:15]:
        print(r)


if __name__ == "__main__":
    main()
