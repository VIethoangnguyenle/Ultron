---
name: hermes-profile-isolation
description: "Use when a job needs its own locked-down Hermes profile."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [hermes, profile, cron, toolset, least-privilege, prompt-size, mcp]
    related_skills: [hermes-runtime-audit, ultron-scheduled-actions, hermes-mcp-config, google-chat-setup]
---

# Cô lập một workload vào profile Hermes riêng (least privilege)

Class of work: một job (cron) hoặc một agent phụ cần **persona / prompt / toolset / bộ nhớ riêng, hẹp hơn default**
— "chạy job Jira dưới profile riêng, không có terminal", "con bot này chỉ được đọc DB", "đừng để persona chính
lẫn vào việc định kỳ". Khác `hermes-runtime-audit` (chỉ ĐỌC + khai báo trạng thái): ở đây là **dựng, thắt quyền,
đo, rồi mới chuyển việc sang**.

## Luật chung

1. **Không suy luận toolset / prompt size — luôn đo bằng resolver thật** (`scripts/measure_cron_prompt.py`).
   Toolset hẹp hay rộng là kết quả của 3 tầng cấu hình chồng nhau; đọc config bằng mắt là đoán sai.
2. **Đo trên đúng nhà**: mọi lệnh đo/phân tích phải chạy với `HERMES_HOME=<profile dir>`, nếu không sẽ đo
   nhầm profile default (số liệu sai hoàn toàn mà không báo lỗi).
3. **Dừng ở các mốc user yêu cầu** và trình **số đo + danh sách tool đã resolve** trước khi đụng cron của
   profile default. Việc dựng profile là thay đổi có blast radius (job có thể gửi tin thật).
4. **Profile KHÔNG thừa hưởng `.env` của default** trừ khi clone ⇒ thiếu key thì job chết im lặng
   (không gọi được model, không gửi được tin). Kiểm tra key trước khi chạy thử.
5. **Job cũ giữ nguyên, chỉ disable** — không xoá, để còn rollback.

## Quy trình

### 1. Recon trước khi tạo
- `hermes profile --help`, `hermes tools --help`, `hermes cron create|edit --help`: **đọc help, đừng đoán cú pháp**
  (nhiều thứ không có cờ CLI, xem bước 4).
- Chọn model: hỏi gateway `/v1/model/info` (có `input_cost_per_token` / `output_cost_per_token`), không phải
  `/v1/models` (danh sách tên, không giá). Không có trường tốc độ ⇒ đừng hứa "nhanh hơn", chỉ nói rẻ hơn.
- Xác định **đường ticker** cho job (mục "Ticker" bên dưới) — quyết định này đổi cách bàn giao.

### 2. Tạo profile
```bash
hermes profile create <tên> --no-skills --description "<vai trò 1-2 câu>"
```
- `--description` được decomposer dùng để route theo vai trò ⇒ viết đúng việc, không viết tên.
- `--no-skills` **loại trừ** `--clone` / `--clone-from` / `--clone-all` (code chặn cứng). Muốn hẹp thì dùng
  `--no-skills` rồi tự copy đúng skill cần.
- `--no-skills` vẫn để lại **1 skill bundled luôn-on** (`autonomous-ai-agents/hermes-agent`) + `.bundled_manifest`
  → xoá nếu cần đúng số skill; marker `.no-bundled-skills` ở gốc profile giữ cho `hermes update` không seed lại.
- `hermes profile create` sinh wrapper `~/.local/bin/<tên>` = `hermes -p <tên> "$@"` (cờ `--no-alias` để bỏ).

### 3. SOUL.md của profile (≤ ~25 dòng)
Chỉ 3 thứ: **vai trò**, **ngôn ngữ trả lời**, **định dạng output** cho kênh sẽ nhận. Không copy SOUL.md của
profile chính (persona chính = token + hành vi sai). Với job cron, nhắc rõ: output CHÍNH LÀ tin gửi đi,
không phải câu trả lời cho người hỏi lại.

