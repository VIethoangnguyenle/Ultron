---
name: headless-agent-jobs
description: "Use when a long job runs on a headless coding agent."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [claude-code, codex, agy, delegation, quota, long-running, verification]
    related_skills: [claude-code, codex, agy-orchestration]
---

# Long jobs on headless agents

Dùng khi một việc lớn (build knowledge graph, index repo, refactor nhiều module, phân tích hàng nghìn file)
giao cho agent headless — `claude` (Jarvis), `codex`, `agy` (Matcha). Việc này KHÁC một lần code ngắn: nó
vượt hạn mức một phiên, nên cần chọn engine, hẹn chạy tiếp, và kiểm chứng kết quả trước khi báo xong.

## 1. Chọn engine theo HÌNH DẠNG hạn mức, không theo sở thích
- claude: hạn mức **cửa sổ phiên 5h**, reset trong ngày ⇒ dùng lại được trong ngày.
- codex: hạn mức **tháng** — cạn là cạn cả tháng, đừng coi là đường dự phòng gần.
- agy: hạn mức theo **nhóm model** (hiện chỉ `gemini-3.1-pro*` còn quota — Hoàng chốt).
⇒ Việc lớn = NHIỀU phiên. Nói trước "việc này cần vài phiên" thay vì hứa xong trong một lần, và đừng để
nhiều con cùng nhảy vào một thư mục kết quả.

## 2. Một writer cho một thư mục kết quả
Trước khi thả thêm một run: `ps -eo pid,etime,args | grep -E 'claude -p|codex exec|agy.real'`.
Đang có run trên cùng repo ⇒ KHÔNG thả run thứ hai (hai agent cùng ghi `.ua/`, `dist/`, cache là cách nhanh
nhất để hỏng artifact). Cách đúng: kill watcher cũ, hoặc đợi run hiện tại xong rồi nối tiếp.

## 3. Resume, đừng restart
Pipeline lớn thường để checkpoint (`tmp/`, `intermediate/`, cache). Prompt lần chạy sau PHẢI nói rõ
"đã có X dở dang — RESUME từ chỗ dở, KHÔNG làm lại từ đầu"; thiếu câu đó agent làm lại từ 0 và tốn quota
gấp nhiều lần. Chỉ xoá checkpoint khi đã xác minh nó hỏng, và backup trước khi xoá.

## 4. Tự động hoá việc chạy tiếp (đừng dựa vào trí nhớ)
Job vượt hạn mức ⇒ để vòng lặp nền: đợi mốc reset → chạy lại → bỏ qua đơn vị đã xong (file kết quả đã tồn tại)
→ lặp mỗi giờ → ghi log. Template: `templates/resume_loop.sh`. Thông báo bằng
`background=true, notify=true`; đừng hẹn suông rồi để người dùng tự nhớ.

## 5. Kiểm chứng ARTIFACT, không kiểm chứng sự tồn tại
`ls` ra file không có nghĩa là xong. Chạy script kiểm chứng (UA: `scripts/verify_ua_graph.py`) và đọc số liệu
thật: số đơn vị, độ phủ so với tổng nguồn, tỉ lệ nội dung template/máy móc, các mục phụ (tour / layer / mẫu).
Self-report của agent KHÔNG phải bằng chứng: nó có thể khai "đã sinh file" trong khi file rỗng hoặc nội dung
chỉ là boilerplate. Báo cáo ĐÚNG mức đạt — "cấu trúc xong, chất lượng mô tả còn yếu" tốt hơn "xong rồi".

## 6. Ghi lại khối lượng lớn: chia theo module
Một run viết lại toàn bộ artifact lớn (~10k mục) ⇒ **OOM-kill (exit 137)** giữa chừng, phần đã làm vẫn dở.
Chia theo đơn vị tự nhiên (module / thư mục cấp 1), mỗi lượt ≤ ~1.600 mục, chạy tuần tự; mỗi lượt:
backup artifact → prompt giới hạn phạm vi đúng module ("chỉ sửa field Y của node thuộc module Z; không đổi id,
không thêm/bớt mục") → **ghi ra file tạm rồi rename đè** (ghi trực tiếp dễ hỏng file chục MB).
Exit 137 là tín hiệu phải chia nhỏ hơn, không phải lỗi môi trường. Template: `templates/chunked_summary_loop.sh`.

## 7. Làm agent headless thực thi một skill/workflow
Slash command KHÔNG được expand trong print mode (`agy --print "/understand …"` → chỉ trả lời như chat, exit 0,
không sinh file, dù help có cờ ngụ ý ngược lại). Đường chạy được: bỏ slash command, thay bằng prompt
"ĐỌC file SKILL.md … RỒI THỰC THI workflow … bằng công cụ shell/node của bạn", kèm resume + "KHÔNG hỏi lại".
Prompt thật + biến thể cho từng engine: `references/agent-executes-skill.md`.
