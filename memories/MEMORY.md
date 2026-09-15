Sync state: ~/Ultron/sync.sh ⇄ github VIethoangnguyenle/Ultron (restore.sh); KHÔNG commit .env/auth.json/state.db.
§
Bot Ultron (VNPay Workspace). Text thô, link <url|text>. Mention: <users/<id>>; bot ko displayName → chip '@' đừng chèn space; thread nhiều người chip có thể SAI tên → đối chiếu id.
§
Jarvis=claude CLI, Matcha=agy; VIỆC VIẾT CODE mới (script/tool/cổng) ⇒ luôn giao claude, Ultron không tự viết.
§
Guard: cấm restart gateway từ trong gateway + cấm sửa config.yaml; restart → claude đọc scripts/gw_restart.txt; sửa config: `hermes config set`.
§
Đọc ảnh: vision_analyze; video → skill video-analysis. TTS vi-VN-NamMinhNeural→ffmpeg wav→paplay.
§
db-access: write chỉ VBSMEONL+VBSMEOFF (preview+token, SIT); mở write DB khác qua Hoàng. LIVE ≠ SIT schema.
§
Sổ hồ sơ: people.py + skill team-people.
§
Chat: gchat_send_file.py gửi file THẬT (không thả path local); gchat_dump.py đọc lịch sử; URL dài bọc code block.
§
Email: google_token.json + google_calendar_token.json; chỉ ping mail book họp/review; mail trong DM.
§
Manager của Hoàng = chị Nguyên (users/105726904933324385534, Phó phòng P.DVNH).
§
Luật dạy qua KÊNH nào chỉ áp kênh đó (Siri: gọn, hỏi từng phần) — đừng lẫn kênh.
§
Siri/widget: cổng local :9444 speak + :9445 chat + gateway :9443 (127.0.0.1) sống sau teardown 17h30; chỉ node Tailscale tắt.
§
KHÔNG nhận/lưu mật khẩu, credential Hoàng gửi qua chat; từ chối + đưa cách không cần secret.
§
Bản đồ kênh: DM anh=chủ · DM 1:1 đồng nghiệp=hỗ trợ · VBB SME=dự án · DVNH-Daily=nội bộ · chồn ăn dưa=tán gẫu · Agent Space=bot khác · Home AAQAZxc2km8 (Ultron-Trợ lý, chỉ anh)=nhận báo cáo định kỳ.
§
Cấm grep -r trong ~/.hermes (cache json ~4,5MB làm phình ngữ cảnh).
§
Build graph UA + reasoning source: agy + model claude-opus-4-6-thinking
§
Nén: endpoint KHÔNG cache prefix; Hoàng chốt ngữ cảnh RỘNG cho task dài (ngưỡng 300k); tiết kiệm = cắt output công cụ, KHÔNG hạ ngưỡng.
§
Lô agy to (≥25 node / ≥30KB) hay fail rỗng + exit 0 khi cạn quota → cắt nhỏ ≤16KB/14 node; LUÔN kiểm size từng lô, đừng tin exit code.
§
Skill dự án (tester-support, ua-source-trace…) là user-owned → curator KHÔNG patch được; cần sửa thì báo Hoàng `hermes curator adopt <skill>`.