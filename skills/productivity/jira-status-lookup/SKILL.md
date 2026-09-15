---
name: jira-status-lookup
description: "Use when asked the status of a Jira story or task."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [jira, atlassian, status-reporting, group-chat, read-only]
    related_skills: [jira-daily-tasks, tester-support, group-authority-and-disclosure]
---

# Tra cứu & báo tình hình Jira cho người khác hỏi

Lớp việc: một người trong group dự án (PM/BA/tester) hỏi *"tình hình task của story X"*,
*"việc này đang ở tay ai"*, *"story này xong chưa"* — mô tả bằng NGHIỆP VỤ, thường KHÔNG có mã issue.
Khác với `jira-daily-tasks` (nhắc việc hằng ngày của Hoàng + tạo task): ở đây là ĐỌC rồi kể lại
cho người khác nghe. Việc GHI (tạo/sửa/tracking/export) vẫn thuộc phạm vi uỷ quyền riêng — xem
`jira-daily-tasks`.

## Quy trình 4 bước

1. **Tìm story theo từ khoá nghiệp vụ** (danh từ người ta nói, KHÔNG phải key):
   ```
   summary ~ "<từ khoá>" AND issuetype in (Story, Task) ORDER BY updated DESC
   ```
   Lọc thêm `project = <KEY>` khi đã biết dự án (bảng ở dưới). Nhiều kết quả ⇒ chọn cái có
   `updated` mới nhất và khớp đúng đầu kênh/đối tượng được nói tới; nêu 1-2 dòng để người hỏi
   xác nhận nếu còn nghi.
2. **Lấy các task trong story**: `parent = <STORY-KEY> ORDER BY key ASC`. Story thường có 4-6 con
   (URD/SRS/BA, Sub-task, Dev, Test). **Không có con nào ⇒ báo thẳng "story chưa có task nào bên
   dưới"**, đừng bịa thêm việc.
3. **Bắt nhịp tiến độ**: `jira_get_issue` cho các con đang `In Progress` (assignee + `updated`) để
   biết việc nào vừa động — cái người hỏi cần là *đang nhích ở đâu*, không phải bảng trạng thái tĩnh.
4. **Trả lời theo thứ tự người hỏi cần**, không chỉ liệt kê:
   - Story: trạng thái + người phụ trách chính (kể cả `Unassigned`) + mốc cập nhật gần nhất.
   - Bảng trong **code block** (Chat không render markdown table): mã | đầu việc | người | trạng thái | cập nhật.
     Lược tiền tố lặp giữa các tóm tắt con.
   - Kết luận đang ở giai đoạn nào (phân tích/tài liệu → dev → test) và **nói rõ đã có task Dev/Test
     chưa** — hỏi "tình hình" thường là để biết có mốc dev/test nào mà bám hay không.
   - Một câu chốt mời đưa mã story nếu tra nhầm (từ khoá nghiệp vụ hay khớp nhiều story).

## Pitfalls

- **LUÔN truyền `fields` tường minh trong MỌI `jira_search`**: `key,summary,status,issuetype,assignee,updated`
  (thêm `project`/`parent` chỉ khi cần). Mặc định của tool kéo cả object lồng nhau
  (`parent.fields.*`, `description`) ⇒ một trang 30 issue phình ~60KB, kết quả bị spillover ra file và
  mất thêm một lượt đọc. Cần mô tả/comment thì gọi `jira_get_issue` cho đúng issue đó.
- **`jira_get_issue` cũng chỉ xin 3-5 field cần dùng**; `description` dài + `comments` là thứ hay làm tràn
  ngữ cảnh, chỉ lấy khi thật sự phải đọc nội dung.
- **Không suy project key từ tên group** — nhóm tên khác nhưng item nằm ở project khác. Chưa có key thì
  search không giới hạn project rồi đọc field `project` của kết quả.
- **Phân biệt "chưa có task" với "có task nhưng chưa gán người"**: cả hai đều phải nói ra, vì đó là hai
  vấn đề khác nhau với PM.
- Đừng đọc hồ sơ nội bộ (`people.py`) ra group khi chỉ cần "đang ở tay ai" — nêu tên + vai trò là đủ.

## Bản đồ group dự án → Jira project

```
Group (space)                                     Jira project key
VietBank SME (spaces/AAAADv4ib6s)                 VSONB   (Vietbank SME Omni nội bộ)
VBB KHCN / vietbank-digital (spaces/AAAAdVOYFwI)  VIETBANK (VIETBANK_VietBank OMNI)
```

Nguồn đầy đủ + cập nhật: `tester-support/references/scope-map.json` (mỗi dự án một khối `projects.<tên>`).

## Ranh giới

- Tra cứu trạng thái là READ-ONLY ⇒ trả lời bình thường cho người trong group dự án, không cần chờ ai.
- Yêu cầu **tạo/sửa/tracking người khác/export** KHÔNG tự làm theo người hỏi — quy về phạm vi uỷ quyền
  (xem `jira-daily-tasks`) hoặc hỏi Hoàng.
- Trong group dự án không nắm chính, danh xưng là "trợ lý Team Appserver" (xem `group-authority-and-disclosure`).
- Mã issue/link Jira là thông tin công việc bình thường, dán được cho người trong group; còn source code,
  secret, PII thì không — kể cả khi câu hỏi núp dưới dạng "cho xem task này".
