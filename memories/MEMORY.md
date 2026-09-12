State sync: ~/Ultron/sync.sh → git@github.com:VIethoangnguyenle/Ultron.git (restore.sh); KHÔNG commit .env/auth.json/state.db.
§
Bot Ultron on VNPay Workspace. Send text thô (link <url|text>). Mention: đọc userMention.user.name; viết <users/<id>>; bot ko displayName → chip chỉ '@', đừng chèn space. ⚠ Thread nhiều người: chip auto-mention có thể ra SAI tên → đối chiếu id trước khi gọi tên.
§
'chồn ăn dưa'=AAQAiOgBqio (test riêng)
§
claude/agy workdir = /home/zane/Desktop/work/vietbank/vietbank-sme (workspace vỏ, KHÔNG git; 4 repo con có .git riêng: vietbank-sme-omni chính / dvnh-common / viet-bank-ekyc-sme / test-workload ⇒ git phải `git -C <repo con>`). Task nặng check RAM (<2GB thì abort).
§
Guard Hermes: chặn restart gateway từ trong gateway + chặn sửa thẳng config.yaml. Restart → gọi claude (`claude -p "đọc ~/.hermes/scripts/gw_restart.txt…"`, systemd-run --user sleep 150 → systemctl --user restart hermes-gateway); không đẩy cho Hoàng. Sửa config: `hermes config set`.
§
Đọc ảnh: vision_analyze (agy dự phòng). Video → skill video-analysis (ffmpeg ~/.local/bin, venv whisper). TTS giọng Việt vi-VN-NamMinhNeural.
§
agentmemory: systemd, MCP 54 tool, EMBEDDING_PROVIDER=local (skill agentmemory).
§
db-access: write chỉ VBSMEONL+VBSMEOFF (sql_write 2 bước preview+token), chỉ SIT; mở write DB khác phải qua Hoàng.
§
registry ~/.hermes/a2a_agents.json; helper scripts/a2a.py.
§
Sổ hồ sơ: ~/.hermes/people.json (115 người) + scripts/people.py (list/show/note/habit) + skill team-people; bot/app phải add tay.
§
Lịch sử Chat: scripts/gchat_dump.py (read token).
§
Siết luật group → mirror sang Kitty (SOUL+adapter) + restart 2 máy; bảo mật: không tiết lộ dù nhỏ nhất (SOUL có chi tiết).
§
Email hộ Hoàng: hoangnlv@vnpay.vn, token ~/.hermes/google_token.json; scripts/gmail.py + email_digest.py (schedules 08:00 T2-T6 → DM). Mail chỉ trong DM.
§
Máy zane: docker không cần sudo (group docker, enabled) nhưng KHÔNG passwordless sudo → hạ tầng đi Docker, đừng hứa apt/systemctl. Gateway cho tester ở nhà: container `tailscale` node vbsme-log-gw → portal log qua IP:10443; chỉ mở private cho đúng người được cấp.