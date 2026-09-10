Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
When the user switches machines (clones Ultron + runs restore.sh), remind them to re-provide credentials: the API-key environment file and auth.json (OAuth tokens) are never synced to git; they must run `hermes setup` or copy their own backups.
§
Google Chat bot "Ultron" is live on VNPay Workspace (GCP project cosmic-inkwell-508103-s8, allowlist hoangnlv@vnpay.vn, fail-closed); publishing a Chat app there may need Workspace admin rights, not just GCP project access. Runbook in skill google-chat-setup.
§
Google Chat mention detection: @all = annotations[].userMention.user=={}; specific user = userMention.user.name=='users/...'. Read via spaces.messages().list with user OAuth. (Hoàng + bot user ids are in skill google-chat-setup.)
§
Google Chat: `hermes send`/cron gửi text thô, không render markdown — dùng cú pháp native <url|text> cho link (markdown chỉ chạy cho phản hồi agent trong group).
§
Google Chat groups: vietbanksme project group = spaces/AAAADv4ib6s; "Những chú chồn ăn dưa" (AAQAiOgBqio) là group riêng của Hoàng để test với bạn bè, KHÔNG phải group dự án. Hoàng đã tắt approvals.mode=off để chạy script/curl lấy log không bị hỏi approval.
§
Run `claude`/`agy` for vietbanksme from `/home/zane/Desktop/work/vietbank/vietbank-sme` (project root, NOT the `-omni` subdir): spans multiple source dirs, codegraph+serena live there. Before EACH heavy agy/claude task, check RAM+CPU (free -h, uptime, ps sort by %mem/%cpu) to ensure the box won't freeze; abort/warn if available RAM <~2GB or load is climbing.
§
Gateway restart from inside the gateway is blocked by a guardrail (even via claude/script). Workaround: schedule a systemd user timer (OnActiveSec=15s → systemctl --user restart hermes-gateway); verify linger=yes first.