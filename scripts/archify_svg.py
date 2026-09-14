#!/usr/bin/env python3
"""Cầu nối Archify -> SVG (và PNG) cho pipeline Markdown -> PDF.

Archify render ra một file HTML đầy đủ (CSS nằm ở <head>, sơ đồ là <svg> trong
<body>). Markdown chỉ nhúng được ảnh, nên script này:
    1. gọi `node bin/archify.mjs render <type> <json> <tmp.html>`
    2. cắt lấy phần tử <svg> cấp cao nhất đầu tiên
    3. gấp toàn bộ <style> của <head> vào trong <svg> -> file SVG self-contained
    4. (tuỳ chọn) rasterize bằng Chrome headless, đúng cách scripts/md2pdf.py dùng

Chỉ dùng standard library. Không sửa gì trong bản vendor của Archify.

Usage:
    archify_svg.py --type architecture --json in.json --out out.svg
                   [--png out.png] [--html keep.html] [--theme light|dark]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Bản vendor read-only của Archify; đổi được bằng biến môi trường ARCHIFY_DIR.
ARCHIFY_DIR = Path(os.environ.get("ARCHIFY_DIR", "/home/zane/.hermes/vendor/archify"))
TYPES = ["architecture", "workflow", "sequence", "dataflow", "lifecycle"]

# Chrome lấy y như scripts/md2pdf.py (binary cố định, headless cũ, no-sandbox).
CHROME = "/usr/bin/google-chrome"


class Fail(Exception):
    """Lỗi có thông điệp gọn để in ra JSON, không lòi traceback."""


# ---------------------------------------------------------------- bước 1: render

def run_archify(dtype: str, src_json: Path, out_html: Path) -> None:
    """Gọi CLI Archify để render HTML. Lỗi thì in stderr của nó rồi báo Fail."""
    cli = ARCHIFY_DIR / "bin" / "archify.mjs"
    if not cli.exists():
        raise Fail(f"archify CLI not found: {cli}")
    cmd = ["node", str(cli), "render", dtype, str(src_json), str(out_html),
           "--quality", "standard"]
    proc = subprocess.run(cmd, cwd=str(ARCHIFY_DIR), capture_output=True,
                          text=True, timeout=300)
    if proc.returncode != 0:
        sys.stderr.write((proc.stdout or "")[-4000:])
        sys.stderr.write((proc.stderr or "")[-4000:])
        raise Fail(f"archify render {dtype} failed (exit {proc.returncode})")
    if not out_html.exists() or out_html.stat().st_size == 0:
        raise Fail(f"archify produced no HTML: {out_html}")


# ------------------------------------------------- bước 2: cắt <svg> khỏi HTML

_SKIP_BLOCK = re.compile(r"<(script|style)\b[^>]*>.*?</\1\s*>|<!--.*?-->",
                         re.IGNORECASE | re.DOTALL)


def _find_svg_start(text: str) -> int:
    """Vị trí thẻ <svg> đầu tiên nằm NGOÀI <script>/<style>/comment."""
    blocked = [(m.start(), m.end()) for m in _SKIP_BLOCK.finditer(text)]
    pos = 0
    while True:
        i = text.find("<svg", pos)
        if i < 0:
            return -1
        if i + 4 < len(text) and (text[i + 4].isalnum() or text[i + 4] in "-_:"):
            pos = i + 4  # <svgfoo>, không phải thẻ svg
            continue
        if any(a <= i < b for a, b in blocked):
            pos = i + 4
            continue
        return i


def _tag_end(text: str, start: int) -> int:
    """Chỉ số ngay sau '>' của thẻ mở bắt đầu tại start (bỏ qua '>' trong ngoặc kép)."""
    quote = ""
    for i in range(start, len(text)):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == ">":
            return i + 1
    raise Fail("unterminated <svg> tag in archify HTML")


def extract_svg(html_text: str) -> tuple[str, str]:
    """Trả về (open_tag, inner_html) của <svg> cấp cao nhất đầu tiên.

    Đếm thẻ lồng nhau vì Archify có <svg> con (icon, brand mark) bên trong.
    """
    start = _find_svg_start(html_text)
    if start < 0:
        raise Fail("no top-level <svg> element found in archify HTML")
    open_end = _tag_end(html_text, start)
    open_tag = html_text[start:open_end]
    if open_tag.rstrip().endswith("/>"):
        raise Fail("top-level <svg> is self-closing (empty diagram)")

    # Đếm lồng nhau: <svg> con (icon, brand mark) không được cắt nhầm thẻ đóng.
    tag_re = re.compile(r"<svg(?=[\s/>])|</svg\s*>", re.IGNORECASE)
    depth, pos = 1, open_end
    while True:
        nxt = tag_re.search(html_text, pos)
        if not nxt:
            raise Fail("unbalanced <svg> tags in archify HTML")
        if nxt.group(0).startswith("</"):
            depth -= 1
            if depth == 0:
                return open_tag, html_text[open_end:nxt.start()]
            pos = nxt.end()
            continue
        end = _tag_end(html_text, nxt.start())
        if not html_text[nxt.start():end].rstrip().endswith("/>"):
            depth += 1  # thẻ tự đóng thì không mở thêm tầng
        pos = end


def collect_head_styles(html_text: str) -> str:
    """Gom nội dung mọi <style> trong <head> để nhét vào trong <svg>."""
    head = re.search(r"<head\b[^>]*>(.*?)</head\s*>", html_text,
                     re.IGNORECASE | re.DOTALL)
    if not head:
        return ""
    blocks = re.findall(r"<style\b[^>]*>(.*?)</style\s*>", head.group(1),
                        re.IGNORECASE | re.DOTALL)
    return "\n".join(b for b in blocks if b.strip())


# --------------------------------------------- bước 2b: vá thuộc tính thẻ <svg>

def _attr(open_tag: str, name: str) -> str | None:
    m = re.search(r"\b%s\s*=\s*([\"'])(.*?)\1" % re.escape(name), open_tag,
                  re.IGNORECASE | re.DOTALL)
    return m.group(2).strip() if m else None


def _set_attr(open_tag: str, name: str, value: str) -> str:
    """Thay giá trị thuộc tính, hoặc thêm mới ngay sau '<svg'."""
    pat = re.compile(r"\b%s\s*=\s*([\"'])(.*?)\1" % re.escape(name),
                     re.IGNORECASE | re.DOTALL)
    if pat.search(open_tag):
        return pat.sub(lambda m: '%s="%s"' % (name, value), open_tag, count=1)
    return open_tag[:4] + ' %s="%s"' % (name, value) + open_tag[4:]


def _num(value: str | None) -> float | None:
    if not value:
        return None
    m = re.match(r"\s*(-?[\d.]+)", value)
    return float(m.group(1)) if m else None


def normalize_svg_tag(open_tag: str, theme: str | None) -> tuple[str, str]:
    """Bảo đảm <svg> có xmlns + viewBox + width + height. Trả về (tag, viewBox)."""
    view = _attr(open_tag, "viewBox")
    width, height = _num(_attr(open_tag, "width")), _num(_attr(open_tag, "height"))

    if view:
        parts = re.split(r"[\s,]+", view.strip())
        if len(parts) == 4:
            width = width or _num(parts[2])
            height = height or _num(parts[3])
    elif width and height:
        view = f"0 0 {width:g} {height:g}"
    else:
        raise Fail("<svg> has neither viewBox nor width/height")

    if not width or not height:
        raise Fail(f"cannot determine size from viewBox={view!r}")

    tag = _set_attr(open_tag, "viewBox", view)
    tag = _set_attr(tag, "width", f"{width:g}")
    tag = _set_attr(tag, "height", f"{height:g}")
    if not _attr(tag, "xmlns"):
        tag = tag[:4] + ' xmlns="http://www.w3.org/2000/svg"' + tag[4:]
    if not _attr(tag, "xmlns:xlink") and "xlink:" in open_tag:
        tag = tag[:4] + ' xmlns:xlink="http://www.w3.org/1999/xlink"' + tag[4:]
    if theme:
        # CSS của Archify chọn màu qua [data-theme=...]; trong SVG rời, :root
        # chính là thẻ <svg> nên đặt thuộc tính ở đây là đổi được cả bảng màu.
        tag = _set_attr(tag, "data-theme", theme)
    return tag, view


def build_svg(html_text: str, theme: str | None) -> tuple[str, str]:
    """Ghép file SVG self-contained. Trả về (nội dung, viewBox)."""
    open_tag, inner = extract_svg(html_text)
    open_tag, view = normalize_svg_tag(open_tag, theme)
    css = collect_head_styles(html_text)
    style = ""
    if css:
        # CDATA để CSS (có '>' , '&') không phá cú pháp XML của file SVG.
        safe = css.replace("]]>", "]] >")
        style = f"\n<style type=\"text/css\"><![CDATA[\n{safe}\n]]></style>\n"
    # Không kèm khai báo <?xml?>: file bắt đầu thẳng bằng <svg (UTF-8 là mặc định).
    return f"{open_tag}{style}{inner}</svg>\n", view


# --------------------------------------------------- bước 3: PNG bằng Chrome

def svg_to_png(svg_path: Path, png_path: Path, view_box: str) -> None:
    """Chụp SVG ra PNG bằng Chrome headless — cùng binary/cờ như md2pdf.py."""
    if not Path(CHROME).exists():
        raise Fail(f"chrome not found: {CHROME}")
    parts = re.split(r"[\s,]+", view_box.strip())
    width, height = max(1, round(float(parts[2]))), max(1, round(float(parts[3])))
    cmd = [
        CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        "--disable-dev-shm-usage", "--hide-scrollbars",
        "--default-background-color=FFFFFFFF",   # nền trắng
        "--force-device-scale-factor=2",         # deviceScaleFactor = 2
        f"--window-size={width},{height}",       # kích thước = viewBox
        "--virtual-time-budget=5000",
        f"--screenshot={png_path}",
        svg_path.resolve().as_uri(),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not png_path.exists() or png_path.stat().st_size == 0:
        sys.stderr.write((proc.stderr or "")[-2000:])
        raise Fail(f"chrome screenshot failed (exit {proc.returncode})")


# ------------------------------------------------------------------------ main

def run(args: argparse.Namespace) -> dict:
    src = Path(args.json).expanduser()
    if not src.exists():
        raise Fail(f"input json not found: {src}")
    out = Path(args.out).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="archify_svg_"))
    try:
        html_path = Path(args.html).expanduser() if args.html else tmpdir / "render.html"
        html_path.parent.mkdir(parents=True, exist_ok=True)
        run_archify(args.type, src, html_path)
        svg_text, view = build_svg(html_path.read_text(encoding="utf-8", errors="replace"),
                                   args.theme)
        out.write_text(svg_text, encoding="utf-8")

        result = {"ok": True, "type": args.type, "svg": str(out.resolve()),
                  "bytes": out.stat().st_size, "viewBox": view}
        if args.html:
            result["html"] = str(html_path.resolve())
        if args.png:
            png = Path(args.png).expanduser()
            png.parent.mkdir(parents=True, exist_ok=True)
            svg_to_png(out, png, view)
            result["png"] = str(png.resolve())
            result["png_bytes"] = png.stat().st_size
        return result
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Archify JSON -> self-contained SVG (+PNG).")
    ap.add_argument("--type", required=True, choices=TYPES)
    ap.add_argument("--json", required=True, help="Archify IR JSON input")
    ap.add_argument("--out", required=True, help="Output .svg path")
    ap.add_argument("--png", help="Also rasterize to this .png")
    ap.add_argument("--html", help="Keep the intermediate archify HTML here")
    ap.add_argument("--theme", choices=["light", "dark"],
                    help="Override diagram palette (default: as archify rendered it)")
    args = ap.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False))
        return 0
    except Fail as e:
        print(json.dumps({"ok": False, "error": str(e)}, ensure_ascii=False))
        return 1
    except subprocess.TimeoutExpired:
        print(json.dumps({"ok": False, "error": "timeout running external command"}))
        return 1
    except OSError as e:
        print(json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
