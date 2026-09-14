#!/usr/bin/env python3
"""Verify độc lập: bookmark (outline) + link nội bộ + số trang của PDF. Dùng: python3 pdf_verify.py <pdf>"""
import sys
from pypdf import PdfReader

path = sys.argv[1]
r = PdfReader(path)
print("file:", path)
print("so trang:", len(r.pages))
print("PDF version:", r.pdf_header)
try:
    print("PageMode:", r.trailer["/Root"].get("/PageMode"))
except Exception as e:
    print("PageMode: (loi)", e)

# --- links nội bộ ---
links = []
for i, p in enumerate(r.pages):
    for a in (p.get("/Annots") or []):
        o = a.get_object()
        if str(o.get("/Subtype")) == "/Link":
            dest = o.get("/Dest")
            tgt = None
            if isinstance(dest, str):
                nd = r.named_destinations.get(dest)
                if nd is not None:
                    tgt = r.get_page_number(nd.page) + 1
            links.append((i + 1, tgt))
print("so link noi bo:", len(links), "->", [t for _, t in links])


# --- outline (bookmark) đệ quy ---
def walk(items, level=1):
    n = 0
    for it in items:
        if isinstance(it, list):
            n += walk(it, level + 1)
            continue
        try:
            page = r.get_page_number(it.page) + 1
        except Exception:
            page = "?"
        print("  " * level + f"- [{level}] {it.title}  -> tr.{page}")
        n += 1
    return n


print("--- OUTLINE ---")
try:
    total = walk(r.outline)
except Exception as e:
    total = f"(loi doc outline: {e})"
print("tong bookmark:", total)
