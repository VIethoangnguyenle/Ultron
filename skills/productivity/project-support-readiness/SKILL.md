---
name: project-support-readiness
description: "Use when chấm độ sẵn sàng support group dự án mới."
version: 0.1.0
author: Ultron
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [readiness, project-onboarding, knowledge-graph, tester-support]
    related_skills: [tester-support, ua-source-trace, project-knowledge-cards, team-people]
---

# Đủ điều kiện support một group/dự án mới chưa?

## Khi dùng
- Hoàng hỏi "em đã đủ ngữ cảnh / kiến thức để support group <dự án> chưa?"
- Trước khi nhận việc đầu tiên trong một group dự án mới (tester/dev bắt đầu hỏi).

Nguyên tắc gốc: **trả lời bằng SỐ ĐO THẬT, không bằng cảm giác** — mỗi mục "đủ/thiếu" phải có lệnh kiểm
đứng sau. Không bao giờ chốt "chắc là đủ".

## 6 mục kiểm (thiếu mục nào thì câu hỏi thuộc mục đó phải hỏi lại Hoàng)

| # | Mục | Cách kiểm | Đủ là khi |
|---|---|---|---|
| 1 | Graph đã nạp | MCP `understand_anything` → `list_projects` | thấy project, `Coverage` OK, có Layers/Domains |
| 1b | Mô tả đã việt hoá | đọc `<root>/.ua/knowledge-graph.json` + `domain-graph.json`, unwrap `['nodes']`, đếm `summary` rỗng và đếm còn tiếng Anh (regex dấu tiếng Việt) | rỗng = 0, tiếng Anh = 0 |
| 2 | Entry trong scope-map | `~/.hermes/skills/productivity/tester-support/references/scope-map.json` | có `spaces[]`, `graph_source`, `error_code_source`, `log_source`, `db_source`, `kb_dir` |
| 3 | Nguồn mã lỗi | theo `error_code_source` | có bảng mã lỗi trong DB, HOẶC có từ điển mã lỗi trích từ code |
| 4 | Thẻ nghiệp vụ | `python3 ~/.hermes/scripts/bizcard.py list` | có ≥1 thẻ của dự án đó |
| 5 | Mốc phiên bản | `cat <root>/.ua/meta.json` | `gitCommitHash` là hash thật, KHÔNG phải `not-a-git-repo` |
| 6 | Tư cách thành viên | `grep -rhoE 'spaces/[A-Za-z0-9_-]+' ~/.hermes/logs/gateway.log \| sort \| uniq -c \| sort -rn` rồi `python3 ~/.hermes/scripts/gchat_members.py --space spaces/XXX` | có space ID của group + biết ai trong đó |

## Bẫy khi kiểm (đã trả giá)
- **Graph JSON phải unwrap trước khi lặp**: `knowledge-graph.json` / `domain-graph.json` top-level là OBJECT
  `{version, project, nodes, edges, tour, layers}` (bản cũ có thể là list) ⇒ lấy `d['nodes']`. Lặp thẳng
  top-level khi nó là object là lặp ra KEY (chuỗi) → `AttributeError: 'str' object has no attribute 'get'`.
- **`gitCommitHash: not-a-git-repo` ⇒ graph KHÔNG có mốc.** Hệ quả phải nói rõ: không phát hiện được khi dev
  sửa code làm câu trả lời cũ lệch ⇒ mọi câu trả lời phải kèm cảnh báo độ mới UNKNOWN.
- **Không mượn nguồn của dự án khác.** Link log, bảng mã lỗi, DB list là PER-PROJECT; dự án mới chưa khai thì
  dừng và hỏi Hoàng, tuyệt đối không thử link/bảng của dự án đã có để "đoán".
- **Mã lỗi không phải lúc nào cũng nằm trong DB.** Có dự án để mã lỗi rải trong code theo từng service
  (enum/hằng số) chứ không có bảng tập trung ⇒ mục 3 khi đó = phải tự dựng từ điển mã lỗi từ code TRƯỚC khi
  nhận câu hỏi mã lỗi.
- **Chưa được add vào group thì chưa tính là support được**: không có space ID ⇒ không biết ai trong group,
  không gọi đúng người khi cần, và cũng không nhận được câu hỏi nào.

## Phân loại kết quả (cái gì tự làm, cái gì phải hỏi Hoàng)
- **Tự làm**: khai entry scope-map (khi đã đủ thông tin), dựng từ điển mã lỗi từ code, mở thẻ nghiệp vụ
  (skill `project-knowledge-cards`), kéo commit mốc nếu repo có remote.
- **Phải hỏi Hoàng** (không suy diễn): log của dự án xem ở đâu · mã lỗi tra ở đâu (bảng DB hay chỉ trong code)
  · DB nào dùng cho SIT và tester có cần ghi không · add Ultron vào group / cấp space ID.

## Cách trình bày khi Hoàng hỏi "đã đủ chưa"
1. Mở bằng kết luận thẳng (vd "chưa đủ — được ~7/10"), không rào đón.
2. "Đã có" kèm **số đo thật** (số node/cạnh, coverage, số domain/flow, % mô tả tiếng Việt) — không nói
   "đã xong" chung chung.
3. "Còn thiếu" dạng **bảng bọc code block** (Chat không render markdown table): thiếu gì ↔ vì sao chưa
   support được.
4. Tách rõ **việc thuộc Hoàng** và **việc em tự làm**.
5. Chốt 2 dòng: "hiện trả lời được gì — chưa gì" (vd luồng nghiệp vụ/kiến trúc: được; mã lỗi/log/DB: chưa).

## Chấm điểm mẫu (kiểm lại bằng bảng trên trước khi dùng)
- **vietbanksme** — đủ 6 mục: scope-map đầy đủ, mã lỗi `AD_MESSAGE`, log portal UAT/LIVE, DB SIT, 3 thẻ.
- **vietbank-digital** (vietbank-omni + viet-bank-omni-ekyc + dvnh-common) — mục 1/1b ĐỦ (~15k node /
  ~31k cạnh / coverage 97% / ~147 domain, mô tả 100% tiếng Việt); mục 2–6 THIẾU: chưa có entry scope-map
  (thiếu nguồn mã lỗi + log + DB + kb_dir), chưa có thẻ nghiệp vụ, `meta.json` ghi `not-a-git-repo`,
  Ultron chưa nằm trong group nào của dự án ⇒ chưa có space ID. Khác biệt nghiệp vụ: mã lỗi digital nằm rải
  trong code theo từng service, KHÔNG có bảng tập trung kiểu `AD_MESSAGE` như VBSME.

## Verification
- Mỗi mục "đã có"/"còn thiếu" phải trỏ được về một output tool thật trong lượt đó.
- Trước khi nói "chưa có space": đã grep `spaces/` trong `gateway.log` để chắc group không tồn tại.
- Trước khi nói "graph xong": đếm lại `summary` rỗng + còn-tiếng-Anh trên chính file graph hiện tại
  (không tin file progress, không tin exit code của job build).
