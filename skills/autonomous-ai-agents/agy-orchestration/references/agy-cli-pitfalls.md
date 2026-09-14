# Bẫy khi gọi agy (CLI, print mode) — đúc kết thực chiến

## 1. Log rỗng KHÔNG phải bằng chứng thất bại
agy print mode (`-p`) thường **không ghi gì ra stdout** kể cả khi chạy thành công → file log 0 byte + exit 0 vẫn có thể là **đã làm xong**.
→ Xác minh bằng **file/kết quả thật** (mtime, kích thước, nội dung đích), KHÔNG kết luận từ log. Đã từng báo sai với Hoàng vì tin log rỗng (merge thật ra xong, file ghi lúc 20:29 trong khi log 0 byte).

## 2. Prompt: 1 dòng + câu "thực thi"
Prompt nhiều dòng: 1 lần chạy 10 phút không tiến triển (nghi bị cắt ở dòng đầu, chưa khẳng định 100%).
Prompt 1 dòng + "Đọc kỹ <file task> rồi **THỰC THI** bằng shell/python, KHÔNG trả lời suông, làm tới khi xong" → xong trong ~2 phút.
→ Luôn: task dài để trong file (`/tmp/<task>.md`), prompt ngắn 1 dòng.

## 3. Watcher phải canh đúng PID của `agy.real`
Nếu launch `nohup timeout N agy ... &` thì `$!` là PID của `timeout`/subshell — nó có thể thoát TRƯỚC khi agy xong (gặp thật: watcher báo xong lúc 20:28, agy còn ghi file tới 20:29).
→ Lấy PID thật: `pgrep -f 'agy.real --model'`, rồi `while ps -p <pid>; do sleep 45; done`.

## 4. Kiểm trước khi launch: có tiến trình agy nào đang chạy không
`pgrep -af agy.real` — hai agy cùng ghi một thư mục `.ua/` là race condition (đã gặp). Có rồi thì đừng launch thêm; xong việc thì `kill <pid>` dọn sạch.

## 5. Quota là per-MODEL, không phải per-account
`~/.antigravity_sw/logs/rotation.log` ghi `QUOTA HIT on <account>` rồi `ROTATED → ...`; `hagy who` xem account hiện tại.
Luật Hoàng chốt 2026-09-14: hết quota 1 model ⇒ thử model Gemini khác trước, chỉ `hagy next` khi cả thang hết. Wrapper v1.3 hiện nhảy account ngay (đang cho Jarvis sửa).

## 6. Lệnh chạy nền chuẩn
`cd <repo> && nohup timeout 7000 agy --model gemini-3.1-pro-high --effort high --print-timeout 120m --dangerously-skip-permissions -p '<prompt 1 dòng>' > /tmp/<name>.log 2>&1 &`

## 7. Verify kết quả graph sau khi agy "xong"
Tự đếm lại bằng Python: số node/edge, id unique, **orphan edge = 0**, prefix filePath theo từng repo con, layers/domains/tour, và sample 2-3 mô tả xem có phải "Auto-generated node for ..." không. Số liệu merge chuẩn (2026-09-14): omni 10.631 + ekyc 1.803 + dvnh-common 2.776 = **15.210 node / 31.356 cạnh, orphan 0, 35 layer, tour 27 bước**.