### 4. config.yaml tối thiểu của profile
```yaml
model: {default: <model>, provider: custom, base_url: ..., api_key: ${<ENV_KEY>}, api_mode: chat_completions}
custom_providers: [...]              # nếu endpoint riêng — khai context_length cho model
memory: {memory_enabled: false, user_profile_enabled: false}   # job stateless: bỏ banner MEMORY/USER khỏi prompt
platform_toolsets: {cron: [<tên-mcp-server>]}                  # cách THU HẸP đúng (xem mục dưới)
plugins: {enabled: []}
mcp_servers: {<chỉ server cần>: {..., tools: {exclude: [...]}}}
_config_version: <giữ nguyên số do lệnh create sinh ra>
```
**Đừng quên `platform_toolsets`**: profile mới sinh ra config KHÔNG có key này ⇒ rơi về bundle mặc định của
platform (đầy đủ core tool: terminal, file, code_execution, delegation, browser…) — profile "hẹp" mà vẫn full quyền.

### 5. .env của profile
Copy tay từ `.env` của default (chỉ **tên key ⇒ giá trị**, in ra tên + `len` để xác nhận, KHÔNG in giá trị):
- key model (`HERMES_*_API_KEY`),
- token MCP server mà profile khai,
- biến môi trường mà **adapter chiều GỬI** thực sự đọc (đọc code adapter, đừng copy cả bộ — biến chỉ dùng
  cho inbound là thừa).
Mỗi lượt job chạy, cron tự nạp lại `.env` **của chính profile đó** ⇒ chỉ cần key nằm trong `.env` profile.

### 6. Skill sang profile
Skill là **per-profile** (`<profile>/skills`) ⇒ copy đúng thư mục skill cần:
`cp -a ~/.hermes/skills/<cat>/<skill> ~/.hermes/profiles/<tên>/skills/<cat>/<skill>`.
Verify bằng đúng hàm mà cron preflight gọi, dưới HERMES_HOME của profile:
```bash
HERMES_HOME=<profile dir> <venv>/bin/python -c "
from tools.skills_tool import skill_view; import json
p=json.loads(skill_view('<tên skill>')); print(p['success'], p.get('readiness_status'), p.get('setup_needed'))"
```
`success: True` + `readiness_status: available` + `setup_needed: False` ⇒ preflight không chặn job.

### 7. Đo + trình, rồi mới chuyển job
Dùng `scripts/measure_cron_prompt.py` (mục Đo lường). Trình bảng: **toolset resolved · số tool trong schema ·
bytes tool-schema · ký tự system prompt · model · số skill**. Sau khi được duyệt mới tạo/chuyển job và chạy thử.

### 8. Chuyển job + chạy thử + verify lần chạy
```bash
hermes cron pause <id-job-cũ>                 # giữ nguyên nội dung, chỉ disable (đừng xoá)
hermes -p <tên> cron create "<cron expr>" "$(cat /tmp/prompt.txt)" \
    --name <tên job> --skill <skill> --deliver "<platform>:spaces/<id>"
hermes -p <tên> cron run <id-job-mới>         # chạy NGAY ("Ran now: succeeded"), không cần chờ tới giờ
```
- Chép prompt job cũ bằng cách ghi ra file rồi `"$(cat file)"` — an toàn với prompt nhiều dòng/backtick,
  hơn là nhồi cả prompt vào một tham số dòng lệnh.
- Verify sau khi chạy, **từ artifact thật** (xem mục Đo lường): `jobs.json` của profile (`last_status`,
  `last_delivery_error`, `model_snapshot`), `cron/output/<job-id>/<ts>.md` (prompt + **nguyên văn** response),
  và `state.db` để biết model THỰC SỰ gọi tool gì.
