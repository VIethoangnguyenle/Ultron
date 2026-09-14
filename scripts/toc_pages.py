#!/usr/bin/env python3
"""Do trang bat dau tung muc trong PDF, doi chieu voi tieu de trong muc luc cua file markdown."""
import re, subprocess, sys

def measure(md_path, pdf_path):
    md = open(md_path, encoding="utf-8").read()
    toc = re.findall(r"^(\d+)\.\s+\[(.+?)\]\(#m\1\)", md, re.M)
    txt = subprocess.run(["pdftotext", pdf_path, "-"], capture_output=True, text=True).stdout
    pgs = txt.split("\f")
    rows = []
    for num, title in toc:
        target = f"{num}. {title}"
        page = None
        for i, body in enumerate(pgs, start=1):
            if any(ln.strip() == target for ln in body.splitlines()):
                page = i
                break
        rows.append((int(num), title, page))
    return rows, len([p for p in pgs if p.strip()])

if __name__ == "__main__":
    rows, npages = measure(sys.argv[1], sys.argv[2])
    print(f"TONG TRANG (co chu): {npages}")
    for num, title, page in rows:
        print(f"{num}\t{title}\ttr. {page}")
    miss = [t for _, t, p in rows if p is None]
    print("KHONG TIM THAY:", miss)
