# Hướng dẫn cài đặt Ultron (Google Chat bot trợ lý Hoàng)

> Tài liệu này ghi lại **toàn bộ quá trình cài đặt thực tế** của Ultron, để người
> khác có thể dựa theo mà tự cài một con tương tự. Các giá trị cụ thể (GCP project,
> email service account, workspace...) là của Hoàng — **bạn phải thay bằng giá trị
> của chính mình**.

---

## Mục lục

1. [Ultron là gì](#1-ultron-là-gì)
2. [Yêu cầu trước khi cài](#2-yêu-cầu-trước-khi-cài)
3. [Cài Hermes Agent](#3-cài-hermes-agent)
4. [Cài Google Chat bot](#4-cài-google-chat-bot)
5. [Cấu hình config.yaml](#5-cấu-hình-configyaml)
6. [Cấu hình .env (secrets)](#6-cấu-hình-env-secrets)
7. [Cài các tool phụ](#7-cài-các-tool-phụ)
8. [Scripts + cron jobs](#8-scripts--cron-jobs)
9. [Skills (kiến thức dự án)](#9-skills-kiến-thức-dự-án)
10. [Sync / restore qua git](#10-sync--restore-qua-git)
11. [Các fix quan trọng đã áp dụng](#11-các-fix-quan-trọng-đã-áp-dụng)

---

## 1. Ultron là gì

Ultron = **trợ lý cá nhân của Hoàng**, chạy trên Hermes Agent (Nous Research), kết nối
vào **Google Chat** trong workspace VNPay. Nó:

- Trả lời đồng nghiệp (tester/BA/dev) trong group khi được `@mention`.
- Tra mã lỗi, giải thích nghiệp vụ, truy log, tra dữ liệu DB SIT.
- Xuất báo cáo / diagram / PDF gửi lên group.
- Đọc ảnh, render markdown + mermaid thành PDF.
- Cho tester câu SQL (SELECT + UPDATE/DELETE/INSERT kèm ràng buộc).

**Hai tầng quan trọng:** (1) con bot (Hermes gateway) nhận/gửi tin nhắn; (2) bộ não
(model LLM + skills + MCP) tạo ra câu trả lời.

---

## 2. Yêu cầu trước khi cài

| Thứ | Yêu cầu | Ghi chú |
|---|---|---|
| OS | Linux (Ubuntu/Debian) | Host thực tế: Linux 6.1 |
| Python | 3.10+ | Hermes cần |
| Node.js | 18+ (đang dùng v26) | để cài mermaid-cli / claude-code |
| npm | có | |
| Chrome | google-chrome (headless) | để render PDF |
| Google Workspace | có domain công ty | Gmail thường KHÔNG host được Chat app |
| GCP project | có quyền tạo SA + bật API | |
| Git + GitHub | có SSH key | để sync repo Ultron |

---

## 3. Cài Hermes Agent

Cài theo docs chính thức: https://hermes-agent.nousresearch.com/docs

Sau khi cài, Hermes nằm ở `~/.hermes/` (state) và `~/.hermes/hermes-agent/` (source).
Mọi thứ bên dưới đều thao tác trên 2 thư mục này.

---

## 4. Cài Google Chat bot

### 4.1 Kiến trúc (quan trọng, đọc kỹ)

- **Inbound**: Cloud Pub/Sub **pull subscription** (không cần public URL/tunnel).
- **Outbound**: Chat REST API.
- **HAI loại credential khác nhau, đừng trộn lẫn:**

| Credential | Dùng cho | JSON key |
|---|---|---|
| **Service Account** (bắt buộc) | Bot nhận/gửi tin nhắn | `{"type": "service_account", ...}` |
| **OAuth client_secret** (tùy chọn) | Gửi file đính kèm (`/setup-files`) | `{"installed": {...}}` hoặc `{"web": {...}}` |

> Chat `media.upload` **từ chối** xác thực bằng service account → gửi file phải đi qua
> OAuth cá nhân của từng user (`/setup-files`).

### 4.2 Các bước trên GCP Console (cần quyền Admin)

1. **Bật 2 API** trong project:
   - Google Chat API: `https://console.cloud.google.com/apis/library/chat.googleapis.com`
   - Cloud Pub/Sub API: `https://console.cloud.google.com/apis/library/pubsub.googleapis.com`
2. **Tạo Service Account** (IAM & Admin > Service Accounts > Create). **Không cần cấp
   project-level role** nào. Tạo key JSON, tải về.
3. **Pub/Sub > tạo TOPIC** id `hermes-chat-events`.
4. **Trong topic > tạo PULL subscription** id `hermes-chat-events-sub`, retention 7 ngày.
5. **IAM binding — bước hay sai nhất (TWO service accounts):**
   - Trên **SUBSCRIPTION**: thêm principal `<sa-của-bạn>` với role **Pub/Sub Subscriber**.
   - Trên **TOPIC**: thêm **Chat app's push service account** (tìm trong Google Chat API >
     Configuration > "Service Account Email", dạng `service-<project-number>@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`)
     với role **Pub/Sub Publisher**.
   - ⚠ ĐỪNG tráo 2 cái này. Subscriber trên subscription = SA của bạn; Publisher trên topic
     = SA `gsuiteaddons` (KHÔNG phải SA của bạn).
6. **Google Chat API > Configuration**: connection = Cloud Pub/Sub, trỏ vào **TOPIC full name**
   `projects/<proj>/topics/hermes-chat-events` (KHÔNG phải subscription). Bật DM + group.
   Đặt app status **LIVE**.
7. **Thêm bot vào space** (tìm theo tên app). Sự kiện `ADDED_TO_SPACE` sẽ resolve bot user_id.

### 4.3 Cấu hình phía host (idempotent)

```bash
cd ~/.hermes/hermes-agent

# Kiểm tra dependencies (thường chỉ thiếu google-cloud-pubsub)
venv/bin/python -c "from plugins.platforms.google_chat.adapter import check_google_chat_requirements"
# nếu False: ~/.hermes/bin/uv pip install --python venv/bin/python google-cloud-pubsub==2.39.0

# Lưu credential quyền 600
install -m 600 /path/to/service-account.json ~/.hermes/google-chat-sa.json
install -m 600 /path/to/client_secret.json ~/.hermes/google_chat_user_client_secret.json
```

### 4.4 Chạy setup wizard

```bash
hermes gateway setup   # chọn Google Chat, điền env vars
```

Hoặc ghi thẳng vào `~/.hermes/.env` (xem mục 6).

---

## 5. Cấu hình config.yaml

File `~/.hermes/config.yaml`. Đây là phần cấu hình "não" của Ultron.

### 5.1 Model chính

```yaml
model:
  default: deepseek-v4-pro
  provider: custom
  base_url: https://api-llm.x.vnshop.cloud/v1        # gateway LLM nội bộ VNPay
  api_key: ${HERMES_CUSTOM_API_LLM_X_VNSHOP_CLOUD_API_KEY}
  api_mode: chat_completions
```

### 5.2 Custom provider (đăng ký gateway nội bộ)

```yaml
custom_providers:
  - name: VNPay LLM Gateway
    base_url: https://api-llm.x.vnshop.cloud/v1
    key_env: HERMES_CUSTOM_API_LLM_X_VNSHOP_CLOUD_API_KEY
    model: deepseek-v4-pro
    api_mode: chat_completions
    models:
      deepseek-v4-pro:
        context_length: 1000000
```

### 5.3 Vision (đọc ảnh) — bắt buộc vì model chính không có vision

```yaml
auxiliary:
  vision:
    provider: custom
    model: deepseek-v4-flash-vision-exp              # model vision của gateway nội bộ
    base_url: https://api-llm.x.vnshop.cloud/v1
    api_key: ${HERMES_CUSTOM_API_LLM_X_VNSHOP_CLOUD_API_KEY}
    timeout: 120
```

> ⚠ Không có block này thì `vision_analyze` sẽ rơi vào model không hiểu ảnh → báo
> "unsupported image". Model vision đúng phải thử bằng cách gọi `/v1/chat/completions`
> với payload `image_url` trước khi cấu hình.

### 5.4 MCP servers

```yaml
mcp_servers:
  db-access:                                        # tra DB Oracle/Mongo SIT
    url: http://127.0.0.1:8443/mcp
    headers:
      x-api-key: ${MCP_DB_ACCESS_API_KEY}
  atlassian:                                        # Jira + Confluence
    command: uvx
    args: ["--python=3.12", "mcp-atlassian"]
    env:
      CONFLUENCE_URL: https://wiki.servicehub.vn
      CONFLUENCE_USERNAME: hoangnlv@vnpay.vn
      CONFLUENCE_PERSONAL_TOKEN: ${MCP_ATLASSIAN_CONFLUENCE_TOKEN}
      JIRA_URL: https://jr.servicehub.vn/
      JIRA_USERNAME: hoangnlv@vnpay.vn
      JIRA_PERSONAL_TOKEN: ${MCP_ATLASSIAN_JIRA_TOKEN}
    tools:
      exclude: [ ...danh sách tool không cần... ]
  understand-anything:                              # graph reasoning source (agy)
    command: uv
    args:
      - --directory
      - /home/zane/Desktop/tools/mcp/Understand-Anything-MCP
      - run
      - server.py
    env:
      PROJECT_ROOTS: /home/zane/Desktop/work/vietbank/vietbank-sme,/home/zane/Desktop/work/dvnh-common
```

### 5.5 Platform Google Chat (typing indicator tuỳ chỉnh)

```yaml
platforms:
  google_chat:
    typing_status_text: Ultron đang nghĩ đã… 🤖💭
```

---

## 6. Cấu hình .env (secrets)

File `~/.hermes/.env` — **CHỈ chứa secret, không bao giờ commit vào git.**

```bash
# Google Chat bot (bắt buộc)
GOOGLE_CHAT_SERVICE_ACCOUNT_JSON=/home/zane/.hermes/google-chat-sa.json
GOOGLE_CHAT_PROJECT_ID=cosmic-inkwell-508103-s8
GOOGLE_CHAT_SUBSCRIPTION_NAME=projects/cosmic-inkwell-508103-s8/subscriptions/hermes-chat-events-sub
GOOGLE_CHAT_ALLOWED_USERS=hoangnlv@vnpay.vn          # fail-closed: rỗng = chặn tất cả
GOOGLE_CHAT_HOME_CHANNEL=spaces/XXXX                  # tuỳ chọn, cho cron delivery

# LLM gateway nội bộ
HERMES_CUSTOM_API_LLM_X_VNSHOP_CLOUD_API_KEY=...

# MCP
MCP_DB_ACCESS_API_KEY=...
MCP_ATLASSIAN_CONFLUENCE_TOKEN=...
MCP_ATLASSIAN_JIRA_TOKEN=...
```

> `.env` là credential store; không đọc bằng read_file — dùng terminal nếu cần sửa.

---

## 7. Cài các tool phụ

### 7.1 Claude Code (coding/ops agent)

```bash
npm install -g @anthropic-ai/claude-code
claude          # đăng nhập lần đầu
```

Vai trò: Ultron điều phối `claude` cho việc coding/ops/infra (restart gateway, sửa config...).

### 7.2 mermaid-cli + asset render PDF

```bash
PUPPETEER_SKIP_DOWNLOAD=true npm install -g @mermaid-js/mermaid-cli
# copy asset mermaid (để render offline):
cp ~/.local/lib/node_modules/@mermaid-js/mermaid-cli/node_modules/mermaid/dist/mermaid.min.js \
   ~/.hermes/scripts/assets/mermaid.min.js
```

> ⚠ `mmdc` (mermaid-cli) KHÔNG dùng được trên máy có Chrome 114 (puppeteer-core 25.x không
> launch nổi Chrome 114). Render PDF dùng script `md2pdf.py` (Chrome `--print-to-pdf` trực tiếp).

### 7.3 Log analyzer (vnpay-log-analyzer)

```bash
# nằm ở ~/.claude/skills/vnpay-log-analyzer/ (của Claude Code)
# dùng script vblog.py để index/trace log
```

---

## 8. Scripts + cron jobs

### 8.1 Scripts trong `~/.hermes/scripts/`

| Script | Chức năng |
|---|---|
| `md2pdf.py` | Render markdown (+mermaid) → PDF nhanh (offline) |
| `gchat_reply.py` | Gửi reply vào thread (service account) cho @Hoàng-mention |
| `mention_poller.py` | Quét @Hoàng mention, theo dõi Hoàng trả lời chưa |
| `escalate_pending.py` | Forward các file escalate về DM Hoàng |
| `gchat_read_oauth.py` | Lấy OAuth read-token (chat.spaces/messages.readonly) |
| `resource_snapshot.py` | Snapshot tài nguyên máy (RAM/CPU/disk) |
| `ultron-sync.sh` | Sync state → repo git |

### 8.2 Cron jobs (đã đăng ký)

| Job | Lịch | Chức năng |
|---|---|---|
| `ultron-sync` | mỗi 60m | sync state → git |
| `ultron-escalate` | mỗi 2m | forward escalate → DM Hoàng |
| `ultron-mention-poller` | mỗi 2m | quét @Hoàng mention |
| `ultron-mention-reply` | mỗi 2m | quyết định trả lời hay escalate |
| `daily-resource-check` | 9h mỗi ngày | snapshot RAM/CPU |

---

## 9. Skills (kiến thức dự án)

Các skill tùy chỉnh trong `~/.hermes/skills/`:

| Skill | Chức năng |
|---|---|
| `tester-support` | Trả lời tester, scope theo project (scope-map) |
| `vbsme-db-lookup` | Tra DB SIT + cho tester câu SQL |
| `vbsme-error-diagnosis` | Chẩn đoán mã lỗi vbsme |
| `vbsme-flow-explainer` | Giải thích flow nghiệp vụ |
| `google-chat-setup` | Runbook cài/fix Google Chat bot |
| `markdown-mermaid-pdf` | Render markdown+mermaid → PDF |

**Scope map** (`references/scope-map.json` trong skill `tester-support`): map mỗi group →
đúng 1 dự án + đường dẫn các nguồn (graph, log, mã lỗi, DB, KB). **Đọc nó trước khi trả lời
bất kỳ câu hỏi nào** — không hardcode bảng/schema/DB trong đầu.

---

## 10. Sync / restore qua git

Repo: `git@github.com:VIethoangnguyenle/Ultron.git` (local `~/Ultron`).

**Sync (đẩy lên):** `sync.sh` (tự động qua cron `ultron-sync`).
**Restore (máy mới):**

```bash
git clone git@github.com:VIethoangnguyenle/Ultron.git ~/Ultron
bash ~/Ultron/restore.sh        # copy state về ~/.hermes
```

⚠ **Sau khi clone phải cấp lại credential** — `.env` (API keys) và `auth.json` (OAuth
tokens) là secret, KHÔNG bao giờ commit. Chạy `hermes setup` hoặc copy backup `.env`/`auth.json`
của mình vào `~/.hermes/`.

**Không commit:** `.env`, `auth.json`, `state.db` (+ WAL/SHM).

---

## 11. Các fix quan trọng đã áp dụng

Đây là các bug đã gặp + cách fix (để người cài sau khỏi dẫm lại):

1. **Gửi file PDF bị "unsupported file type"** → root cause: mimetype cứng
   `application/octet-stream`. Fix: đoán mimetype theo extension (`mimetypes.guess_type`).
2. **Gửi file timeout ngắt quãng** → thêm retry (transient error: timeout/broken pipe/429/5xx)
   vào `_send_file`.
3. **Trả lời lộn thread** → root cause: typing-card state key theo `space` thay vì `thread`.
   Fix: key theo `(space, thread)`.
4. **Vision báo "unsupported image"** → root cause: model chính không có vision + thiếu
   `auxiliary.vision`. Fix: cấu hình model vision (mục 5.3).
5. **Render PDF chậm 6 phút** → root cause: load mermaid từ CDN. Fix: dùng asset mermaid local
   + Chrome `--print-to-pdf` (0.4s).
6. **Kết luận sai "log đã bị xóa"** → UAT log zip theo THÁNG; log cũ nằm trong zip tháng đó.
   Đừng kết luận mất log chỉ vì danh sách phẳng không thấy ngày — phải mò zip tháng.

### 11.1 Quy tắc an toàn (bắt buộc, đọc kỹ trước khi cài cho người khác)

- **Không commit secret** (`.env`, token, key, `auth.json`).
- **Cho tester câu SQL:** SELECT tự do; UPDATE/DELETE/INSERT phải có WHERE chặt + kèm cảnh báo;
  DROP/TRUNCATE/ALTER cấm + escalate.
- **Không lộ tiến trình trace / code nội bộ** ra group — chỉ đưa kết quả nghiệp vụ cuối.
- **Escalate về Hoàng** khi gặp: deadline, số liệu, quyết định kỹ thuật, thông tin nhạy cảm.

---

## Phụ lục: giá trị máy-specific của Hoàng (tham chiếu)

> Đây là giá trị của Hoàng, **bạn thay bằng của mình**. Ghi lại để tiện debug.

- GCP project: `cosmic-inkwell-508103-s8`
- SA email (Hermes): `ultron-tr-l-ho-ngnlv@cosmic-inkwell-508103-s8.iam.gserviceaccount.com`
- Chat app pusher SA: `service-698401240103@gcp-sa-gsuiteaddons.iam.gserviceaccount.com`
- Topic: `projects/cosmic-inkwell-508103-s8/topics/hermes-chat-events`
- Subscription: `projects/cosmic-inkwell-508103-s8/subscriptions/hermes-chat-events-sub`
- Allowlist: `hoangnlv@vnpay.vn`
- Hoàng user id: `users/110121981097849566202`
- Bot Ultron id: `users/107189931083311611240`
- Group vietbanksme: `spaces/AAAADv4ib6s`
- Group riêng Hoàng (test bạn bè): `spaces/AAQAiOgBqio`
