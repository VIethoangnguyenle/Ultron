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

## Pitfalls — 9 bẫy đã gặp thật (gộp 2026-09-12, cập nhật 2026-09-15)

1. **mmdc / `npx @mermaid-js/mermaid-cli` KHÔNG chạy được trên box này** — bundle puppeteer-core 25.x
   không launch nổi system Chrome 114 → treo ~30s rồi TimeoutError. Đừng dùng mmdc.
2. **mermaid.js từ CDN ⇒ PDF RỖNG ~660 byte mà exit code vẫn 0** (Chrome treo ở bước tải CDN).
   `md2pdf.py` nhúng `assets/mermaid.min.js` LOCAL ⇒ luôn kiểm size/pages, đừng tin exit code.
3. **`file://` phải là đường dẫn TUYỆT ĐỐI** — `file://relative` bị parse thành host ⇒ trang trắng,
   PDF 660 byte (chỉ gặp khi tự dựng pipeline ngoài `md2pdf.py`).
4. **Mermaid v11 "Syntax error in text"** khi message sequenceDiagram chứa `;` (hiểu là phân tách câu
   lệnh) hoặc lồng nhiều `:` → đổi `;` thành `+`/dấu phẩy, `A->>B: nhãn: giá trị` → `A->>B: nhãn (giá trị)`.
5. **Chrome tự in header/footer `file:///tmp/....html` + `9/14/26, 11:26 AM` ở mọi trang** — trông như rác
   khi gửi khách/team. Đã thêm cờ `--no-pdf-header-footer` vào `md2pdf.py` (2026-09-14). Kiểm chứng:
   `pdftotext out.pdf - | grep -c "file:///tmp"` phải = 0.
6. **`nl2br` bật ⇒ đừng tự ngắt dòng trong Markdown**: xuống dòng giữa câu bị render thành `<br>`
   (gãy dòng giữa đoạn/bullet). Viết mỗi đoạn và mỗi bullet trên MỘT dòng, để trình duyệt tự wrap.
7. **Mục lục phải ghi số trang VÀ bấm được**: render 1 lần → dò trang từng mục bằng
   `for p in $(seq 1 N); do pdftotext -f $p -l $p out.pdf - | grep -q "^<số>. <tên mục>" && echo $p; done`
   → điền số trang vào mục lục rồi render lại. Để bấm được: tiêu đề mục viết bằng raw HTML
   `<h2 id="m2">2. …</h2>` + mục lục dùng `[Tên mục](#m2)` (`md2pdf.py` không bật `toc`/`attr_list`
   nên `## Tên {#id}` vô hiệu). Chi tiết + cách verify (pypdf, KHÔNG pdftohtml):
   `references/pdf-render-pitfalls.md` mục 5.

8. **Cần sơ đồ kiến trúc đẹp (không phải luồng mermaid đơn giản) ⇒ dùng Archify** qua cầu nối
   `scripts/archify_svg.py` (render JSON IR → SVG + PNG), rồi nhúng `![...](file:///...png)` vào .md.
   Bẫy lớn nhất: **SVG của Archify không self-contained** (CSS ở `<head>` của HTML ⇒ tách SVG ra là
   thành khối đen) và **validator layout rất chặt** (phải sửa theo gợi ý `labelDy`/`fromSide`/cột rồi
   render lại 2–4 vòng). Recipe đầy đủ + lệnh kiểm chứng: `references/archify-diagrams.md`.

9. **Diagram cao hơn 1 trang ⇒ sinh TRANG TRẮNG giữa tài liệu** (đã gặp thật 2026-09-15 với
   sequenceDiagram 5 lifeline + 3 note): text extract của trang trắng ~1 ký tự, exit code vẫn 0.
   Fix bằng CSS ép mỗi diagram nằm gọn 1 trang và tự sang trang:
   `pre.mermaid { page-break-inside: avoid; page-break-after: always; }` +
   `pre.mermaid svg { max-width:100% !important; max-height:230mm !important; height:auto !important; }`
   → `md2pdf.py in.md -o out.pdf --css "$(cat /tmp/mermaid-fit.css)"`. Verify bằng đếm ký tự từng trang
   (`for p in $(seq 1 N); do echo page$p $(pdftotext -f $p -l $p out.pdf - | tr -d ' \f\n' | wc -c); done`),
   KHÔNG chỉ nhìn tổng số trang.

Chi tiết + số đo: agentmemory lesson (context=`markdown-mermaid-pdf`) — gọi `memory_lesson_recall`
query `markdown-mermaid-pdf`.

## Recover if mermaid.min.js goes missing

```bash
cp ~/.local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js \
   ~/.hermes/scripts/assets/mermaid.min.js
```

## Verify the render

`pdftotext out.pdf -` (or `pdf_read.py` from the pdf skill) and check the diagram text — if it
shows participant names + messages (not the raw `sequenceDiagram`/`->>` source), mermaid
rendered. For visual QA export a PNG (`pdftoppm -png -r 100 out.pdf page`) and inspect.

Cổng chặn bắt buộc sau mỗi lần build:

```bash
pdfinfo out.pdf | grep Pages                                    # >= 1
pdftotext out.pdf - | grep -c "sequenceDiagram\|Syntax error"   # phải = 0
```
