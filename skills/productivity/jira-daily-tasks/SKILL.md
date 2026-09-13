---
name: jira-daily-tasks
description: "Use when quản lý task Jira của Hoàng mỗi sáng."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jira, atlassian, task-management, reminder, productivity]
---

# Quản lý task Jira hằng ngày của Hoàng

Skill để Ultron lấy danh sách task Jira chưa hoàn thành của Hoàng, thống kê
và gửi nhắc nhở mỗi sáng. Dùng MCP server `atlassian` (mcp-atlassian) đã kết
nối tới Jira của Hoàng.

## Kết nối (đã cấu hình sẵn)

- Server MCP: `atlassian` (stdio `uvx --python=3.12 mcp-atlassian`)
- Jira URL: `https://jr.servicehub.vn/`
- Jira username: `hoangnlv@vnpay.vn`
- Auth: Personal Access Token (PAT / Bearer), lưu trong `~/.hermes/.env` key
  `MCP_ATLASSIAN_JIRA_TOKEN`, được tham chiếu `${MCP_ATLASSIAN_JIRA_TOKEN}`
  trong `config.yaml` (KHÔNG đưa token vào config.yaml vì file này sync git).
- Tool Jira có tiền tố `mcp__atlassian__jira_*`.

## Tool chính cần dùng

- `mcp__atlassian__jira_search` — tìm issue bằng JQL (tool quan trọng nhất).
  Tham số: `jql` (bắt buộc), `fields` (mặc định 'summary,status,assignee,priority'),
  `limit` (1-50), `start_at`, `projects_filter`, `expand`.
- `mcp__atlassian__jira_get_issue` — chi tiết 1 issue.
- `mcp__atlassian__jira_get_sprint_issues` — issue trong sprint.
- `mcp__atlassian__jira_get_board_issues` — issue trong board.
- `mcp__atlassian__jira_get_issue_dates` — lịch sử ngày/trạng thái 1 issue.
- `mcp__atlassian__jira_get_issue_sla` — SLA của 1 issue.
- `mcp__atlassian__jira_get_user_profile` — thông tin user.

## JQL chuẩn — task CHƯA LÀM của Hoàng

Dùng `statusCategory != Done` là tín hiệu chuẩn nhất (loại đúng cả các trạng
thái "(Tester) Closed", "Resolved", "Cancelled" vốn đã xong nhưng status name
không phải chữ Done).

```
assignee = currentUser() AND statusCategory != Done ORDER BY priority DESC, updated DESC
```

Các trạng thái "chưa làm" thực tế ở Jira của Hoàng: `Need To Do`, `To Do`,
`In Progress`, `In Review`. Priority thường chỉ có `Medium`; phân loại theo
`status` quan trọng hơn priority ở đây.

### Biến thể theo nhu cầu

```
# Chưa làm + có deadline (duedate không rỗng)
assignee = currentUser() AND statusCategory != Done AND duedate is not EMPTY ORDER BY duedate ASC

# Đang làm dở (đang bận)
assignee = currentUser() AND status = "In Progress"

# Chưa bắt đầu (cần khởi động)
assignee = currentUser() AND status in ("To Do", "Need To Do")

# Chờ review / cần người khác duyệt
assignee = currentUser() AND status = "In Review"

# Cập nhật gần đây (7 ngày)
assignee = currentUser() AND updated >= -7d ORDER BY updated DESC
```

## Fields nên lấy khi liệt kê

`key,summary,status,priority,issuetype,updated,duedate,project` — thêm `project`
để lấy key + tên đầy đủ dự án (dùng phân nhóm theo Section dự án). Chỉ gọi
`jira_get_issue` khi cần chi tiết mô tả/comment của một task cụ thể.

## Format link cho task (BẮT BUỘC)

Google Chat KHÔNG render markdown `[text](url)` hay `**bold**` khi gửi qua
`hermes send` / cron delivery (text thô). Phải dùng cú pháp Google Chat native:
`<https://jr.servicehub.vn/browse/KEY|KEY>` — mới thành link click được.

Mỗi task một dòng, KEY là link:
`• <https://jr.servicehub.vn/browse/VSONB-5098|VSONB-5098>  Mở khóa người dùng - Duyệt lệnh`

Tránh: dấu `**` (Google Chat dùng `*` nếu cần bold, nhưng tốt nhất là không),
markdown link `[text](url)` (hiện nguyên văn, không click được).

Template gọn gàng (PHÂN THEO SECTION DỰ ÁN — mỗi project là một mục, kèm tên
đầy đủ dự án + key; trong mỗi project, mỗi task kèm trạng thái ngắn trong ngoặc):
```
📋 Task Jira hôm nay — 6 task chưa xong

📍 Vietbank SME Omni nội bộ (VSONB) — 4 task
• <url|VSONB-5098>  Mở khóa người dùng - Duyệt lệnh  (Need To Do)
• <url|VSONB-5025>  Dev Server - cắt chuỗi text  (To Do)

📍 Nam Á Bank SME (NABSME) — 2 task
• <url|NABSME-773>  Luồng chuyển khoản  (To Do)
```

