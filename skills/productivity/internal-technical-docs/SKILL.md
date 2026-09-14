---
name: internal-technical-docs
description: "Use when viết tài liệu kỹ thuật nội bộ cho Hoàng duyệt."
version: 1.1.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [documentation, technical-doc, pdf, approval-flow, delivery]
    related_skills: [markdown-mermaid-pdf, tester-support, pdf]
---

# Tài liệu kỹ thuật nội bộ — viết, duyệt, giao

Class of work: viết một tài liệu dài (tài liệu kỹ thuật hệ thống, kiến trúc, quy trình, hướng dẫn)
để Hoàng duyệt rồi gửi team. Khác hẳn trả lời tester trong chat: đây là artifact nhiều trang, có
phiên bản, có chuỗi duyệt.

## Thứ tự bắt buộc (đừng nhảy bước)

1. **Đề mục trước** — gửi outline vài dòng (số mục + 1 dòng nội dung mỗi mục) để Hoàng duyệt HƯỚNG ĐI
   trước khi viết. Sai định vị mà viết hết thì phải viết lại từ đầu.
2. **Chốt định vị đúng loại tài liệu.** Hoàng phân biệt rõ: *bản giới thiệu* vs **tài liệu kỹ thuật**.
   Khi được yêu cầu "tài liệu kỹ thuật" ⇒ phải có: phân lớp kỹ thuật, tên + phiên bản thành phần,
   bảng vai trò từng lớp, sơ đồ, phạm vi dữ liệu, nguyên tắc an toàn, quy trình xử lý, giới hạn.
   Không viết kiểu "em là trợ lý ảo, em có thể giúp...".
3. **Viết bản đầy đủ** (Markdown, nguồn ở `~/.hermes/docs/<ten-tai-lieu>.md`) → render PDF.
4. **Gửi riêng DM cho Hoàng duyệt TRƯỚC**: `scripts/gchat_send_file.py --space <dm> --file out.pdf --text "..."`.
   Chỉ sau khi Hoàng OK mới gửi team. Không tự gửi team khi chưa có xác nhận.
5. **Bản sửa thì tăng phiên bản** trong tên tệp (`<Tên>-v1.1.pdf`) và nói rõ trong caption đã đổi gì.

## Số liệu trong tài liệu phải lấy từ MÁY, không đoán

Người đọc tài liệu này (Hoàng, dev) sẽ kiểm chứng. Trước khi viết tên/phiên bản/giấy phép thành phần,
chạy lệnh đọc thật:

```bash
hermes --version                                          # lõi agent
python3 -c "import importlib.metadata as m; print(m.version('<pkg>'))"
node --version; python3 -V; sqlite3 --version
<tool> --version                                          # Chrome, ffmpeg, ...
python3 -c "import json;d=json.load(open('<plugin>/package.json'));print(d['name'],d['version'],d.get('license'),d.get('repository'))"
```

Chỉ ghi giấy phép khi đọc được từ metadata (vd `package.json.license`); không suy đoán. Ghi kèm mốc
thời gian cho bảng phiên bản ("số liệu tại <ngày>") vì phiên bản sẽ lệch về sau.

## Nội dung an toàn (tài liệu gửi team)

- Mô tả môi trường ở mức NGHIỆP VỤ (SIT/UAT/LIVE, log, DB test, Jira/Confluence) — KHÔNG IP, hostname,
  token, đường dẫn nội bộ, tên file/class/hàm.
- Nói rõ phần nào chạy cục bộ, phần nào gọi dịch vụ ngoài (vd hiểu ngôn ngữ do mô hình LLM qua API).
- Không dùng ảnh chụp màn hình thật nếu ảnh chứa dữ liệu giao dịch/khách hàng — vẽ lại bằng sơ đồ.
- Mục "Phạm vi truy cập dữ liệu" và "Nguyên tắc an toàn" giữ lại trong bản gửi team (mặc định CÓ).

## Giao tài liệu (Chat)

