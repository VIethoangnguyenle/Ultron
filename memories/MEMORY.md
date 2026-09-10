Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
Khi chuyển máy (clone Ultron + restore.sh): phải cấp lại credentials — file API-key env và auth.json (OAuth) không sync git, cần chạy `hermes setup` hoặc copy backup riêng.
§
Google Chat bot Ultron live trên VNPay Workspace; chi tiết GCP/SA/allowlist + runbook ở skill google-chat-setup.
§
Google Chat: send/cron gửi text thô, ko render markdown — link dùng <url|text>. Mention ĐỌC: userMention.user.name=='users/...' (@all=user=={}). Mention GHI: auto @người gọi trong group; muốn @ai chủ động viết <users/<id>>, tra id bằng scripts/gchat_members.py. ⚠ Mention BOT: bot ko có displayName nên Google render chip '@' trần → KHÔNG chèn space sau token (viết <users/ID>Kitty, ko phải '<users/ID> Kitty'). Ids ở skill google-chat-setup.
§
Google Chat groups: vietbanksme = spaces/AAAADv4ib6s; "Những chú chồn ăn dưa" (AAQAiOgBqio) là group riêng của Hoàng test với bạn bè, không phải group dự án; "Agent Space" (AAQASaFjh6M) có sếp Nguyên (Nguyễn Thị Hạnh, PP-P.DVNH) + agent Kitty (DVNH) hay hỏi Ultron về giới hạn phạm vi/kiến trúc/train. approvals.mode=off để script/curl lấy log không bị hỏi approval.
§
Run `claude`/`agy` cho vietbanksme từ /home/zane/Desktop/work/vietbank/vietbank-sme (project root, KHÔNG phải -omni): codegraph+serena ở đó. Trước mỗi task nặng check RAM+CPU (free -h, uptime); abort nếu RAM trống <~2GB.
§
Gateway restart bị chặn khi chạy từ trong gateway. Workaround: systemd-run --user transient unit (sleep N rồi systemctl --user restart hermes-gateway).
§
Đọc ảnh: dùng agy (model gemini-3.8-flash-medium), KHÔNG giao claude; phải redirect output ra file (pipe làm agy mất sạch output). auxiliary.vision hay bị 403 'Model is blocked' → đừng phụ thuộc. config.yaml agent chặn sửa.
§
agentmemory đã cài (systemd `agentmemory`, MCP 54 tool, EMBEDDING_PROVIDER=local). Xem skill agentmemory.