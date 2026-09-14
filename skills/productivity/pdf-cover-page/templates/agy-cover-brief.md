# Việc: thiết kế HOẠ TIẾT BÌA cho tài liệu kỹ thuật (SVG tự chứa)

Xuất ra: `<DIR>/cover-bg.svg` (tự tạo thư mục).

## Sản phẩm
Khung hoạ tiết KHỔ DỌC A4 làm NỀN cho trang bìa. Phần chữ tiếng Việt do tài liệu tự đè lên
⇒ **chừa khoảng trống thoáng ở 1/3 dưới**.

## Yêu cầu kỹ thuật (bắt buộc)
- SVG **tự chứa**: KHÔNG ảnh ngoài, KHÔNG font ngoài, KHÔNG `<script>`, KHÔNG `<foreignObject>`.
  Chỉ `<rect> <circle> <path> <line> <polyline> <text> <defs>` + gradient.
- `width="1240" height="1754" viewBox="0 0 1240 1754"` (A4 dọc @150dpi), có `xmlns`.
- Nền gradient tối sang trọng (`#070B14` → `#0E1A2F`), điểm nhấn xanh ngọc `#22D3EE` / lam `#38BDF8`,
  opacity 0.06–0.35, KHÔNG quá 4 màu.
- Nửa trên: hoạ tiết hình học kiểu lưới kết nối / node network — tinh tế, vài node phát sáng, đường mảnh.
- **Wordmark** (tên tài liệu/sản phẩm) cỡ lớn ~150–190px, in hoa, letter-spacing rộng ~0.18em, màu `#F8FAFC`,
  đặt khoảng 1/3 từ trên xuống. Nếu wordmark có dấu tiếng Việt thì kiểm kỹ glyph.
- Dưới wordmark: đường kẻ mảnh phát sáng + khoảng trống (KHÔNG chữ) để tài liệu đè phụ đề.
- Đáy: dải gradient mảnh + khoảng trống cho dòng phiên bản/người phụ trách.
- Tối giản cao cấp, nhiều khoảng thở. KHÔNG clipart, KHÔNG emoji, KHÔNG ảnh chụp, KHÔNG logo bên thứ ba.
- Mọi phần tử nằm gọn trong viewBox; không chữ nào đè lên nhau; KHÔNG thông tin nội bộ/dự án nhạy cảm.

## Tự kiểm chứng TRƯỚC khi báo xong (bắt buộc)
1. Validate XML bằng Python (máy KHÔNG có `xmllint`):
   `python3 -c "import xml.etree.ElementTree as ET; ET.parse('<DIR>/cover-bg.svg'); print('well-formed')"`
2. Render PNG:
   `google-chrome --headless --disable-gpu --hide-scrollbars --window-size=1240,1754 --screenshot=<DIR>/cover-bg.png <DIR>/cover-bg.svg`
   (tuỳ Chrome: có thể cần `file://` + đường dẫn tuyệt đối).
3. Python: `PIL.Image.open(png).size == (1240,1754)`, stddev điểm ảnh > 10 (không trắng/đen trơn), PNG > 60KB.
4. Nếu bước 2/3 fail → sửa và chạy lại; ĐỪNG báo xong khi chưa có PNG hợp lệ.

## Báo cáo khi xong
Đường dẫn SVG + PNG, kích thước PNG, số byte, output bước kiểm chứng 3.
