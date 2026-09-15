# Cổng db-access: source, quyền, và cách tra trực tiếp

## Kiến trúc cổng

- MCP HTTP: `http://127.0.0.1:8443/mcp`. Hermes nối qua entry `db-access` trong `~/.hermes/config.yaml`
  (header `x-api-key`).
- Chạy bằng **user systemd unit** `mcp-db-tools` (`ExecStart` = `node dist/index.js` trong
  `~/Desktop/tools/mcp/Db-Access`) ⇒ restart không cần sudo, nhưng vẫn phải xin phép Hoàng.
- Config `~/Desktop/tools/mcp/Db-Access/config.yaml` có 2 block:
  - `databases:` — connection thật (type/host/port/service/user/pass; pass/user lấy từ `.env`).
  - `sources:` — mỗi source một `apiKey` + danh sách `access:` `<DB>: [read, write]`.
  - `apiKey` trong config là tham chiếu `${VAR}`; giá trị thật nằm trong `.env` cùng thư mục.
- Hot-reload: `fs.watchFile(CONFIG, {interval: 1000})` → `dotenv.config({override: true})` +
  `reloadConfig()` + `initSourceIndex()`. Log nhận biết: `[config] reloaded from ./config.yaml`.

## Quyền là theo SOURCE, không theo connection

- `list_databases` trả về **giao** của (DB có connection) ∩ (DB được cấp cho key đang dùng).
- Vì vậy hai triệu chứng này KHÁC nhau và phải phân biệt:
  - *Thiếu quyền* → `Database '<X>' not found or access denied` (connection có thể vẫn tồn tại).
  - *Thiếu connection* → không có entry trong block `databases:`. **Kiểm tồn tại trước khi xin thông tin
    kết nối:** nhiều DB của cùng dự án dùng chung một Oracle instance (mỗi schema một user, cùng
    host/port/service) — từ connection của DB anh em chạy
    `SELECT COUNT(*) FROM SYS.ALL_USERS WHERE USERNAME='<SCHEMA>'`; nếu có thật thì thêm entry mirror
    đúng entry anh em, KHÔNG tự bịa host/user và cũng không cần hỏi host/port.
- Ví dụ cấu trúc (LUÔN đọc lại config, đừng hardcode): source `default_agent` (key Hermes đang dùng)
  giữ nhóm DB của một dự án + vài DB dùng chung; các source khác chia theo dự án/đối tác, mỗi source
  một tập DB riêng. DB của dự án mới muốn tra được thì phải được thêm vào **đúng source của key mình dùng**.

## Tầng dưới connection: `127.0.0.1:<port>` là SSH TUNNEL, không phải DB local

Mọi entry trong `databases:` trỏ host `127.0.0.1` + port; các port đó do user unit **`mcp-db-tunnel`**
giữ bằng `ssh -N -L <port>:<host-thật>:<db-port> ... <jump-host>` (mỗi port một đích khác nhau, không
nhất thiết cùng máy). Hệ quả: có 3 lớp lỗi khác nhau, **đọc đúng mã lỗi để đi đúng lớp**:

| Triệu chứng | Lớp lỗi | Việc đúng |
|---|---|---|
| `Database '<X>' not found or access denied` | Source/quyền | Đọc block `sources:`, xin cấp cho đúng key |
| `NJS-503: connection to host 127.0.0.1 port <p> could not be established` / `ECONNREFUSED 127.0.0.1:<p>` | Tầng tunnel/mạng | Xem mục dưới — **đừng đi xin quyền, quyền không phải nguyên nhân** |
| `ORA-01031` / `ORA-00942` khi query chéo schema | Quyền trong DB | Tra metadata `SYS.ALL_USERS` / `SYS.ALL_TABLES` rồi mới kết luận |

Quy trình khi gặp lỗi tầng tunnel:

1. `systemctl --user is-active mcp-db-tunnel` + `ss -tln | grep -E ':<port>'` — port không LISTEN = tunnel chết.
2. `journalctl --user -u mcp-db-tunnel -n 10 --no-pager`: dòng `Network is unreachable` / `ExitOnForwardFailure`
   nghĩa là máy đang **không có route tới jump host** (hay gặp khi đổi mạng, ví dụ chuyển sang Wi-Fi) —
   không phải credential sai.
3. Sửa: `systemctl --user restart mcp-db-tunnel`, chờ ~5s, kiểm lại `ss -tln` rồi query lại bằng chính key của mình.
   Tunnel là user unit nên restart không cần sudo, và **không đụng tới `mcp-db-tools`** (luật cấm chỉ áp cho service cổng DB).
4. Sau khi tự khởi động lại tunnel, báo lại người dùng đã làm gì để họ veto nếu muốn.

## Tra trực tiếp không cần restart gateway

Dùng khi session MCP đang giữ snapshot quyền cũ (xem pitfall trong SKILL.md).

Handshake streamable-HTTP, đúng thứ tự:

1. `POST /mcp` `initialize` — headers: `content-type: application/json`,
   `accept: application/json, text/event-stream`, `x-api-key: <key của source>` → response trả header
   `mcp-session-id`.
2. `POST` `notifications/initialized` (kèm `mcp-session-id`).
3. `POST` `tools/call` `{"name":"sql_read","arguments":{"db_name":"<SCHEMA>","sql":"..."}}`.
   Kết quả nằm ở `result.content[0].text`; response có thể là SSE (dòng `data: {...}`) nên phải parse.

Chạy `scripts/mcp_direct_query.py` thay vì gõ tay. Tuyệt đối **không in apiKey** ra chat/log hay
commit.

## Luật an toàn khi đổi quyền

- Không tự sửa `config.yaml` của Db-Access, không tự restart `mcp-db-tools`.
- Xin Hoàng cho phép → chạy cổng MCP preflight → giao Jarvis; yêu cầu kèm: backup config trước khi
  sửa, giữ nguyên mọi entry cũ, chỉ cấp đúng mức `read`/`write` được duyệt, kiểm YAML hợp lệ.
- Sau khi sửa: tự verify độc lập (`list_databases` bằng chính key của mình) rồi mới báo cáo.

## Cách ly dự án: mã lỗi cùng số vẫn có thể khác nghĩa

Bảng mã lỗi của hai dự án khác nhau có thể trùng số nhưng nội dung khác hẳn (một mã ở dự án A là
"Soft OTP bị khoá", ở dự án B là "tài khoản nhận không được phép"). Đó là chuyện bình thường.

- Tra mã lỗi **luôn dùng bảng của đúng dự án** (theo `error_code_source` trong scope-map của skill
  `tester-support`), và chỉ tra trên schema của dự án đang phục vụ.
- **Trong group của dự án nào thì chỉ dùng kiến thức/nguồn của dự án đó** — không nhắc tên, không so
  sánh, không lấy kết quả đã tra ở dự án khác ra trả lời, kể cả khi hai dự án dùng chung thư viện hay
  chung hạ tầng. Ghi chú đối chiếu giữa các dự án (nếu cần) chỉ để nội bộ, không xuất hiện trong câu
  trả lời cho tester.
- Hệ quả đã gặp thật: hai dự án có thể dùng **hai bảng mã lỗi khác nhau** (bảng chung kiểu `AD_MESSAGE`
  ở một bên, bảng chuyên biệt kiểu `MESSAGE_EKYC` ở bên kia) ⇒ tra sai bảng là báo sai nghĩa cho tester.
