---
name: viewing-geecs-figures
description: Show a GEECS scan's analysis figures (waterfalls, averaged images, fit summaries) in the artifact gallery. Use when asked to show, view, display, or plot an analysis figure or result image from a scan. Figures are fetched by URL and saved as artifacts — never loaded into context as inline images.
---

# Viewing GEECS Scan Figures (fetch → artifact, never inline)

Scan analysis figures are pre-rendered PNGs in the experiment's analysis
tree. The `geecs` MCP tools return **references** to them, not image bytes
— `get_scan_figure`'s default result is metadata: figure label,
share-relative path, byte size, pixel dimensions, and a `figure_url`.
This is deliberate: a full-resolution figure inlined into context is tens
of thousands of tokens and can kill the session. Display happens through
the artifact gallery instead.

## Workflow

1. **Find the figure.** `get_scan_analysis(scan_number, day)` shows which
   analyzers ran and their states; `get_scan_figure(scan_number, day)`
   with no `name` lists the candidate figure labels. Pick the one matching
   what the operator asked for; if ambiguous, show the candidate list and
   ask.
2. **Get the reference.** `get_scan_figure(..., name=<label>)` returns the
   metadata dict including `figure_url` (a server-relative path like
   `/figures/2026-05-01/1/.../summary_waterfall.png`).
3. **Fetch and save as an artifact** with a readonly `execute` run. The
   figure host is the geecs MCP server without its `/mcp` suffix —
   currently `http://192.168.6.14:8100`. Append `figure_url` verbatim
   (it is already percent-encoded):

   ```python
   import io
   import urllib.request

   import matplotlib.image as mpimg
   import matplotlib.pyplot as plt

   url = "http://192.168.6.14:8100" + figure_url  # figure_url from the tool result
   data = urllib.request.urlopen(url, timeout=30).read()
   img = mpimg.imread(io.BytesIO(data), format="png")
   fig, ax = plt.subplots(
       figsize=(img.shape[1] / 100, img.shape[0] / 100), dpi=100
   )
   ax.imshow(img)
   ax.axis("off")
   fig.tight_layout(pad=0)
   save_artifact(fig, title="Scan 1 BCaveMagSpec waterfall (2026-05-01)")
   ```

   Title the artifact with scan number, figure label, and day so the
   gallery stays navigable.
4. **Report**: tell the operator the figure is in the gallery, and include
   the figure's `share_relative_path` so they can open the original file
   from the data share when full resolution matters.

## Hard rules

- **Never pass `thumbnail=true` by default.** It returns bounded inline
  image content (≤768 px JPEG) and is reserved for the rare case where
  YOU must visually inspect the figure to answer a question (e.g. "does
  the waterfall look saturated?"). Displaying to the operator is always
  the artifact path above.
- Never fetch figures by guessing URLs — only `figure_url` values returned
  by `get_scan_figure`.
- One artifact per requested figure; don't bulk-save every candidate
  unless asked.
