#!/usr/bin/env python3
"""Thêm cây bookmark (outline) 2 cấp cho PDF do Chrome headless sinh ra.

Chrome tạo được liên kết nội bộ nhưng không sinh outline. Script này hậu xử lý
file PDF: lấy cấu trúc heading (từ Markdown nguồn hoặc tự dò trong PDF), tìm số
trang thật của từng heading bằng pdftotext, rồi ghi lại PDF kèm outline.

Nội dung, số trang và annotation (link nội bộ) được giữ nguyên: writer clone
toàn bộ từ reader, chỉ thêm outline + /PageMode.

Ví dụ:
    pdf_add_outline.py in.pdf -o out.pdf --md source.md --print
    pdf_add_outline.py in.pdf -o out.pdf --auto --print
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

from pypdf import PdfReader, PdfWriter

# <h2 id="m3">3. Năng lực chức năng</h2>  -> cấp 1
RE_MD_H2_RAW = re.compile(r'<h2[^>]*>(.*?)</h2>', re.IGNORECASE | re.DOTALL)
# ### 2.1 Sơ đồ lớp                        -> cấp 2
RE_MD_H3 = re.compile(r'^###\s+(?P<title>\d+\.\d+\s+.*\S)\s*$')

# Heading trong text của PDF
RE_PDF_L1 = re.compile(r'^\d+\.\s+\S')
RE_PDF_L2 = re.compile(r'^\d+\.\d+\s+\S')

# Dòng mục lục: "3. Năng lực chức năng — tr. 4"
RE_TOC_LINE = re.compile(r'[—-]\s*tr\.\s*\d+\s*$')

TOC_MARKER = 'mục lục'


def norm(text: str) -> str:
    """Chuẩn hoá một dòng để so khớp: bỏ thẻ, giải mã entity, gộp khoảng trắng."""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def headings_from_markdown(md_path: Path) -> list[tuple[int, str]]:
    """Cấp 1 = <h2 id="mX">N. Tiêu đề</h2>; cấp 2 = ### N.M Tiêu đề."""
    headings: list[tuple[int, str]] = []
    for raw_line in md_path.read_text(encoding='utf-8').splitlines():
        line = raw_line.rstrip()
        m2 = RE_MD_H2_RAW.search(line)
        if m2:
            title = norm(m2.group(1))
            if title and TOC_MARKER not in title.lower():
                headings.append((1, title))
            continue
        m3 = RE_MD_H3.match(line)
        if m3:
            title = norm(m3.group('title'))
            if title and TOC_MARKER not in title.lower():
                headings.append((2, title))
    return headings


def page_count(pdf_path: Path) -> int:
    return len(PdfReader(str(pdf_path)).pages)


def page_lines(pdf_path: Path, page_no: int) -> list[str]:
    """Text của đúng một trang (1-based), đã chuẩn hoá từng dòng."""
    out = subprocess.run(
        ['pdftotext', '-f', str(page_no), '-l', str(page_no), str(pdf_path), '-'],
        capture_output=True, text=True, check=True,
    ).stdout
    return [norm(line) for line in out.splitlines()]


def load_pages(pdf_path: Path) -> list[list[str]]:
    return [page_lines(pdf_path, n) for n in range(1, page_count(pdf_path) + 1)]


def is_toc_page(lines: list[str]) -> bool:
    return any(TOC_MARKER == line.lower() or line.lower().startswith(TOC_MARKER)
               for line in lines)


def body_lines(lines: list[str]) -> list[str]:
    """Bỏ các dòng mục lục ("... — tr. N") để không nhận nhầm trang."""
    return [line for line in lines if line and not RE_TOC_LINE.search(line)]


def headings_from_pdf(pages: list[list[str]]) -> list[tuple[int, str]]:
    """Tự dò heading trong PDF khi không có file Markdown nguồn.

    Số hiệu mục phải tăng dần, nếu không một danh sách đánh số trong thân bài
    ("1. Nhận yêu cầu", "2. Xác định ngữ cảnh", ...) sẽ bị nhận nhầm là mục cấp 1.
    """
    headings: list[tuple[int, str]] = []
    seen: set[str] = set()
    current, sub = 0, 0
    for lines in pages:
        for line in body_lines(lines):
            if TOC_MARKER in line.lower() or line in seen:
                continue
            level, number = classify(line)
            if level == 1 and number[0] > current:
                current, sub = number[0], 0
            elif level == 2 and number[0] == current and number[1] > sub:
                sub = number[1]
            else:
                continue
            seen.add(line)
            headings.append((level, line))
    return headings


