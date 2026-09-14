# Sơ đồ Archify → ảnh cho tài liệu PDF

## Khi nào dùng
Sơ đồ kiến trúc / luồng / tuần tự / vòng đời cần đẹp, cố định như ảnh. Archify = mã nguồn mở (MIT),
bản vendor ở `~/.hermes/vendor/archify`; nhận file JSON (IR) → render HTML + SVG.

## Luôn dùng cầu nối, ĐỪNG tự tách SVG
```bash
hermes-agent/venv/bin/python scripts/archify_svg.py \
  --type <architecture|workflow|sequence|dataflow|lifecycle> \
  --json ir.json --out out.svg --png out.png [--theme light|dark]
```
In ra JSON `{"ok":true,"viewBox":"0 0 W H","png_bytes":N}` → đọc viewBox để biết khổ ảnh.

## Bẫy 1 — SVG của Archify KHÔNG self-contained
CSS nằm trong `<style>` ở `<head>` của HTML (preset "classic" ≈186KB). Tách mỗi `<svg>` ⇒ mọi khối
thành **đen đặc**, chữ mất. Cầu nối đã gấp toàn bộ CSS vào `<svg>`. Dấu hiệu sớm: PNG < 60KB cho sơ đồ
~1000px là nghi mất style (bản đúng ~100–140KB).

## Bẫy 2 — validator layout rất chặt
`node bin/archify.mjs render <type> <ir.json> <out.html>` trả `layout/constraint` kèm gợi ý:
- `Label "X" overlaps component "Y"` + "Suggested fix: labelDy +24" ⇒ đặt `labelDy` cho nhãn đó.
- `Labels "A" and "B" overlap` ⇒ lệch một nhãn ±26px (`labelDx`/`labelDy`).
- `must honor inferred fromSide/toSide` ⇒ ghi rõ `fromSide`/`toSide`. Route hợp lệ: `auto, straight,
  drop, outside-right, return-left, bottom-channel, up-channel`.
- `Sublabel needs ~Npx but node provides Mpx` ⇒ rút ngắn sublabel hoặc tăng `width` (tăng width trong
  workflow dễ sinh `node exceeds horizontal bounds of lane`).
- Hai node cùng lane cách < 28px ⇒ **đổi cột**, đừng nới width.
Cách làm hiệu quả: vòng lặp render → parse lỗi → sửa theo gợi ý → render lại (2–4 vòng là sạch).
Kiểu `architecture` (đặt toạ độ tay) khắt khe nhất; `workflow`/`sequence`/`lifecycle` ổn định hơn ⇒
muốn vẽ "kiến trúc tổng thể" thì mô tả theo LỚP bằng workflow (lanes = lớp) thay vì toạ độ tay.

## Nhúng vào Markdown → PDF
- Trong .md: `![Mô tả](file:///home/zane/.hermes/docs/diagrams/<ten>.png)` + 1 dòng caption in nghiêng.
- CSS phải có `img{max-width:100%!important;height:auto!important}` (xem `docs/pdf-extra.css`).
- Kiểm chứng ảnh đã vào PDF: `pdfimages -list out.pdf` → đúng số ảnh + đúng trang.

## Kiểm chứng trước khi giao
- `vision_analyze` từng PNG (chữ đè/cắt? style đúng?) — bước này bắt được bản mất CSS.
- Thêm ảnh xong phải đo LẠI số trang mục lục (`scripts/toc_pages.py`) rồi render lại.
