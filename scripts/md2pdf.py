#!/usr/bin/env python3
"""Render a Markdown file (with ```mermaid fenced blocks) to PDF — fast, offline.

Pipeline: markdown -> HTML (python-markdown) -> inline local mermaid.min.js
-> chrome --headless --print-to-pdf. No CDN, no Puppeteer, no network.

Replaces the old ~6-minute "chrome headless + mermaid from CDN" path with a
sub-second local render (mermaid.js is bundled at scripts/assets/mermaid.min.js).

Usage:
    md2pdf.py input.md [-o output.pdf] [--css extra.css] [--title "..."]

The mermaid CLI (mmdc) is NOT used here: mmdc bundles puppeteer-core 25.x which
cannot launch the system Chrome 114, so we render mermaid in-browser and print
straight to PDF with Chrome's native headless mode.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
MERMAID_JS = HERMES_HOME / "scripts" / "assets" / "mermaid.min.js"
CHROME = "/usr/bin/google-chrome"

_DEFAULT_CSS = """
@page { size: A4; margin: 18mm 16mm; }
body { font-family: 'Helvetica Neue', Arial, sans-serif; font-size: 11pt;
       line-height: 1.55; color: #1a1a1a; }
h1 { font-size: 20pt; border-bottom: 2px solid #eee; padding-bottom: 6px; }
h2 { font-size: 15pt; margin-top: 22px; }
h3 { font-size: 13pt; }
pre, code { font-family: 'JetBrains Mono', 'Fira Code', Consolas, monospace; }
pre.mermaid { background: #fff; border: 1px solid #e5e5e5; border-radius: 6px;
              padding: 12px; overflow-x: auto; }
pre:not(.mermaid) { background: #f6f8fa; border: 1px solid #e5e5e5;
                    border-radius: 6px; padding: 10px; overflow-x: auto; }
code { background: #f6f8fa; padding: 1px 4px; border-radius: 3px; font-size: 9.5pt; }
table { border-collapse: collapse; margin: 12px 0; }
th, td { border: 1px solid #ddd; padding: 6px 10px; text-align: left; }
th { background: #f2f4f6; }
img { max-width: 100%; }
"""


def _wrap_mermaid_blocks(body: str) -> str:
    """Convert ``<pre><code class="language-mermaid">...</code></pre>`` (output of
    python-markdown's fenced_code) into ``<pre class="mermaid">...</pre>`` that mermaid
    will render in the browser. HTML-unescape the inner code first."""
    pattern = re.compile(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        re.DOTALL,
    )

    def _repl(m: re.Match) -> str:
        code = html.unescape(m.group(1))
        return f'<pre class="mermaid">{code}</pre>'

    return pattern.sub(_repl, body)


def markdown_to_html(md_text: str) -> str:
    import markdown as md

    body = md.markdown(
        md_text,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
    )
    return _wrap_mermaid_blocks(body)


def build_html(md_text: str, title: str, extra_css: str) -> str:
    body = markdown_to_html(md_text)
    css = _DEFAULT_CSS + "\n" + extra_css
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>{css}</style>
</head>
<body>
{body}
<script>{_load_mermaid_js()}</script>
<script>mermaid.initialize({{startOnLoad:true, theme:'default', securityLevel:'loose'}});</script>
</body></html>"""


def _load_mermaid_js() -> str:
    if not MERMAID_JS.exists():
        raise SystemExit(
            f"mermaid.min.js not found at {MERMAID_JS}. "
            "Copy it from the mermaid-cli node_modules (see skill md2pdf)."
        )
    return MERMAID_JS.read_text(encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Markdown (+mermaid) -> PDF, offline & fast.")
    ap.add_argument("input", help="Markdown file to render")
    ap.add_argument("-o", "--output", help="Output PDF path (default: input stem + .pdf)")
    ap.add_argument("--css", default="", help="Extra CSS to append")
    ap.add_argument("--title", default="", help="Document title (default: first H1 or filename)")
    ap.add_argument("--time-budget-ms", type=int, default=10000,
                    help="Chrome virtual-time budget ms for mermaid to render (default 10000)")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        ap.error(f"input not found: {src}")
    md_text = src.read_text(encoding="utf-8")

    title = args.title or _first_heading(md_text) or src.stem.replace("_", " ").title()
    html_text = build_html(md_text, title, args.css)

    out = Path(args.output) if args.output else src.with_suffix(".pdf")
    tmp_html = out.with_suffix(".html")

    tmp_html.write_text(html_text, encoding="utf-8")
    cmd = [
        CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-pdf-header-footer",
        f"--virtual-time-budget={args.time_budget_ms}",
        f"--print-to-pdf={out}",
        str(tmp_html),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=120)
    except subprocess.CalledProcessError as e:
        sys.stderr.write((e.stderr or "")[-2000:])
        return 1
    finally:
        tmp_html.unlink(missing_ok=True)

    if not out.exists() or out.stat().st_size == 0:
        sys.stderr.write(f"PDF not produced: {out}\n")
        return 1
    print(out)
    return 0


def _first_heading(md_text: str) -> str:
    m = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    return m.group(1).strip() if m else ""


if __name__ == "__main__":
    sys.exit(main())
