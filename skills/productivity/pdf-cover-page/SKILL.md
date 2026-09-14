---
name: pdf-cover-page
description: Use when a PDF/doc needs a designed cover page.
---

# Trang bìa cho tài liệu PDF

## Khi nào dùng
Tài liệu dài (kỹ thuật, báo cáo, hướng dẫn) cần trang bìa có hoạ tiết/ảnh, không chỉ dòng tiêu đề chữ.
Kết quả: 1 file PDF — trang 1 là bìa full-bleed, các trang sau là nội dung + mục lục bấm được.

## Quy trình 6 bước

1. **Xin hoạ tiết từ agy (Matcha)** — agy KHÔNG có model sinh ảnh; nó VẼ **SVG tự chứa** rồi tự raster bằng
   Chrome. Dùng brief mẫu `templates/agy-cover-brief.md` (đổi tiêu đề/màu/kích thước), chạy NỀN bằng
   `terminal(background=true, notify=true)`:
   `agy --add-dir <dir> --model gemini-3.1-pro-high --print-timeout 20m --dangerously-skip-permissions --print 'Đọc kỹ <brief> và làm đúng yêu cầu, tự kiểm chứng trước khi báo xong.'`
   Brief phải yêu cầu: viewBox `1240x1754` (A4 @150dpi), tự chứa (không font/ảnh ngoài), wordmark chừa chỗ,
   **1/3 dưới để trống** cho chữ tiếng Việt, và tự kiểm chứng (xmllint + Chrome screenshot + PIL size/stddev
   + PNG > 60KB).
   ⚠️ **Đừng chạy `nohup ... &` trong `execute_code`** — lệnh bị nuốt, process không sống. Dùng `terminal(background=true)`.
2. **Soi ảnh bằng `vision_analyze`** trước khi dùng: chữ có đè/tràn lề không, 1/3 dưới có trống thật không.
3. **Dựng `cover.html`** theo `templates/cover.html`: `@page{size:A4; margin:0}`, ảnh
   `position:absolute; width:210mm; height:297mm; object-fit:cover`, chữ overlay đặt bằng mm.
4. **Render bìa thành PDF riêng**:
   `/usr/bin/google-chrome --headless --no-sandbox --disable-gpu --no-pdf-header-footer --virtual-time-budget=6000 --print-to-pdf=/tmp/cover.pdf file:///tmp/cover.html`
   → kiểm `pdfinfo | grep Pages` = 1.
5. **Render tài liệu KHÔNG kèm bìa** (bỏ khối bìa trong .md; trang 1 tài liệu = dòng thông tin + Mục lục) rồi GHÉP:
   ```python
   from pypdf import PdfWriter
   w = PdfWriter()
   for f in ['/tmp/cover.pdf','/tmp/doc.pdf']: w.append(f)
   w.write('/tmp/final.pdf')
   ```
6. **Đánh bookmark/outline SAU khi ghép** (chạy trên file đã ghép để số trang bookmark đúng), rồi verify.

## Bẫy (đã trả giá)
- **Nhét bìa vào chính .md ⇒ viền trắng**: `@page{size:A4;margin:18mm 16mm}` của md2pdf làm nội dung tràn ra
  margin bị CẮT, âm margin không bleed được. ⇒ Bìa phải là PDF riêng với `@page{margin:0}` rồi ghép. Không sửa
  `md2pdf.py` cho việc này (đổi @page ảnh hưởng cả tài liệu; padding của body không lặp lại theo từng trang).
- **CSS base của md2pdf ghi đè**: có `img{max-width:100%!important;height:auto!important;margin:10px auto}`
  ⇒ nếu nhét bìa vào .md thì img mất `height:100%`/`object-fit`. Làm bìa riêng thì không dính bẫy này.
- **Số trang mục lục**: bìa = trang 1, dòng thông tin + Mục lục = trang 2, nội dung từ trang 3 — giống hệt khi
  tài liệu còn trang tiêu đề cũ ⇒ **số trang trong mục lục KHÔNG đổi**. Đừng cộng/trừ số trang theo cảm giác:
  lấy số thật từ `scripts/pdf_verify.py` (`so link noi bo: 12 -> [...]`) rồi so với mục lục.
- **Đừng bắt agy validate bằng `xmllint`** — máy không có `libxml2-utils`, agy sẽ báo fail rồi tự chuyển sang
  `xml.etree.ElementTree`. Ghi luôn vào brief: validate bằng Python (`ElementTree`), không cần xmllint.
- **Kiểm full-bleed bằng PIXEL**, đừng chỉ nhìn: raster trang 1 `pdftoppm -f 1 -l 1 -r 50 -png` → 4 điểm ảnh ở
  góc phải là màu tối của nền (không phải 255,255,255). `pdftoppm` đặt tên `-01.png` (2 chữ số) khi tài liệu ≥ 10 trang.
- **Vị trí chữ overlay**: đặt theo mm trong khung 210x297mm; wordmark thường ở ~1/4–1/3 chiều cao, khối nhãn +
  phụ đề nên nằm ~40–48% để trang không bị "nặng đầu", khối thông tin neo đáy ~26mm.

## Kiểm chứng trước khi giao
`pdf_verify.py` (số trang · `tong bookmark` · `so link noi bo` khớp mục lục) · `pdfimages -list` thấy ảnh bìa ở
trang 1 · `vision_analyze` trang bìa (dấu tiếng Việt, không đè wordmark, bố cục cân) · `vision_analyze` trang 2
(mục lục gọn trong 1 trang).

Templates: `templates/cover.html` (khung bìa + vị trí chữ theo mm), `templates/agy-cover-brief.md` (brief giao agy).
