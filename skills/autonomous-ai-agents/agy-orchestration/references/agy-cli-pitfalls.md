# Bẫy khi gọi agy (print mode) — đúc kết thực chiến

## 1. Log rỗng KHÔNG phải bằng chứng thất bại
agy print mode thường **không ghi gì ra stdout** dù chạy thành công → file log 0 byte vẫn có thể là xong. Xác minh bằng **file kết quả + mtime**, không bằng log.

## 2. Kiểm file phải POLL nhiều lần
agy ghi file ở giây cuối trước khi thoát. `ls` ngay lúc process vừa chết = hay báo nhầm "chưa có file". Cách đúng: chờ 20-30s rồi `ls`, lặp 2-3 lần; script canh (watcher) nên `sleep 25` sau khi process thoát rồi mới kiểm.

## 3. Watcher phải canh đúng pid `agy.real`
- `$!` của lệnh nền KHÔNG chắc là agy thật (có thể là pid của `timeout`/subshell).
- Trước khi launch: `pgrep -af agy.real` — nếu còn tiến trình agy cũ thì `head -1` sẽ bắt nhầm pid cũ ⇒ watcher canh sai tiến trình và báo "xong" trong khi job mới còn chạy.
- Sau khi launch: `pgrep -f 'agy.real --model <model>' | head -1` lấy pid THẬT rồi mới gắn watcher.

## 4. Prompt cho `-p`: một dòng, ngắn, và ép thực thi
- Prompt nhiều dòng từng cho kết quả 0 tiến triển; prompt 1 dòng + câu *"THỰC THI bằng shell/python của bạn, KHÔNG trả lời suông, làm tới khi xong"* chạy ổn định.
- Việc dài/nhiều ràng buộc ⇒ **để toàn bộ spec trong file** (vd `/tmp/ua_merge_task.md`) rồi prompt chỉ: `Đọc kỹ <file> rồi THỰC THI toàn bộ yêu cầu trong đó…`.
- Việc lớn phải **chia lô + ghi kết quả dần** (temp rồi rename) để crash không mất tiến độ; mỗi lô ≤ ~250 node.

## 5. Quota là per-MODEL, không phải per-account
1 model cạn quota ⇒ thử model KHÁC trong thang trước, chỉ xoay account (`hagy next`) khi hết cả thang. Kiểm quota event ở `~/.antigravity_sw/logs/rotation.log`.

## 6. Wrapper `~/.local/bin/agy` v1.5 — `--effort` chỉ cho model `*-high`
- `agy.real` tự suy reasoning effort từ model id: chỉ id đuôi `*-high` nhận `--effort high`; truyền cho `-low`/`-medium` sẽ lỗi `invalid model selection … conflicts with --effort=high`.
- v1.5 đã vá: `effort_args_for` gắn `--effort` theo từng model, và tự bỏ `--effort` do caller truyền sai — có log `DROPPED --effort (model X does not accept it)` trong `rotation.log`.
- Thang 7 model: `3.1-pro-high → 3.1-pro-low → 3.8-flash-high → 3.8-flash-medium → 3.7-flash-high → 3.7-flash-medium → 3.6-flash-high`; xoay account chỉ sau khi cả thang chết.

## 7. Verify bản vá wrapper độc lập (không tin self-report)
Chạy lại **đúng ca từng fail qua chính wrapper**: `agy --model gemini-3.1-pro-low --effort high -p 'ok'` phải RC=0; kiểm `bash -n`; đối chiếu `rotation.log`.