- Đích gửi khác space đang chat sẽ sinh warning lành tính
  (`origin has thread_id=... but delivery target lost it`) — tin thành tin mới ở đích, không lỗi; muốn log sạch
  thì xoá `origin` của job (hỏi user trước).

## Thắt quyền toolset — 3 tầng, thứ tự ưu tiên

| Tầng | Ở đâu | Dùng khi nào |
|---|---|---|
| `enabled_toolsets` per-job | `jobs.json` (list[str] hoặc null) | **Tránh dùng để thu hẹp** — xem bẫy bên dưới; CLI không có cờ nào set được nó (không có `--toolsets` trong `cron create/edit --help`) |
| `platform_toolsets.<platform>` | `config.yaml` của profile | **Cách đúng để thu hẹp**: list có tên MCP server ⇒ thành allowlist, không merge thêm server nào |
| cứng trong code | cron luôn trừ `cronjob, messaging, clarify` | đừng đưa 3 tên này vào danh sách enable; `messaging` thậm chí **không phải toolset có thật** |

- `enabled_toolsets: null` = nền là `platform_toolsets` của platform đó.
- Bẫy: `enabled_toolsets` per-job **tự merge MỌI MCP server đang bật** của profile ⇒ ghi `['atlassian']` vẫn
  có thể kéo theo db-access/agentmemory/understand-anything. Muốn chắc thì đi qua `platform_toolsets`.
- Gửi tin của job cron KHÔNG đi bằng tool: dùng trường `deliver:`. Cron luôn trừ toolset messaging nên đừng
  hứa "cấp tool gửi tin".

## MCP tools: `include` là ALLOWLIST — dùng nó, đừng chăm danh sách `exclude`

`mcp_servers.<tên>.tools.include` CÓ thật: nó là **whitelist**. Khi có `include`, `exclude` bị bỏ qua
**hoàn toàn**; `include: []` = không đăng ký tool nào. Tên khớp theo tên **raw của MCP server**
(`jira_search`, KHÔNG phải `mcp__atlassian__jira_search`), hỗ trợ glob `*`/`?`/`[`, phân biệt hoa thường.
⇒ "chỉ được đọc" đúng cách là **allowlist vài tool đọc**, không phải blacklist tool ghi.

**Bẫy: 4 tool utility của MCP KHÔNG đi qua include/exclude** — `list_resources`, `read_resource`,
`list_prompts`, `get_prompt` do 2 cờ riêng `tools.resources` / `tools.prompts` quyết định (mặc định `true`,
⇒ vẫn còn sau khi đã `include`). Muốn "đúng N tool" thì tắt thêm 2 cờ đó và nói rõ với user rằng mình thêm
ngoài danh sách họ chốt. Số đo hiệu chỉnh (mcp-atlassian): `include: [jira_search, jira_get_issue]`
⇒ **6 tool** (2 jira + 4 utility); thêm `resources: false` + `prompts: false` ⇒ **2 tool**.
Luôn in lại **số tool RAW** sau khi sửa filter để chứng minh, đừng tin cảm giác "đã hẹp rồi".

Nếu user vẫn chọn blacklist (`exclude`): danh sách tay viết ra thường **thiếu** (mcp-atlassian: ngoài 5 tool
ghi hay được liệt kê còn ~20 tool ghi nữa như `jira_assign_issue`, `jira_move_issue`, `jira_create_sprint`,
`jira_batch_create_issues`, `jira_edit_comment` + 4 tool confluence ghi). Quy trình: đối chiếu danh sách loại
với **danh sách RAW tool** (`skip_tool_search_assembly=True`), rồi **trình phần còn lại cho user quyết** —
không tự thêm ngoài danh sách đã chốt, nhưng tuyệt đối không kết luận "đã chỉ đọc" khi rào duy nhất là một
câu dặn trong prompt.

## Ticker: cron là PER-PROFILE, job KHÔNG có trường `profile`

