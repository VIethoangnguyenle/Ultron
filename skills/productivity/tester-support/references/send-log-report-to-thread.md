# Gửi báo cáo log vào ĐÚNG thread (đã kiểm chứng 2026-09-14)

Tester hỏi trong thread nào ⇒ file báo cáo phải nằm trong thread đó, nếu không họ không thấy.

## 1. Tìm thread_id của tin nhắn tester
`gchat_dump.py` KHÔNG trả thread. Lấy từ state DB:

```bash
cd ~/.hermes
sqlite3 state.db "SELECT DISTINCT s.id, s.chat_id, s.thread_id FROM messages m JOIN sessions s ON s.id=m.session_id WHERE m.content LIKE '%<mã GD>%';"
```
→ dùng `chat_id` (space) + `thread_id` (`spaces/.../threads/...`).

## 2. Gửi file vào thread (1 tin ngắn + file, KHÔNG dán log dài)

```bash
scripts/gchat_send_file.py --space spaces/XXXX --thread spaces/XXXX/threads/YYYY \
  --file /tmp/BAO-CAO.md --text "<users/ID_tester> ... 1 câu kết luận ..."
```

- File `.md` gửi được (`contentType: text/markdown`), Chat hiện thành card tải về bình thường.
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
