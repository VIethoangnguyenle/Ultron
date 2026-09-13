State sync: ~/Ultron/sync.sh → git@github.com:VIethoangnguyenle/Ultron.git (restore.sh); KHÔNG commit .env/auth.json/state.db.
§
Bot Ultron on VNPay Workspace. Send text thô (link <url|text>). Mention: đọc userMention.user.name; viết <users/<id>>; bot ko displayName → chip chỉ '@', đừng chèn space. ⚠ Thread nhiều người: chip auto-mention có thể ra SAI tên → đối chiếu id trước khi gọi tên.
§
Tên gọi Hoàng đặt: Jarvis=claude CLI, Matcha=agy. VIỆC VIẾT CODE mới (script/tool/cổng) ⇒ luôn giao claude, Ultron không tự viết (Hoàng chốt 13/09).
§
Guard Hermes: chặn restart gateway từ trong gateway + chặn sửa config.yaml trực tiếp; restart → gọi claude đọc ~/.hermes/scripts/gw_restart.txt; sửa config: `hermes config set`.
§
Đọc ảnh: vision_analyze (agy dự phòng). Video → skill video-analysis. TTS giọng Việt vi-VN-NamMinhNeural.
§
agentmemory: systemd, MCP 54 tool, EMBEDDING_PROVIDER=local.
§
db-access: write chỉ VBSMEONL+VBSMEOFF (sql_write 2 bước preview+token), chỉ SIT; mở write DB khác phải qua Hoàng.
§
Sổ hồ sơ: people.json + scripts/people.py (list/show/note/habit) + skill team-people; bot/app phải add tay.
§
Chat: gchat_dump.py (đọc lịch sử), gchat_send_file.py --space --file (gửi ảnh/file THẬT lên chat — không bao giờ thả path local).
§
Email: token ~/.hermes/google_token.json; scripts/gmail.py + email_digest.py (08:00 T2-T6 → DM). Mail chỉ trong DM.
§
gateway :9443 đã bind 127.0.0.1 (13/09) ⇒ widget/Siri local vẫn chạy sau teardown 17h30.
§
Manager của Hoàng = chị Nguyên (users/105726904933324385534, Phó phòng P.DVNH).
§
Luật dạy qua KÊNH nào chỉ áp kênh đó (luật Siri: gọn văn nói, hỏi từng phần mỗi lượt 1 câu, lọc input méo, manager=chị Nguyên) — không lẫn sang chat/group.
§
Lịch: schedules.yaml có every_minutes+between (lặp 15') — không tạo cron job.
§
Siri/widget: node Tailscale `ultron` (ultron.tail5d68a5.ts.net), 2 cổng :9444 speak + :9445 chat (local-first); token state/siri_token.txt; teardown 17h30 chỉ tắt node, không tắt cổng.