- `jobs.json` neo tại `get_hermes_home()` ⇒ job tạo trong profile nào thì lưu + chạy bằng `.env`/`config.yaml`/
  `skills` của profile đó. Signature `create_job()` **không có** tham số `profile`.
- Ticker trong gateway **chỉ tick nhiều profile khi `gateway.multiplex_profiles: true`** (mặc định false).
  Multiplex tắt ⇒ job nằm trong `profiles/<tên>/cron/jobs.json` **không bao giờ chạy**, im lặng.
- Hai đường hợp lệ:
  - **(A)** `hermes config set gateway.multiplex_profiles true` + restart gateway — đổi cách phục vụ bot cho
    MỌI profile, cần restart (guard: không tự restart gateway từ trong gateway).
  - **(B)** ở profile default, một **action trong `schedules.yaml`** (KHÔNG tạo cron job mới) chạy script
    gọi `hermes -p <tên> cron tick`. Chọn (B) khi cần giữ nguyên đường chat đang chạy.
    - `schedules.yaml` không chỉ có `when: "HH:MM"` — còn `every_minutes: N` + `between: ["HH:MM","HH:MM"]`,
      đúng thứ ticker cần. Cửa sổ hẹp quanh giờ chạy là đủ; tick thừa vô hại (job không còn tới hạn).
    - **Script của action BẮT BUỘC là `.py`**: dispatcher luôn chạy `[<venv>/bin/python, <path>, *args]`
      ⇒ một dòng `sh` / lệnh hệ thống không thể làm action script.
    - Script mới = việc viết code ⇒ theo luật của máy này là giao Jarvis/claude (chạy cổng MCP preflight
      trước khi giao), rồi **tự verify độc lập**: đọc lại source + chạy 2 lần (kỳ vọng exit 0, stderr rỗng,
      im lặng khi không có job tới hạn), không tin self-report.
    - Test đường thật ngay, đừng chờ tới giờ: `daily_dispatch.py --list` (action đã đăng ký chưa) rồi
      `daily_dispatch.py --run <id>` (fire ngay, bỏ qua đồng hồ).

## Deliver khi job chạy ngoài gateway

- Cron có **lane standalone**: không có adapter sống thì nó gọi thẳng sender của platform
  (`cron/scheduler_delivery.py` → `tools.send_message_tool._send_to_platform`) ⇒ `hermes -p <tên> cron tick`
  vẫn gửi được, không cần gateway.
- Mỗi lượt chạy job tự `load_hermes_dotenv(hermes_home=get_hermes_home())` + reset cache secret ⇒ key trong
  `.env` profile là đủ; nhưng **phải đúng key mà adapter chiều-gửi đọc** (với Google Chat: service-account JSON;
  project/subscription chỉ dùng cho inbound).
- Đích gửi nên khai tường minh (`<platform>:spaces/<id>`); gửi thử vào DM của user, KHÔNG vào space chung.
- **Đừng suy ra DM từ chỗ đang chat.** Space user đang nhắn có thể là group (`type=ROOM`/`spaceType=SPACE`).
  Xác minh bằng chính API: Gọi `GET https://chat.googleapis.com/v1/spaces/<id>` bằng token đọc của user
  (`~/.hermes/google_chat_read_token.json`, scope `chat.spaces.readonly`) → chỉ dùng khi
  `spaceType=DIRECT_MESSAGE` và `singleUserBotDm=true`. Đối chiếu chéo: dump vài tin trong space đó phải thấy
  tin do CHÍNH bot này gửi. Không tìm được DM space thì DỪNG và báo user, đừng gửi vào space chung.

## Đo lường

- `hermes prompt-size --platform <platform> [--json]` — dựng agent offline, số khớp wire, không gọi API.
- `scripts/measure_cron_prompt.py <label>` — **đo đúng đường cron** (MCP discovery → resolver cron → AIAgent →
  system prompt) và in: toolset resolved, số tool trong schema, số tool RAW (bỏ `tool_search` bridge), bytes
  tool-schema, ký tự/bytes system prompt, các section, danh sách tên tool. Nhớ chạy kèm `HERMES_HOME`.
