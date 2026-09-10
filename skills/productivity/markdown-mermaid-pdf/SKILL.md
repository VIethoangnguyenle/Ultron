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

## Pitfalls (mmdc broken / slow CDN path)

Đã chuyển sang agentmemory lessons (context=`markdown-mermaid-pdf`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `markdown-mermaid-pdf`.

## Recover if mermaid.min.js goes missing

```bash
cp ~/.local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js \
   ~/.hermes/scripts/assets/mermaid.min.js
```

## Verify the render

`pdftotext out.pdf -` (or `pdf_read.py` from the pdf skill) and check the diagram text — if it
shows participant names + messages (not the raw `sequenceDiagram`/`->>` source), mermaid
rendered. For visual QA export a PNG (`pdftoppm -png -r 100 out.pdf page`) and inspect.
