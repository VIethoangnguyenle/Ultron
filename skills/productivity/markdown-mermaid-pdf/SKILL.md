---
name: markdown-mermaid-pdf
description: "Use when rendering Markdown with mermaid diagrams to PDF."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [pdf, mermaid, markdown, diagram, render, document]
    related_skills: [pdf, architecture-diagram]
---

# Markdown (+ mermaid) → PDF — fast offline render

Turn a Markdown file containing ```mermaid fenced blocks into a PDF in well under a second.
Used whenever Hoang (or a tester/dev teammate) needs a flow/mechanism explained as a
markdown file with sequence/flowchart diagrams delivered as a PDF to a Google Chat group.

## The script

`~/.hermes/scripts/md2pdf.py input.md [-o out.pdf] [--css extra.css] [--title T]`

Pipeline: markdown → HTML (python-markdown, extensions `fenced_code,tables,sane_lists,nl2br`)
→ wrap `language-mermaid` code blocks as `<pre class="mermaid">` → inline LOCAL `mermaid.min.js`
→ `google-chrome --headless --print-to-pdf --virtual-time-budget=10000`. Zero network.

## Why NOT mmdc (mermaid-cli) — critical pitfall

`mmdc` is installed globally BUT does NOT work on this box: it bundles `puppeteer-core` 25.x,
which cannot launch the system Chrome 114 (`google-chrome --version` → 114.0.5735.133). Running
`mmdc` hangs 30s then throws `TimeoutError: Timed out after waiting 30000ms`. Do NOT use mmdc.

Chrome 114's native `--headless --print-to-pdf` works fine (sub-second), so the script drives
Chrome directly and renders mermaid in-browser. mermaid.js is a 3.5MB UMD bundle vendored at
`~/.hermes/scripts/assets/mermaid.min.js` (copied from mermaid-cli's node_modules so an npm
update doesn't move it out from under the script).

## The old slow path (do not repeat)

A previous render took ~6 minutes by loading `mermaid.js` from CDN in headless Chrome. Root
causes: CDN fetch (3.5MB + fonts) over a slow link + cold Chrome start. The fix removes BOTH:
mermaid is local, and Chrome prints straight to PDF. New render: ~0.4s.

## Recover if mermaid.min.js goes missing

```bash
cp ~/.local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js \
   ~/.hermes/scripts/assets/mermaid.min.js
```

## Verify the render

`pdftotext out.pdf -` (or `pdf_read.py` from the pdf skill) and check the diagram text — if it
shows participant names + messages (not the raw `sequenceDiagram`/`->>` source), mermaid
rendered. For visual QA export a PNG (`pdftoppm -png -r 100 out.pdf page`) and inspect.
