Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
When the user switches machines (clones Ultron + runs restore.sh), remind them to re-provide credentials: the API-key environment file and auth.json (OAuth tokens) are never synced to git; they must run `hermes setup` or copy their own backups.
§
Google Chat bot "Ultron" is live on VNPay Workspace (GCP project cosmic-inkwell-508103-s8, allowlist hoangnlv@vnpay.vn, fail-closed); publishing a Chat app there may need Workspace admin rights, not just GCP project access. Runbook in skill google-chat-setup.
§
Google Chat: Hoàng's user resource id = users/110121981097849566202 (email hoangnlv@vnpay.vn, displayName 'Hoàng, Nguyễn Lê Việt'). Bot Ultron's own id = users/107189931083311611240. @all mention = annotations[].userMention.user == {} (empty); a specific user mention = userMention.user.name == 'users/...'. Detect via spaces.messages().list with user OAuth (chat.messages.readonly).
§
Google Chat: hermes send / cron delivery gửi text thô, KHÔNG render markdown [text](url) hay **bold** — phải dùng cú pháp native <url|text> mới thành link click được (bộ chuyển markdown chỉ chạy cho phản hồi agent trong group).
§
Google Chat groups: vietbanksme project group = spaces/AAAADv4ib6s; "Những chú chồn ăn dưa" (AAQAiOgBqio) là group riêng của Hoàng để test với bạn bè, KHÔNG phải group dự án. Hoàng đã tắt approvals.mode=off để chạy script/curl lấy log không bị hỏi approval.
§
Run `claude`/`agy` for vietbanksme from `/home/zane/Desktop/work/vietbank/vietbank-sme` (project root, NOT the `-omni` subdir): spans multiple source dirs, codegraph+serena live there. Before EACH heavy agy/claude task, check RAM+CPU (free -h, uptime, ps sort by %mem/%cpu) to ensure the box won't freeze; abort/warn if available RAM <~2GB or load is climbing.