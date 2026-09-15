## Dev xin bản `.md` của tài liệu (đã gặp 15/09/2026)

Luật "ưu tiên PDF" là cho **mặc định**, không phải cấm: khi dev/tester **xin rõ ràng** file `.md`
(để sửa, nhúng wiki), gửi **bản `.md` gốc đã dùng để render** — KHÔNG convert ngược từ PDF (mất bảng,
JSON dài dòng). Vì vậy sau mỗi lần `md2pdf.py`, **giữ nguyên file `.md` nguồn** (đừng xoá/đổi tên),
để lúc bị hỏi là gửi được ngay.

# Gửi báo cáo log vào ĐÚNG thread, dạng PDF (đã kiểm chứng 2026-09-14)

Tester hỏi trong thread nào ⇒ file báo cáo phải nằm trong thread đó, nếu không họ không thấy.

**Định dạng gửi = PDF** (Hoàng chốt 2026-09-14: *"gửi file cho tester… luôn ưu tiên file PDF để mô tả nhé,
kể cả log em cũng để ở trong đó"*). Báo cáo tra log cũng vậy: nội dung theo `templates/log-report.md`
(7 mục), xuất ra `.pdf` rồi mới gửi. `.md` chỉ là bản nháp nội bộ.

## 0. Từ template → PDF

```bash
python3 ~/.hermes/scripts/md2pdf.py /tmp/BAO-CAO.md -o /tmp/BAO-CAO.pdf
# kiểm tra thật: file tồn tại, > 0 byte, mở được
ls -la /tmp/BAO-CAO.pdf && pdfinfo /tmp/BAO-CAO.pdf 2>/dev/null | head -5
```

## 1. Tìm thread_id của tin nhắn tester
`gchat_dump.py` KHÔNG trả thread. Lấy từ state DB:

```bash
cd ~/.hermes
sqlite3 state.db "SELECT DISTINCT s.id, s.chat_id, s.thread_id FROM messages m JOIN sessions s ON s.id=m.session_id WHERE m.content LIKE '%<mã GD>%';"
```
→ dùng `chat_id` (space) + `thread_id` (`spaces/.../threads/...`).

## 2. Gửi file PDF vào thread (1 tin ngắn + file, KHÔNG dán log dài)

```bash
scripts/gchat_send_file.py --space spaces/XXXX --thread spaces/XXXX/threads/YYYY \
  --file /tmp/BAO-CAO.pdf --text "$(cat /tmp/cap.txt)"
```

- Gửi **PDF** (Content-Type `application/pdf`) — Chat hiện thành card tải về bình thường.
  `.md` KHÔNG gửi làm bản chính cho tester (chỉ dùng nội bộ).
- Caption viết ra file rồi `--text "$(cat ...)"` — đừng nhét newline qua f-string/`repr()` (sẽ ra chữ `\n`).
- Kiểm lại bằng `gchat_dump.py --space ...` xem tin đã nằm đúng thread.
- **Tên người gửi:** đường user-OAuth (implicit) ⇒ tin hiện dưới tên **Hoàng**, không phải tên bot.
  Gửi cho người khác thì phải nói rõ việc này cho Hoàng biết.

## 3. Chọn ĐÚNG file log trên portal (bẫy tốn thời gian)
- Danh mục log có thể có ~95 file pod; **xếp theo cột ngày-giờ trên autoindex, KHÔNG sort theo tên**.
- Mốc ngày trên autoindex = mtime file, có thể lệch hẳn ngày trong log; **luôn kiểm mốc thời gian BÊN TRONG file**
  (`head -c 400` + `tail -c 400`) trước khi kết luận là pod đúng.
- Lọc theo mã GD/TRN, rồi in **số dòng** rồi mới in nội dung (`cut -c1-260`) để không tràn output.
- Dòng JSON thuần (không có tiền tố thời gian): lấy mốc từ dòng header gần nhất phía trên
  (`awk -v n=N 'NR>=n-8 && NR<=n'` rồi lọc `\[2026-...\]`).
