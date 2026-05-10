---
name: html-to-image-export
description: Export visible HTML pages, local static diagram HTML, SVG/figure sections, or selected DOM elements to PNG screenshots using a bundled Node.js and headless Chrome script. Use when Codex needs to turn .html files, file URLs, localhost pages, diagrams, charts, or repeated CSS-selected screen regions into image files for papers, docs, reports, or visual verification.
---

# HTML to Image Export

## Quick Start

Use `scripts/export_html_image.js` for deterministic PNG export without npm packages. The script launches installed Chrome or Edge in headless mode and captures either the whole page/viewport or every element matching a CSS selector.

Full-page export:

```bash
node /path/to/html-to-image-export/scripts/export_html_image.js --input page.html --out page.png --full-page --scale 2
```

Batch export repeated figures or SVG blocks:

```bash
node /path/to/html-to-image-export/scripts/export_html_image.js --input diagrams.html --selector ".figure" --out exported-png --width 1280 --height 800 --scale 2
```

Capture a running app page:

```bash
node /path/to/html-to-image-export/scripts/export_html_image.js --input http://localhost:3000 --wait-for-selector "#app" --out screenshot.png --width 1440 --height 1000 --scale 2
```

## Workflow

1. Identify the target source:
   - Use a local `.html` path for static diagrams or generated report pages.
   - Use `http://localhost:...` after starting the app server for dynamic frontend screens.
   - Use a CSS selector when several diagrams, figures, cards, SVGs, or panels should be exported as separate files.
2. Pick the output shape:
   - For one screenshot, pass `--out some-file.png`.
   - For selector batch export, pass `--out some-directory`; the script writes one PNG per matched element.
3. Set rendering dimensions:
   - Use `--width` and `--height` for the browser viewport.
   - Use `--scale 2` for thesis/report images that need sharper text.
   - Use `--full-page` when a page is taller than the viewport.
4. Wait for dynamic content when needed:
   - Use `--wait-for-selector` for Vue/React/app pages.
   - Use `--delay 500` or higher when animations, fonts, Mermaid, ECharts, or remote assets need extra time.
5. Verify the output dimensions and content after export. Re-run with a larger viewport or a narrower selector if text is clipped.

## Script Options

- `--input <path-or-url>`: Required. Local HTML file, `file://` URL, or `http(s)://` page.
- `--out <path>`: Output PNG path for single screenshots, or output directory for selector batch export.
- `--selector <css>`: Export each matching element as a separate PNG using its DOM bounding box.
- `--wait-for-selector <css>`: Wait until an element exists before capture.
- `--width <px>` and `--height <px>`: Viewport size. Defaults to `1280x720`.
- `--scale <number>`: Device scale factor. Defaults to `2`.
- `--full-page`: Capture the full page instead of only the viewport.
- `--delay <ms>`: Extra wait after load and fonts. Defaults to `200`.
- `--clip-padding <px>`: Add padding around selector captures. Defaults to `0`.
- `--preserve-layout`: Keep selected elements exactly in the page layout. Omit this for sharper diagram exports; selector export normally expands the target's width and overflow before capture.
- `--transparent`: Preserve transparent background where the page allows it.
- `--chrome <path>`: Explicit Chrome/Edge executable path when auto-detection fails.

## Notes

- Prefer selector export over CSS-hiding rewrites; it avoids modifying source HTML and works for repeated `.figure`, `svg`, `.diagram`, `.chart`, or app panel regions.
- Keep `--scale 2` or higher for paper/report images. The original project scripts used 2x browser rendering; `--scale 1` produces roughly half the pixels and will look softer after insertion into Word or PDF.
- Selector export uses a high-quality capture mode by default: it temporarily removes width and overflow constraints from matched elements before measuring and screenshotting them. Use `--preserve-layout` only when the exact on-page layout matters more than maximum image sharpness.
- For static HTML diagrams, opening via `file://` is usually enough. For framework apps or pages that rely on routed assets, start the dev/server process first and capture the localhost URL.
- If the script reports that no browser was found, pass `--chrome` with the installed Chrome or Edge path.
