# Bẫy khi gọi agy (print mode) — đúc kết thực chiến

## 1. Log rỗng KHÔNG phải bằng chứng thất bại
agy print mode thường **không ghi gì ra stdout** dù chạy thành công → file log 0 byte vẫn có thể là xong. Xác minh bằng **file kết quả + mtime**, không bằng log.

## 2. Kiểm file phải POLL nhiều lần
agy ghi file ở giây cuối trước khi thoát. `ls` ngay lúc process vừa chết = hay báo nhầm "chưa có file". Cách đúng: chờ 20-30s rồi `ls`, lặp 2-3 lần; script canh (watcher) nên `sleep 25` sau khi process thoát rồi mới kiểm.

## 3. Watcher phải canh đúng tiến trình cha — đừng canh `agy.real`
- `$!` của lệnh nền KHÔNG chắc là agy thật (có thể là pid của `timeout`/subshell).
- **ĐỪNG canh `pgrep -f 'agy.real --model …' | sort -n | tail -1`**: `agy.real` **fork tiến trình con cùng cmdline**, nên pid mới nhất thường là con ngắn hạn → watcher thoát sau ~1 phút và báo "xong" giả (đã xảy ra 3 lần).
- Cách đúng: canh **pid của lệnh `timeout <giây> agy …`** (`pgrep -f 'timeout 5400 agy'`) — nó sống đúng bằng vòng đời job; hoặc canh bằng **vòng poll file tiến độ** (file ngừng đổi + không còn tiến trình agy nào).
- Trước khi launch vẫn phải `pgrep -af agy.real` để chắc không còn job agy cũ chạy chồng.

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

## 8. Giao agy "viết lại mô tả" → nó hay lách bằng CÂU KHUÔN SÁO
Khi được giao viết mô tả tiếng Việt cho node, agy có thể **dịch máy móc bằng regex** và sinh câu sáo rỗng kiểu
*"Thực thi phương thức X trong lớp Y. Phương thức này đảm nhiệm logic xử lý tương ứng, phục vụ tiến trình nghiệp vụ của hệ thống."*
⇒ số "node còn tiếng Anh" về 0 nhưng chất lượng bằng không.
Prompt phải: (1) **liệt kê CẤM** đúng các khuôn sáo đó, (2) bắt **đọc file source thật** rồi mô tả cụ thể, (3) đặt **≥ N ký tự**, (4) bắt agy **tự đếm lại số node còn khuôn sáo = 0**.
Verify độc lập: đếm số node chứa chuỗi khuôn sáo (không chỉ đếm "còn tiếng Anh"), và kiểm mẫu ở các node đã viết tốt trước đó xem có bị ghi đè không.
Rollback nhanh: trước mỗi lượt bắt agy backup `.bakN-<ts>` để khôi phục bản sạch nếu chất lượng kém.

## 9. Verify bản vá wrapper độc lập (không tin self-report)
Chạy lại **đúng ca từng fail qua chính wrapper**: `agy --model gemini-3.1-pro-low --effort high -p 'ok'` phải RC=0; kiểm `bash -n`; đối chiếu `rotation.log`.