def classify(line: str) -> tuple[int, tuple[int, ...]]:
    """(cấp, số hiệu) của một dòng; cấp 0 nghĩa là không phải heading."""
    if RE_PDF_L2.match(line):
        major, minor = line.split()[0].rstrip('.').split('.')[:2]
        return 2, (int(major), int(minor))
    if RE_PDF_L1.match(line):
        return 1, (int(line.split('.')[0]), 0)
    return 0, (0, 0)


def find_page(title: str, pages: list[list[str]]) -> int | None:
    """Số trang 1-based chứa heading, ưu tiên khớp cả dòng.

    Dòng mục lục bị loại trước khi so khớp, nên trang bìa/Mục lục không bao giờ
    bị nhận nhầm chỉ vì nó liệt kê tên mục — nhưng heading nào thật sự nằm trên
    trang đó vẫn tìm ra đúng.
    """
    candidates = [(page_no, body_lines(lines)) for page_no, lines in enumerate(pages, 1)]
    for page_no, lines in candidates:
        if title in lines:
            return page_no
    for page_no, lines in candidates:
        if any(line.startswith(title) for line in lines):
            return page_no
    for page_no, lines in candidates:
        if title in ' '.join(lines):
            return page_no
    return None


def resolve(headings: list[tuple[int, str]], pages: list[list[str]]) -> list[tuple[int, str, int | None]]:
    return [(level, title, find_page(title, pages)) for level, title in headings]


def write_outline(src: Path, dst: Path, resolved: list[tuple[int, str, int | None]]) -> int:
    writer = PdfWriter(clone_from=str(src))
    last_page = len(writer.pages) - 1
    parent = None
    added = 0
    for level, title, page_no in resolved:
        if page_no is None:
            continue
        index = min(page_no - 1, last_page)
        if level == 1:
            parent = writer.add_outline_item(title, index)
        else:
            writer.add_outline_item(title, index, parent=parent)
        added += 1
    writer.page_mode = '/UseOutlines'
    with dst.open('wb') as fh:
        writer.write(fh)
    return added


def print_outline(resolved: list[tuple[int, str, int | None]]) -> None:
    level1 = [row for row in resolved if row[0] == 1]
    level2 = [row for row in resolved if row[0] == 2]
    print(f'Bookmark: {len(resolved)} (cấp 1: {len(level1)}, cấp 2: {len(level2)})')
    for level, title, page_no in resolved:
        target = page_no if page_no is not None else 'KHÔNG TÌM THẤY'
        print(f'{"  " * (level - 1)}{"-" if level == 1 else "*"} {title}  -> tr. {target}')
    pages_l1 = [row[2] for row in level1]
    print('Trang đích cấp 1: ' + ','.join(str(p) for p in pages_l1))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Thêm cây bookmark cho PDF sinh bởi Chrome.')
    parser.add_argument('input', help='PDF đầu vào')
    parser.add_argument('-o', '--output', help='PDF đầu ra (bắt buộc, trừ khi chỉ --print)')
    parser.add_argument('--md', help='Markdown nguồn để lấy cấu trúc heading')
    parser.add_argument('--auto', action='store_true', help='Tự dò heading trong PDF')
    parser.add_argument('--print', dest='do_print', action='store_true',
                        help='In danh sách bookmark kèm trang đích')
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    src = Path(args.input)
    if not src.is_file():
        print(f'Không thấy file đầu vào: {src}', file=sys.stderr)
        return 2
    if not args.md and not args.auto:
        print('Cần --md <source.md> hoặc --auto.', file=sys.stderr)
        return 2
    if not args.output and not args.do_print:
        print('Cần -o <out.pdf> (hoặc dùng --print để chỉ xem trước).', file=sys.stderr)
        return 2

    pages = load_pages(src)
    if args.md:
        md_path = Path(args.md)
        if not md_path.is_file():
            print(f'Không thấy file Markdown: {md_path}', file=sys.stderr)
            return 2
        headings = headings_from_markdown(md_path)
    else:
        headings = headings_from_pdf(pages)

    if not headings:
        print('Không tìm được heading nào.', file=sys.stderr)
        return 1

    resolved = resolve(headings, pages)
    missing = [title for _, title, page_no in resolved if page_no is None]

    if args.output:
        dst = Path(args.output)
        if dst.resolve() == src.resolve():
            print('Đầu ra trùng đầu vào — từ chối ghi đè.', file=sys.stderr)
            return 2
        added = write_outline(src, dst, resolved)
        print(f'Đã ghi {dst} — {added} bookmark, {len(pages)} trang, /PageMode /UseOutlines.')

    if args.do_print:
        print_outline(resolved)
    for title in missing:
        print(f'CẢNH BÁO: không tìm thấy trang cho "{title}"', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
