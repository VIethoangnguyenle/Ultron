State sync: ~/Ultron/sync.sh → git@github.com:VIethoangnguyenle/Ultron.git (restore.sh); KHÔNG commit .env/auth.json/state.db.
§
Bot Ultron on VNPay Workspace. Send text thô (link <url|text>). Mention: userMention.user.name → viết <users/<id>>; bot ko displayName → chip '@', đừng chèn space; thread nhiều người chip auto có thể SAI tên → đối chiếu id.
§
Jarvis=claude CLI, Matcha=agy; VIỆC VIẾT CODE mới (script/tool/cổng) ⇒ luôn giao claude, Ultron không tự viết.
§
Guard Hermes: cấm restart gateway từ trong gateway + cấm sửa config.yaml; restart → claude đọc scripts/gw_restart.txt; sửa config: `hermes config set`.
§
Đọc ảnh: vision_analyze (agy dự phòng). Video → skill video-analysis. TTS vi-VN-NamMinhNeural; phát trên máy: ffmpeg→wav→paplay, XDG_RUNTIME_DIR=/run/user/1001 (paplay ko đọc mp3).
§
db-access: write chỉ VBSMEONL+VBSMEOFF (sql_write preview+token), chỉ SIT; mở write DB khác phải qua Hoàng.
§
Sổ hồ sơ: people.json + scripts/people.py (list/show/note/habit) + skill team-people.
§
Chat: gchat_dump.py (đọc lịch sử), gchat_send_file.py --space --file (gửi file THẬT lên chat, không thả path local). URL dài có `_`/`*` phải bọc code block — Chat ăn ký tự.
§
Email: token google_token.json + google_calendar_token.json (chỉ đọc lịch). Hoàng chốt 14/09: chỉ ping mail book họp nội bộ / review tài liệu dự án; mail chỉ trong DM.
§
Manager của Hoàng = chị Nguyên (users/105726904933324385534, Phó phòng P.DVNH).
§
Luật dạy qua KÊNH nào chỉ áp kênh đó (Siri: gọn văn nói, hỏi từng phần mỗi lượt, lọc input méo) — không lẫn sang chat/group.
§
Lịch: schedules.yaml có every_minutes+between — không tạo cron job. `calendar-remind` (2') nhắc họp từ calendar Hoàng: 2 mốc, DM + loa máy; config state/calendar_remind.json.
§
Siri/widget: cổng local :9444 speak + :9445 chat + gateway :9443 (127.0.0.1) sống sau teardown 17h30; chỉ node Tailscale tắt.
§
KHÔNG nhận/lưu mật khẩu, credential Hoàng gửi qua chat; từ chối + đưa cách không cần secret.
§
Bản đồ kênh: DM anh=chủ · DM 1:1 đồng nghiệp=hỗ trợ (phong thái thường, theo hồ sơ người đó) · VBB SME=dự án · DVNH-Daily=nội bộ · chồn ăn dưa=tán gẫu · Agent Space=gặp bot khác. Chi tiết: people.py.