- Chat chỉ 1 tin NGẮN: kết luận + tên tệp đã gửi; tóm tắt cấu trúc bằng 1 code block ngắn; KHÔNG dán
  log dài, không dán cả bảng lớn vào chat.
- Gửi tệp THẬT (attachment) bằng `scripts/gchat_send_file.py`, KHÔNG thả đường dẫn local.
- Tệp gửi qua user OAuth hiện dưới tên Hoàng trong DM — bình thường, nói rõ "file em gửi kèm ở trên".
- Xác nhận đã lên chat bằng `scripts/gchat_dump.py --space <space> --limit 3`, đừng tin mỗi exit code.

## QA bản render (bắt buộc trước khi gửi)

```bash
pdfinfo out.pdf | grep -E "^Pages|Page size"        # >= 1 trang, A4
pdftotext out.pdf - | grep -cE "flowchart|Syntax error|file:///tmp"   # phải = 0
pdftoppm -png -r 60 out.pdf /tmp/chk && for f in /tmp/chk*.png; do
  [ $(stat -c%s "$f") -lt 15000 ] && echo "NGHI TRANG TRANG: $f"; done
```

- Sơ đồ mermaid nhãn dài ⇒ SVG cao hơn 1 trang ⇒ tiêu đề để trắng gần hết, sơ đồ nhảy trang sau.
  Chữa: nhãn ngắn (2–5 từ), ≤5 node dùng `flowchart LR`, chi tiết đưa xuống bảng, `--css` với
  `.mermaid svg{max-width:100%!important;height:auto!important}`; KHÔNG dùng `page-break-inside: avoid`
  cho `.mermaid`/`table`.
