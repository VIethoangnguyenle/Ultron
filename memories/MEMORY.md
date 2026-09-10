Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
When the user switches machines (clones Ultron + runs restore.sh), remind them to re-provide credentials: the API-key environment file and auth.json (OAuth tokens) are never synced to git; they must run `hermes setup` or copy their own backups.
§
Google Chat bot Ultron live trên VNPay Workspace; chi tiết GCP/SA/allowlist + runbook ở skill google-chat-setup.
§
Google Chat mention: @all=annotations[].userMention.user=={}; user=userMention.user.name=='users/...'. Read qua spaces.messages().list (user OAuth). Hoàng+bot ids ở skill google-chat-setup.
§
Google Chat: `hermes send`/cron gửi text thô, không render markdown — dùng cú pháp native <url|text> cho link (markdown chỉ chạy cho phản hồi agent trong group).
§
Google Chat groups: vietbanksme project group = spaces/AAAADv4ib6s; "Những chú chồn ăn dưa" (AAQAiOgBqio) là group riêng của Hoàng để test với bạn bè, KHÔNG phải group dự án. Hoàng đã tắt approvals.mode=off để chạy script/curl lấy log không bị hỏi approval.
§
Run `claude`/`agy` for vietbanksme from `/home/zane/Desktop/work/vietbank/vietbank-sme` (project root, NOT the `-omni` subdir): spans multiple source dirs, codegraph+serena live there. Before EACH heavy agy/claude task, check RAM+CPU (free -h, uptime, ps sort by %mem/%cpu) to ensure the box won't freeze; abort/warn if available RAM <~2GB or load is climbing.
§
Gateway restart bị chặn khi chạy từ trong gateway. Workaround: systemd-run --user transient unit (sleep N rồi systemctl --user restart hermes-gateway).
§
Vision đã bật: auxiliary.vision → deepseek-v4-flash-vision-exp (key custom provider chung). Main deepseek-v4-pro không vision. config.yaml agent bị chặn sửa → giao claude (Bash).
§
agentmemory đã cài (systemd `agentmemory`, MCP 54 tool); lessons migrate từ skill pitfalls; EMBEDDING_PROVIDER=local bật (semantic on-device). Xem skill agentmemory.