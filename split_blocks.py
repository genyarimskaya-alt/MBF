import requests
from PIL import Image, ImageFilter
import numpy as np
import io
import os

os.makedirs('./blocks', exist_ok=True)

# Download
url = "https://con.xlcrm.ai/WcWfHEjcdk2BCr7W486wPg/images/bACNoDOhdkueRBrbXwoGqg.jpg"
r = requests.get(url, timeout=30)
img = Image.open(io.BytesIO(r.content)).convert("RGB")
w, h = img.size
print(f"Original size: {w}x{h}")

# Convert to numpy for analysis
arr = np.array(img)

# Detect horizontal separators by scanning rows for uniform color (bg color)
# Calculate row variance — low variance = likely a separator/background row
row_var = arr.var(axis=(1, 2))

# Smooth variance curve
from scipy.ndimage import uniform_filter1d
smoothed = uniform_filter1d(row_var.astype(float), size=5)

# Find local minima (separator regions)
threshold = np.percentile(smoothed, 15)  # bottom 15% = likely bg rows

# Build segments: find runs of "bg" rows
in_bg = smoothed < threshold
segments = []
in_block = False
block_start = 0

for i in range(len(in_bg)):
    if not in_bg[i] and not in_block:
        in_block = True
        block_start = i
    elif in_bg[i] and in_block:
        in_block = False
        if i - block_start > 30:  # min block height 30px
            segments.append((block_start, i))

if in_block and h - block_start > 30:
    segments.append((block_start, h))

# Merge segments that are too close (within 20px)
merged = []
for seg in segments:
    if merged and seg[0] - merged[-1][1] < 20:
        merged[-1] = (merged[-1][0], seg[1])
    else:
        merged.append(list(seg))

print(f"Found {len(merged)} blocks")

# Save blocks and build HTML
TARGET_W = 800
html_parts = ['<!DOCTYPE html><html><head><meta charset="UTF-8">',
              '<style>body{background:#222;font-family:sans-serif;padding:20px;}',
              'figure{margin:0 0 40px;border:1px solid #444;border-radius:8px;overflow:hidden;}',
              'figcaption{background:#333;color:#ccc;padding:8px 16px;font-size:14px;}',
              'img{display:block;max-width:100%;}',
              '</style></head><body>']

for idx, (y0, y1) in enumerate(merged, 1):
    crop = img.crop((0, y0, w, y1))
    cw, ch = crop.size
    # Upscale if narrower than TARGET_W
    if cw < TARGET_W:
        scale = TARGET_W / cw
        crop = crop.resize((int(cw*scale), int(ch*scale)), Image.LANCZOS)
    fname = f"block_{idx:02d}.png"
    crop.save(f"./blocks/{fname}")
    nw, nh = crop.size
    html_parts.append(f'<figure>')
    html_parts.append(f'<figcaption>Block {idx:02d} — original y:{y0}–{y1} ({y1-y0}px tall) → saved {nw}×{nh}px</figcaption>')
    html_parts.append(f'<img src="blocks/{fname}" alt="Block {idx}">')
    html_parts.append(f'</figure>')
    print(f"  block_{idx:02d}.png  y:{y0}-{y1}  saved as {nw}x{nh}")

html_parts.append('</body></html>')
with open('./preview.html', 'w') as f:
    f.write('\n'.join(html_parts))

print("Done — preview.html created")