## Quy trình báo cáo buổi sáng

1. Gọi `jira_search` với JQL `assignee = currentUser() AND statusCategory != Done
   ORDER BY priority DESC, updated DESC`, `limit=50`, và `fields` có kèm `project`.
2. Gom nhóm theo PROJECT (Section dự án): mỗi dự án là một mục tiêu đề
   `📍 <tên dự án> (<project key>) — N task`. Sắp xếp dự án theo số task giảm dần.
3. Trong mỗi dự án, mỗi task một dòng DẠNG LINK `<url|KEY>` kèm trạng thái ngắn
   trong ngoặc: `• <url|KEY>  tóm tắt  (trạng thái)`.
4. Nêu rõ tổng số task chưa làm ở đầu, và nhấn task nào đang bị trì hoãn lâu
   (dựa `updated` cũ) nếu có — cũng để dạng link.
5. KHÔNG tự chuyển trạng thái / sửa / tạo / xóa task hay thay đổi gì trên Jira
   trừ khi Hoàng yêu cầu rõ — mặc định chỉ ĐỌC (read-only).

## Tạo task Jira (CHỈ khi Hoàng yêu cầu rõ ràng)

Mặc định skill này chỉ ĐỌC. Khi Hoàng bảo tạo task:

- Project: `VSONB` (Vietbank SME Omni nội bộ) — issue type thực có: `Task`, `Story`, `Bug`, `Sub-task`, `Sub-bug`.
- Assignee: `hoangnlv@vnpay.vn` (truyền email vào `assignee`).
- Hạn chót: `additional_fields` = `{"duedate": "YYYY-MM-DD", "priority": {"name": "High"}}` — `High` chạy được.
- **Start date / End date** (2 field custom trên jr.servicehub.vn): `customfield_10801` = Start date, `customfield_10802` = End date, định dạng `YYYY-MM-DD`; set qua `jira_update_issue` `additional_fields` (hoặc cùng lúc khi tạo). Hoàng hay muốn 2 mốc này khớp khoảng thời gian thực tế của công việc.
- Mô tả viết theo Jira wiki: `## ` → heading `h2.`; bullet `* ` OK; **KHÔNG dùng `# `** (markdown numbered list bị convert thành heading `h1.`, mất dạng danh sách) — viết `* 1) ...` nếu cần đánh số. Khối SQL để trong `{code:sql}...{code}`.
- Mô tả task nên có mục *Timeline triển khai* chia theo **giai đoạn vòng đời** (lên ý tưởng/khảo sát → nghiên cứu & chọn nền tảng → dựng nền & thử nghiệm → mở rộng năng lực & test trong group → chạy hỗ trợ thực tế & ổn định), mỗi giai đoạn kèm khoảng ngày; đặt khớp với Start date/End date của task (Hoàng chốt 13/09).
- Đính kèm file (gói SQL gửi bank): MCP **chặn path ngoài `/home/zane/.hermes`** (`Path traversal detected`) ⇒ copy file vào `~/.hermes/attachments/` rồi truyền path đó vào `attachments`.
- Sau khi tạo/sửa: verify bằng `jira_get_issue` (fields ngắn) — đừng tin mỗi message "Issue created successfully".
- Nhắc task có hạn: KHÔNG tạo cron mới — task đã có `duedate` sẽ tự nằm trong báo cáo Jira hằng sáng.
- **Tạo task qua lệnh thoại (Siri):** thông tin thường thiếu ở lần nói đầu ⇒ thu **từng phần** (lưu nháp ở
  `~/.hermes/state/siri_draft.json`, mỗi lượt hỏi đúng 1 trường: việc gì → cho ai → start/hạn → ưu tiên),
  đủ trường mới tạo; tạo xong xoá nháp + báo một câu. Việc GHI luôn đọc lại 1 câu xác nhận trước khi tạo.

## Gửi nhắc nhở

Nhắc mỗi sáng được cron `jira-morning-reminder` (9:00 giờ VN) tự chạy. Để gửi
thủ công tới DM của Hoàng:

```
hermes send --to google_chat --subject "Task Jira hôm nay" "<nội dung>"
```

Hoặc gửi tới DM space cụ thể: `hermes send --to google_chat:spaces/AAQAZxc2km8 ...`

## Lưu ý / pitfall

Đã chuyển sang agentmemory lessons (context=`jira-daily-tasks`). Khi cần nhớ lại: gọi `memory_lesson_recall` query `jira-daily-tasks`.