- **MCP catalog lớn KHÔNG nằm trong system prompt**: nó nằm trong **description của tool `tool_search`** ⇒ schema
  chỉ còn 3 tool (`tool_search`/`tool_describe`/`tool_call`) nhưng bytes schema vẫn đáng kể. Khi so sánh phải so
  **cả** prompt **và** bytes schema, đừng chỉ nhìn số tool.
- Số tool có thể chênh giữa 2 lần đo vì `check_fn` của toolset (browser, image_gen…) trả `False` trong tiến
  trình đo ⇒ ghi rõ "đo được ở lần chạy khi toolset khả dụng" + lý do chênh.
- **Đối chiếu số đo với lần chạy THẬT** (đây là bước chứng minh, không phải suy luận):
  - `<profile home>/state.db` bảng `system_prompts(hash, prompt)` = đúng cái system prompt đã dùng cho lượt
    đó ⇒ so `length(prompt)` với con số đo tĩnh.
  - `<profile home>/state.db` bảng `messages(... tool_calls ...)` = tool model THỰC SỰ gọi ⇒ bằng chứng toolset
    hẹp không chặn việc job.
  - `<profile home>/cron/output/<job-id>/<ts>.md` = prompt + **nguyên văn** output đã gửi ⇒ dùng để trích dẫn
    "tin đã gửi" mà không phải dựng lại.
- **Đừng đọc log tool rồi kết luận tool có trong schema.** Khi catalog bị deferred, model gọi `tool_call` với
  TÊN TOOL Ở TRONG, nên log in ra `tool mcp__<server>__<tool> completed` như thể tool đó được gọi trực tiếp —
  trong khi schema chỉ có `tool_search`/`tool_describe`/`tool_call`. Bằng chứng đúng nằm ở `messages.tool_calls`
  (`function.name == "tool_call"`, tên thật nằm trong `arguments`).
- Index skill trong prompt = 0 khi profile không có toolset `skills*` — đó là thiết kế, không phải lỗi; skill
  gắn vào job vẫn nạp được qua preflight/`skill_view`.

## Pitfalls

- **`hermes cron show <id>` không tồn tại** — đọc `hermes cron list` / `hermes cron status` / `jobs.json`.
- **Suy luận toolset từ config = sai**: 3 tầng chồng nhau + MCP merge. Luôn dùng resolver thật.
- **Job chạy trước khi verify deliver = gửi nhầm space hoặc gửi rỗng.** Verify trước: `skill_view` (skill),
  danh sách tool (quyền), key trong `.env` (runtime).
- **File gửi lên Chat phải là file thật, không phải đường dẫn local.** Với script gửi file của bộ này,
  `--thread` **bắt buộc là resource name đầy đủ** `spaces/<sid>/threads/<tid>`; dạng ngắn `threads/<tid>`
  bị Chat trả HTTP 400 *"invalid thread resource name"*. Xác nhận đã lên bằng response có `attachment`.
- **`ls profiles/` trước khi kết luận "đã có profile"** — lần tạo đầu tiên sẽ tạo cả thư mục `profiles/`.

## References

- `references/cron-toolset-resolution.md` — bản đồ hàm/đường resolve toolset của cron, ngữ nghĩa allowlist MCP,
  và bảng số đo hiệu chỉnh (profile đầy đủ vs profile hẹp) để biết mình đo đúng hay sai.
- `references/profile-layout.md` — profile create sinh ra gì (thư mục, template config/.env/SOUL, marker),
  ngữ nghĩa các cờ, wrapper `hermes -p`.
- `scripts/measure_cron_prompt.py` — probe đo toolset + prompt size theo đúng đường cron.