- **Mục lục phải BẤM ĐƯỢC, không chỉ ghi số trang** (Hoàng 2026-09-14: "Mục lục phải route tới trang
  đó luôn"). Tiêu đề mục viết bằng raw HTML `<h2 id="m2">2. …</h2>` (cách 1 dòng trống trên/dưới),
  mục lục dùng link `2. [Tên mục](#m2) — tr. N`. `md2pdf.py` KHÔNG bật extension `toc`/`attr_list`
  ⇒ cú pháp `## Tiêu đề {#id}` vô hiệu, đừng thử.
  Quy trình số trang: render → dò trang từng mục → điền số → render LẠI → kiểm gate (mọi thay đổi sơ
  đồ/độ dài đều dịch trang; chèn `<h2 id=…>` thì gần như không dịch).
- **Verify link nội bộ bằng pypdf, KHÔNG bằng pdftohtml** (pdftohtml không xuất link nội bộ ⇒ báo sai
  "0 link" rồi mất công đi tìm cách khác):

```bash
grep -a -c "/Subtype */Link" out.pdf      # phải = số mục trong mục lục
uv venv /tmp/pdfvenv --python 3.11 && uv pip install --python /tmp/pdfvenv/bin/python pypdf
/tmp/pdfvenv/bin/python -c "import sys;from pypdf import PdfReader as R;r=R(sys.argv[1]);print([[r.get_page_number(d.page) if hasattr(d,'page') else None for d in [r.named_destinations[k] for k in r.named_destinations]]][0]);print(sum(len([1 for a in (p.get('/Annots') or []) if str(a.get_object().get('/Subtype'))=='/Link']) for p in r.pages))" out.pdf
```

  Kết quả đúng phải khớp từng dòng mục lục (vd 12 link → tr. 1,2,4,5,6,6,7,7,8,10,10,11).
- **Cây bookmark (outline)**: Chrome KHÔNG sinh sẵn ⇒ thêm bằng tool `~/.hermes/scripts/pdf_add_outline.py
  <in.pdf> -o <out.pdf> --md <source.md>` (pypdf; dựng outline 2 cấp: cấp 1 = `<h2 id=...>N. …</h2>`,
  cấp 2 = `### N.M …`, tự dò số trang, đặt `/PageMode /UseOutlines` để khung bookmark tự bung).
  Verify độc lập: pypdf đọc lại `reader.outline` (đếm + trang đích từng mục khớp mục lục) và so `pdftotext`
  2 file ⇒ `diff` phải = 0.
  Pitfall: (a) mục lục nằm CHUNG trang 1 với mục 1 ⇒ lọc theo DÒNG (dòng mục lục có đuôi `— tr. N`),
  đừng bỏ cả trang không thì mục 1 mất trang đích; (b) `--auto` bắt nhầm danh sách 6 bước trong mục 9
  ⇒ phải ràng buộc số hiệu tăng đơn điệu; (c) pypdf ghi lại file ⇒ header PDF 1.4 → 1.3 và size tăng ~4%
  (vô hại, nhưng báo trước cho Hoàng để không hoảng).
- Pipeline render + pitfalls đầy đủ: skill `markdown-mermaid-pdf` và
  `references/pdf-render-pitfalls.md` của skill đó (mục 5 = mục lục bấm được).

## Cấu trúc chuẩn (đã được Hoàng duyệt — tài liệu Ultron v1.2)

Bản mẫu dùng lại: `templates/tai-lieu-ky-thuat.md` (copy ra `~/.hermes/docs/<ten-tai-lieu>.md` rồi điền).

12 mục: 1 Tổng quan · 2 **Các lớp kỹ thuật & thành phần** (sơ đồ lớp + bảng vai trò từng lớp + bảng
thành phần mã nguồn mở kèm phiên bản + bảng nội bộ/nền tảng ngoài + điểm vận hành) · 3 Năng lực chức
năng (Tester | Dev-BA | dùng chung) · 4 Cách sử dụng · 5 Định dạng kết quả trả về · 6 Phạm vi truy cập
dữ liệu · 7 Nguyên tắc an toàn & bảo mật · 8 Vận hành & tự động hoá · 9 Quy trình xử lý một yêu cầu
(sơ đồ 6 bước + bảng giải thích) · 10 Giới hạn & hướng phát triển · 11 Phụ lục A câu lệnh mẫu ·
12 Phụ lục B mã lỗi thường gặp.

Bảng đầu tài liệu: Phiên bản · Ngày · Người phụ trách · Đối tượng đọc · Kênh hoạt động.
Mục 2 là chỗ dễ bị đánh giá "nói chung chung" nhất ⇒ BẮT BUỘC nêu tên thành phần + phiên bản thật,
và ghi rõ "số liệu ghi nhận tại <ngày>".

## Pitfalls

1. **Đừng chờ trả lời hết câu hỏi chốt mới viết.** Hoàng nói "cho anh pdf trước" ⇒ chọn phương án
   mặc định hợp lý, viết luôn, và ghi rõ trong caption "em chốt tạm N điểm, anh muốn khác thì em sửa".
   Hỏi xong ngồi chờ = mất lượt.
2. **Bảng thành phần phải phân loại rõ**: mã nguồn mở (kèm phiên bản/giấy phép) | nội bộ tự phát triển |
   nền tảng bên ngoài. Trộn lẫn ba loại là thứ khiến tài liệu bị coi là "nói chung chung".
3. **Mỗi lần sửa bố cục phải render lại từ đầu và soát lại mục lục** — sửa `.md` xong gửi luôn bản
   PDF cũ là lỗi đã từng suýt xảy ra.
4. **Tài liệu là tài sản dài hạn**: giữ `.md` nguồn trong `~/.hermes/docs/`, không xoá bản cũ khi
   Hoàng còn đang so sánh các phiên bản.
5. **Đừng kết luận "PDF không có link" từ pdftohtml** — công cụ đó im lặng với link nội bộ. Đếm
   `/Subtype /Link` trong file thô, hoặc đọc bằng pypdf (named destination dạng `/m2`).
6. **Khi đọc link bằng pypdf**: `/Dest` trả về NameObject (`'/m2'`) — nó là `str` con nên phải kiểm tra
   `isinstance(dest, str)` TRƯỚC nhánh array, nếu không `dest[0]` = `'/'` ⇒ phân giải ra None (đã mất
   thời gian vì lỗi này).
