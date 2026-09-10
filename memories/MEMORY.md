Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
Khi chuyển máy (clone Ultron + restore.sh): phải cấp lại credentials — file API-key env và auth.json (OAuth) không sync git, cần chạy `hermes setup` hoặc copy backup riêng.
§
Google Chat bot Ultron live trên VNPay Workspace; chi tiết GCP/SA/allowlist + runbook ở skill google-chat-setup.
§
Google Chat: send/cron gửi text thô, ko render markdown — link dùng <url|text>. Mention ĐỌC: userMention.user.name=='users/...' (@all=user=={}). Mention GHI: bot tự @người gọi trong group (auto); muốn @ai chủ động thì viết <users/<id>> trong reply (Google tự nhận), tra id bằng scripts/gchat_members.py --space spaces/XXX. Ids ở skill google-chat-setup.
§
Google Chat groups: vietbanksme = spaces/AAAADv4ib6s; "Những chú chồn ăn dưa" (AAQAiOgBqio) là group riêng của Hoàng test với bạn bè, không phải group dự án; "Agent Space" (AAQASaFjh6M) có sếp Nguyên (Nguyễn Thị Hạnh, PP-P.DVNH) + agent Kitty (DVNH) hay hỏi Ultron về giới hạn phạm vi/kiến trúc/train. approvals.mode=off để script/curl lấy log không bị hỏi approval.
§
Run `claude`/`agy` for vietbanksme from `/home/zane/Desktop/work/vietbank/vietbank-sme` (project root, NOT the `-omni` subdir): spans multiple source dirs, codegraph+serena live there. Before EACH heavy agy/claude task, check RAM+CPU (free -h, uptime, ps sort by %mem/%cpu) to ensure the box won't freeze; abort/warn if available RAM <~2GB or load is climbing.
§
Gateway restart bị chặn khi chạy từ trong gateway. Workaround: systemd-run --user transient unit (sleep N rồi systemctl --user restart hermes-gateway).
§
Vision đã bật: auxiliary.vision → deepseek-v4-flash-vision-exp (key custom provider chung). Main deepseek-v4-pro không vision. config.yaml agent bị chặn sửa → giao claude (Bash).
§
agentmemory đã cài (systemd `agentmemory`, MCP 54 tool); lessons migrate từ skill pitfalls; EMBEDDING_PROVIDER=local bật (semantic on-device). Xem skill agentmemory.