# Pitfalls khi render PDF (md2pdf.py + Chrome headless)

Bổ sung cho SKILL.md — các lỗi đã gặp thật khi dựng tài liệu nhiều trang.

## 1. Sơ đồ mermaid quá khổ ⇒ trang trắng / nhảy trang

**Triệu chứng:** `flowchart TB` với nhãn dài (mỗi node 10–15 từ) → SVG cao hơn 1 trang A4 →
trang chứa tiêu đề "…Sơ đồ…" bị để trắng gần hết, sơ đồ bị đẩy sang trang sau, có khi sinh thêm
trang gần trắng.

**Cách sửa:**
- Nhãn node **ngắn** (2–5 từ + 1 dòng phụ `<br/>`), chi tiết đưa xuống **bảng** ngay dưới sơ đồ.
- Với ≤5 node: dùng `flowchart LR` (nằm ngang) — cao thấp, luôn vừa trang.
- CSS phụ (truyền `--css`): `.mermaid svg { max-width:100% !important; height:auto !important; }`
- **KHÔNG** đặt `page-break-inside: avoid` cho `.mermaid` (hay `table`): nó dồn cả khối sang trang sau
  → để lại khoảng trắng lớn. Việc render đã tự tránh cắt giữa khối.

## 2. Chrome in header/footer `file:///tmp/....html` + ngày giờ

Đã thêm `--no-pdf-header-footer` vào `md2pdf.py` (14/09/2026). Nếu sửa lại lệnh Chrome, giữ cờ này.

## 3. `nl2br` ⇒ không tự ngắt dòng trong Markdown

Mỗi đoạn văn / mỗi gạch đầu dòng phải viết trên **một dòng**; xuống dòng tay sẽ thành `<br>` cứng
giữa câu.

## 4. Quy trình QA bắt buộc trước khi gửi

```bash
P=out.pdf
pdfinfo $P | grep -E "^Pages|Page size"                 # số trang, khổ A4
pdftotext $P - | grep -cE "flowchart|Syntax error|file:///tmp"   # phải = 0
# mục lục: dò trang thật của từng heading
for p in $(seq 1 $(pdfinfo $P | awk '/^Pages/{print $2}')); do
  pdftotext -f $p -l $p $P - | grep -qE "^2\. " && echo "trang $p: muc 2"
done
# phát hiện trang trắng: render 60dpi rồi soi dung lượng
pdftoppm -png -r 60 $P /tmp/chk && for f in /tmp/chk*.png; do
  [ $(stat -c%s $f) -lt 15000 ] && echo "NGHI TRANG TRANG: $f"; done
```

**Số trang trong Mục lục phải tính lại SAU khi chốt layout** — mọi thay đổi sơ đồ/độ dài đều làm
dịch trang. Quy trình: render → dò heading → cập nhật mục lục → render lại → kiểm gate lần cuối.

## 5. Mục lục BẤM ĐƯỢC (link nội bộ trong PDF)

Yêu cầu thực tế: "Mục lục phải route tới trang đó luôn" — ghi số trang là **chưa đủ**, phải click được.

- md2pdf bật `fenced_code,tables,sane_lists,nl2br` — **không** có `toc`/`attr_list` ⇒ cú pháp
  `## Tiêu đề {#id}` KHÔNG tạo được anchor. Cách chạy được: viết tiêu đề bằng raw HTML
  `<h2 id="m2">2. Các lớp kỹ thuật</h2>` (cách 1 dòng trống trên/dưới), mục lục thì
  `2. [Các lớp kỹ thuật](#m2) — tr. 2`.
- Chrome headless sinh `/Subtype /Link` + **named destination** (`/m2`) ⇒ bấm trong trình đọc PDF
  nhảy đúng trang. Chèn `<h2 id=...>` gần như không đổi phân trang (vẫn kiểm lại số trang sau render).
- **Verify bằng pypdf, KHÔNG bằng pdftohtml** (pdftohtml không xuất link nội bộ ⇒ dễ kết luận sai "0 link"):

```bash
grep -a -c "/Subtype */Link" out.pdf        # phải = số mục trong mục lục
uv venv /tmp/pdfvenv --python 3.11 && uv pip install --python /tmp/pdfvenv/bin/python pypdf
/tmp/pdfvenv/bin/python /tmp/pdf_links.py out.pdf    # in trang đích của từng link
```

- Pitfall khi tự viết script đọc link: `/Dest` là **NameObject** (`'/m2'`) — NameObject là `str` con,
  phải kiểm tra `isinstance(dest, str)` TRƯỚC nhánh array, nếu không `dest[0]` = `'/'` ⇒ phân giải None.
- Chrome v114 **không** sinh bookmark/outline (pypdf báo `outline: 0`) ⇒ thêm bằng tool hậu xử lý
  `~/.hermes/scripts/pdf_add_outline.py <in.pdf> -o <out.pdf> --md <source.md>` (dựng outline 2 cấp từ
  heading Markdown, tự dò trang, đặt `/PageMode /UseOutlines`). Verify: pypdf đọc `reader.outline` +
  `/PageMode` trong catalog, và `pdftotext` 2 file rồi `diff` phải = 0.
