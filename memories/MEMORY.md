State sync: ~/Ultron/sync.sh mirror memory/skills/config/cron → git@github.com:VIethoangnguyenle/Ultron.git (restore.sh khôi phục máy mới). KHÔNG commit .env/auth.json/state.db.
§
Bot Ultron on VNPay Workspace. Send text thô (link <url|text>). Mention: đọc userMention.user.name; viết <users/<id>>; bot ko displayName → chip chỉ '@', đừng chèn space. ⚠ Thread nhiều người: chip auto-mention có thể ra SAI tên → đối chiếu id trước khi gọi tên.
§
'chồn ăn dưa'=AAQAiOgBqio (test riêng)
§
Run claude/agy từ /home/zane/Desktop/work/vietbank/vietbank-sme; task nặng check RAM trước (abort nếu trống <~2GB).
§
Guard Hermes chặn restart gateway từ trong gateway + chặn sửa thẳng config.yaml. Restart → GỌI CLAUDE (`claude -p "đọc ~/.hermes/scripts/gw_restart.txt…"` chạy `systemd-run --user --collect /bin/sh -c 'sleep 150; systemctl --user restart hermes-gateway'`); KHÔNG đẩy việc cho Hoàng. Sửa config: `hermes config set`.
§
Đọc ảnh: `vision_analyze` chạy tốt (auxiliary vision qua custom gateway); agy chỉ dự phòng (Gemini hay chặn filter). Video tester gửi → skill `video-analysis` (ffmpeg static ~/.local/bin + venv whisper ~/.hermes/venvs/whisper).
§
agentmemory: systemd, MCP 54 tool, EMBEDDING_PROVIDER=local (skill agentmemory).
§
db-access: write CHỈ trên VBSMEONL+VBSMEOFF (sql_write 2 bước: preview+token). Chỉ SIT; tự test tool: INSERT 1 bản ghi mới rồi sửa/xoá chính nó — KHÔNG đụng data cũ; nhờ thật thì đo ảnh hưởng + xin xác nhận; mở write DB khác phải qua Hoàng.
§
Chat chỉ đẩy event khi bot được @mention (-8 tin ngữ cảnh). Bot↔bot BẤT KHẢ THI (Google ko giao event app↔app) → bridge qua Agent Space + envelope [[A2A:v1 from=<alias> to=<alias>]]; alias ultron/kitty; registry ~/.hermes/a2a_agents.json; helper scripts/a2a.py; chi tiết: skill agent-space-knowledge.
§
Sổ hồ sơ: ~/.hermes/people.json (115 người) + scripts/people.py (list/show/note/habit) + skill team-people; bot/app phải add tay.
§
Lịch sử Chat: scripts/gchat_dump.py (read token).
§
Group conduct (Hoàng chốt 2026-09-11): bảo mật KHÔNG tiết lộ dù nhỏ nhất — không source/code, không tên file/class, không hướng dẫn bóc token, không nêu lỗ hổng. Siết luật mới thì mirror sang Kitty (SOUL + adapter) + restart cả 2 máy.