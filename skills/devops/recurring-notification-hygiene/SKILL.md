---
name: recurring-notification-hygiene
description: Use when recurring messages make a chat noisy or spammy.
---

# Tin định kỳ của Ultron — tần suất & chống ồn

Áp dụng cho MỌI đường Ultron tự gửi tin lặp: action trong `~/.hermes/schedules.yaml`
(cơ chế sửa lịch: skill `ultron-scheduled-actions`), cron job có `deliver` trỏ vào chat,
script có cờ `--send` (`compact_stats.py`, `token_budget.py`, `*_progress.py`…), webhook route.

## Ba bậc tần suất — mặc định lấy bậc thấp nhất
1. **Transactional, chỉ khi có việc thật** (mặc định nên dùng): cảnh báo vượt ngưỡng, nhắc họp/việc,
action lỗi. Im lặng là bình thường, chỉ lên tiếng khi có chuyện.
2. **Tổng hợp định kỳ: 1 lần/tuần** (kèm `until`) — mặc định cho báo cáo số liệu.
3. **Nhiều lần/ngày: chỉ khi Hoàng yêu cầu rõ**, và phải nói trước sẽ có mấy tin/ngày.

Vì sao: group nhận báo cáo (Home `spaces/AAQAZxc2km8`) cũng là nơi Hoàng trao đổi — báo cáo tự động
chen vào mạch nói chuyện thì bị đọc là tiếng ồn, không phải thông tin. Muốn "tự động mà vẫn yên" thì
đẩy về bậc 1 (chỉ báo khi bất thường) chứ không phải thêm báo cáo.

Mọi báo cáo tự đặt đều phải có hạn: giữ `until` (hoặc `date:` nếu one-shot). Cắt tần suất **trước**,
chỉ xoá action khi nó không còn giá trị — cắt tần suất là chuyện thường, xoá là chuyện cuối.

Yêu cầu kiểu "theo dõi vài hôm rồi báo anh số thật" là **phép đo MỘT LẦN**, không phải lịch cố định:
one-shot hoặc `until` sát ngày, đừng nhân thành N tin/ngày chạy mãi.

Cảnh báo kỹ thuật (token, lỗi hạ tầng) đi đường escalate/DM, KHÔNG đổ vào group thảo luận.

## Khi bị than ồn — rà thật rồi mới sửa
Đừng đoán nguồn theo trí nhớ; đếm và đối chiếu trước (đầy đủ lệnh: `references/message-noise-audit.md`):
1. Đếm tin bot thật đã gửi vào space.
2. Liệt kê mọi nguồn gửi định kỳ nhắm vào space đó: cron job (`jobs.json` → `deliver`) + action
   (`daily_dispatch.py --list`) + script tự gọi.
3. Đối chiếu với `~/.hermes/cron/dispatch.log` (dòng `FIRED <id> -> '<nội dung>'`).
4. Tin có mặt trong space mà **không** có trong log định kỳ ⇒ do chạy TAY (kiểm mtime script / phiên
   vừa rồi) — nhận đúng chỗ đó thay vì đổ lỗi cho lịch.
5. Sửa: hạ tần suất / đổi `deliver`, giữ `until`; rồi báo lại **một tin ngắn**: vì sao nhiều, đã đổi gì,
còn lại những gì chạy tiếp.

## Pitfalls
- **Kiểm chứng script có cờ gửi tin thì chạy bản KHÔNG gửi.** Sau khi vá một script báo cáo, chạy lại
  không `--send` (hoặc `HERMES_HOME` trỏ thư mục tạm) để xem nội dung. Chạy bản thật "cho chắc" là bắn
  thêm một bản y hệt vào group — thường rơi đúng lúc đang trao đổi nên đọc ra như spam.
- **Một bản bị nhân đôi trông y như spam.** Cùng một nội dung có thể tới từ 2 nguồn (lịch + job cron +
  lần chạy tay). Khi thấy 2 tin giống nhau trong group, kiểm cả 3 nguồn trước khi kết luận.
- **Đừng tắt hẳn báo cáo khi bị than.** Người dùng phàn nàn *tần suất*, không phải sự tồn tại của báo
  cáo: hạ xuống bậc thấp hơn và nói rõ cách bật lại (một dòng trong `schedules.yaml`) là đủ.
- **Không tự hứa "chỉ báo khi bất thường" nếu chưa có cờ đó.** Muốn script tự lọc bất thường phải sửa
  code ⇒ giao Jarvis/claude; nói rõ với Hoàng là việc code, đừng nhận rồi để đó.
- **Mọi thay đổi tần suất phải để lại lý do ngay trong file cấu hình** (comment cạnh action): người
  sau (kể cả chính mình) nhìn vào biết vì sao nó thưa, và biết lệnh bật lại.
