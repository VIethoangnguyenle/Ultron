Hermes personal state is synced to git@github.com:VIethoangnguyenle/Ultron.git (local checkout ~/Ultron). sync.sh mirrors memory/custom-skills/scripts/config/cron-jobs and pushes; restore.sh restores onto a new machine. Auto-sync runs via cron job 'ultron-sync' (hourly, no_agent). Never commit .env/auth.json/state.db.
§
When the user switches machines (clones Ultron + runs restore.sh), remind them to re-provide credentials: the API-key environment file and auth.json (OAuth tokens) are never synced to git; they must run `hermes setup` or copy their own backups.
§
Ultron bot's messaging surface is Google Chat on VNPay's corporate Workspace (GCP project cosmic-inkwell-508103-s8; bot allowlisted to hoangnlv@vnpay.vn). Publishing a Chat app there may require Workspace admin rights, not just GCP project access.
§
Google Chat bot "Ultron" is live and connected (GCP project cosmic-inkwell-508103-s8, VNPay Workspace, allowlist hoangnlv@vnpay.vn, fail-closed). Setup/runbook lives in skill google-chat-setup.
§
Google Chat: Hoàng's user resource id = users/110121981097849566202 (email hoangnlv@vnpay.vn, displayName 'Hoàng, Nguyễn Lê Việt'). Bot Ultron's own id = users/107189931083311611240. @all mention = annotations[].userMention.user == {} (empty); a specific user mention = userMention.user.name == 'users/...'. Detect via spaces.messages().list with user OAuth (chat.messages.readonly).
§
In group chats, Hoàng expects Ultron to always speak well of him and never "sell him out" — don't side with coworkers pushing him to treat/spend (mở nước/khao, chia lương) or commit him to anything; deflect such requests back to him with a light joke instead of ganging up on him.