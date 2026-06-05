#!/usr/bin/env python3
"""
Split infographic into semantic blocks.
Usage:
  python split_blocks.py <image_path>          # local file
  python split_blocks.py                        # tries ./source.png or ./source.jpg
"""

import sys
import os
from PIL import Image

# ── locate source image ────────────────────────────────────────────────────
path = sys.argv[1] if len(sys.argv) > 1 else None
if not path:
    for candidate in ("source.png", "source.jpg", "source.jpeg"):
        if os.path.exists(candidate):
            path = candidate
            break
if not path or not os.path.exists(path):
    print("ERROR: provide image path as argument, e.g.:")
    print("  python split_blocks.py myimage.png")
    sys.exit(1)

img = Image.open(path).convert("RGB")
W, H = img.size
print(f"Loaded: {path}  ({W}x{H}px)")

os.makedirs("blocks", exist_ok=True)

# ── auto-detect horizontal cuts via row brightness variance ────────────────
def row_variance(im, y):
    row = list(im.crop((0, y, im.width, y + 1)).getdata())
    mean = sum(sum(p) / 3 for p in row) / len(row)
    return sum((sum(p) / 3 - mean) ** 2 for p in row) / len(row)

print("Scanning rows for separators...")
variances = []
for y in range(0, H, 2):
    variances.append((y, row_variance(img, y)))

# smooth
WINDOW = 10
smoothed = []
for i, (y, v) in enumerate(variances):
    s = max(0, i - WINDOW)
    e = min(len(variances), i + WINDOW + 1)
    avg = sum(vv for _, vv in variances[s:e]) / (e - s)
    smoothed.append((y, avg))

max_var = max(v for _, v in smoothed) or 1
threshold = max_var * 0.10

in_sep = False
sep_start = 0
separators = []
for y, v in smoothed:
    if v < threshold and not in_sep:
        in_sep = True
        sep_start = y
    elif v >= threshold and in_sep:
        in_sep = False
        if y - sep_start >= 4:
            separators.append((sep_start, y))

cuts = [0] + [int((a + b) / 2) for a, b in separators] + [H]
auto_blocks = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)
               if cuts[i + 1] - cuts[i] > 20]

# ── manual layout fallback ─────────────────────────────────────────────────
# Visual analysis of the infographic layout (proportional):
#
#  0.00 ┬─────────────────────────────────────────────────┐
#       │  TITLE: "Erkennst du dich..."                   │
#  0.13 ├──────────────────────┬──────────────────────────┤
#       │ Row1-L: Fotos        │ Row1-R: Kiefer klickt    │
#  0.38 ├──────────────────────┼──────────────────────────┤
#       │ Row2-L: Gesichts-    │ Row2-R: Kiefer spannt    │
#  0.62 ├──────────────────────┼──────────────────────────┤
#       │ Row3-L: Wangen       │ Row3-R: Morgens Spannung │
#  0.84 ├──────────────────────┴──────────────────────────┤
#       │ Row4-L: Bessere Seite│ Row4-R: Im Video         │
#  0.84 ├─────────────────────────────────────────────────┤
#       │  FOOTER: dark bar                               │
#  1.00 └─────────────────────────────────────────────────┘

def manual_blocks(W, H):
    row_cuts = [0.00, 0.13, 0.355, 0.570, 0.775, 0.915, 1.00]
    rows = [(int(row_cuts[i] * H), int(row_cuts[i+1] * H))
            for i in range(len(row_cuts) - 1)]
    mid = W // 2

    result = []
    # Row 0: full-width title
    y0, y1 = rows[0]
    result.append(dict(x0=0, y0=y0, x1=W, y1=y1, label="Header – Titel"))

    card_labels = [
        ("Fotos schwerer als im Spiegel",   "Kiefer klickt beim Kauen"),
        ("Eine Gesichtshaelfte anders",      "Kiefer spannt sich an"),
        ("Wangen fallen tiefer",             "Morgens Spannung im Kiefer"),
        ("Bessere Seite – dreht sich auto.", "Im Video anderes Gesicht"),
    ]
    for i in range(1, 5):
        y0, y1 = rows[i]
        ll, lr = card_labels[i - 1]
        result.append(dict(x0=0,   y0=y0, x1=mid, y1=y1, label=ll))
        result.append(dict(x0=mid, y0=y0, x1=W,   y1=y1, label=lr))

    # Row 5: footer
    y0, y1 = rows[5]
    result.append(dict(x0=0, y0=y0, x1=W, y1=y1, label="Footer – Schlussplatte"))
    return result

if len(auto_blocks) >= 4:
    print(f"Auto-detect: {len(auto_blocks)} horizontal bands found")
    block_defs = [dict(x0=0, y0=y0, x1=W, y1=y1, label=f"band {i+1}")
                  for i, (y0, y1) in enumerate(auto_blocks)]
else:
    print(f"Auto-detect: only {len(auto_blocks)} bands — using manual layout")
    block_defs = manual_blocks(W, H)

# ── crop, upscale to min 800px wide, save ─────────────────────────────────
TARGET_W = 800
saved = []

for idx, bd in enumerate(block_defs, 1):
    crop = img.crop((bd["x0"], bd["y0"], bd["x1"], bd["y1"]))
    cw, ch = crop.size
    if cw < TARGET_W:
        scale = TARGET_W / cw
        crop = crop.resize((round(cw * scale), round(ch * scale)), Image.LANCZOS)
    fname = f"block_{idx:02d}.png"
    fpath = os.path.join("blocks", fname)
    crop.save(fpath, optimize=True)
    nw, nh = crop.size
    print(f"  {fname}  [{bd['label']}]  -> {nw}x{nh}px")
    saved.append(dict(fname=fname, label=bd["label"], w=nw, h=nh))

# ── build preview.html ─────────────────────────────────────────────────────
lines = [
    "<!DOCTYPE html>",
    '<html lang="de"><head><meta charset="UTF-8">',
    "<title>Block Preview</title>",
    "<style>",
    "  * { box-sizing: border-box; margin: 0; padding: 0; }",
    "  body { background: #111; font-family: 'Segoe UI', sans-serif; padding: 40px 24px; }",
    "  h1 { color: #fff; margin-bottom: 32px; font-size: 20px; }",
    "  figure { margin-bottom: 48px; border-radius: 12px; overflow: hidden;",
    "           box-shadow: 0 4px 24px rgba(0,0,0,.5); }",
    "  figcaption { background: #222; color: #aaa; padding: 10px 18px; font-size: 13px; }",
    "  figcaption strong { color: #fff; font-size: 15px; margin-right: 10px; }",
    "  figcaption span { color: #666; }",
    "  img { display: block; width: 100%; height: auto; }",
    "</style></head><body>",
    f'<h1>Preview — {len(saved)} blocks from {os.path.basename(path)}</h1>',
]
for s in saved:
    lines += [
        "<figure>",
        f'  <figcaption><strong>{s["fname"]}</strong>{s["label"]}'
        f'  <span>({s["w"]}x{s["h"]}px)</span></figcaption>',
        f'  <img src="blocks/{s["fname"]}" alt="{s["label"]}">',
        "</figure>",
    ]
lines.append("</body></html>")

with open("preview.html", "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"\nDone — {len(saved)} blocks in ./blocks/")
print("Open preview.html in a browser.")
