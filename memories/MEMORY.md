State sync: ~/Ultron/sync.sh mirror memory/skills/scripts/config/cron → git@github.com:VIethoangnguyenle/Ultron.git; restore.sh khôi phục máy mới. KHÔNG commit .env/auth.json/state.db — đổi máy phải cấp lại credential (`hermes setup` hoặc copy backup).
§
Bot Ultron live trên VNPay Workspace (chi tiết: skill google-chat-setup). Send gửi text thô, ko markdown — link <url|text>. Mention ĐỌC: userMention.user.name=='users/...'. Mention GHI: auto @người gọi trong group; @ai chủ động viết <users/<id>>, tra id bằng scripts/gchat_members.py. ⚠ bot ko có displayName nên chip chỉ '@' → KHÔNG chèn space (<users/ID>Kitty).
§
'chồn ăn dưa'=AAQAiOgBqio (test riêng)
§
Run `claude`/`agy` cho vietbanksme từ /home/zane/Desktop/work/vietbank/vietbank-sme (KHÔNG phải -omni); trước task nặng check RAM+CPU (free -h, uptime), abort nếu RAM trống <~2GB.
§
Restart gateway từ trong gateway bị chặn → dùng systemd-run --user transient (sleep N rồi systemctl --user restart hermes-gateway).
§
Đọc ảnh: dùng agy (model gemini-3.8-flash-medium), KHÔNG giao claude; phải redirect output ra file (pipe làm agy mất sạch output). auxiliary.vision hay bị 403 'Model is blocked'.
§
agentmemory đã cài (systemd, MCP 54 tool, EMBEDDING_PROVIDER=local). Xem skill agentmemory.
§
db-access: quyền write CHỈ trên VBSMEONL+VBSMEOFF (sql_write 2 bước: preview+token). Ghi DB chỉ SIT; tự test tool thì chỉ INSERT 1 bản ghi mới rồi sửa/xoá chính nó — KHÔNG đụng data cũ; nhờ vả thật thì đo ảnh hưởng + xin xác nhận mới chạy; mở write DB khác phải qua Hoàng.
§
Chat chỉ đẩy event khi bot được @mention (adapter hồi cứu 8 tin trước + chèn [NGỮ CẢNH]). Bot↔bot BẤT KHẢ THI (Google ko giao event app↔app) → bridge qua Agent Space + envelope [[A2A:v1 from=<alias> to=<alias>]]; alias ultron/kitty; registry ~/.hermes/a2a_agents.json; helper scripts/a2a.py; chi tiết: skill agent-space-knowledge.
§
Sổ hồ sơ đồng nghiệp: ~/.hermes/people.json (115 người từ 3 space) + scripts/people.py (list/show/note/set/add/sync) + skill team-people. Tra bằng users/<id>; bot/app phải add tay.
§
Đọc lại lịch sử Chat: scripts/gchat_dump.py (read token, chỉ đọc).