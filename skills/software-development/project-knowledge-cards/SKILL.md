---
name: project-knowledge-cards
description: Use when a business question was already traced.
---

# Thẻ nghiệp vụ dự án — trả lời câu đã phân tích mà không trace lại

Mỗi câu hỏi nghiệp vụ đã trace một lần thì **ghi lại thành thẻ có hạn dùng**; lần sau tra thẻ trước,
chỉ trace phần đã lệch. Áp cho dự án có source lớn (vbsme trước tiên).

## Chỗ lưu (per dự án)
```
<workspace>/docs/knowledge/
  README.md          cơ chế
  registry.json      mục lục: id -> file thẻ; repos + gate_ref
  cards/<id>.json    thẻ
```
Prototype đầu: `/home/zane/Desktop/work/vietbank/vietbank-sme/docs/knowledge` (3 thẻ: payroll-batch,
etag-cache, napas247-recon).

## Cấu trúc thẻ (JSON)
`id`, `title`, `kind` (business-flow | mechanism), `aliases[]`, `questions_answered[]`,
`conclusion{summary, steps[], api_paths[], error_codes, where_to_look_next[]}`, `traps[]`,
`evidence[{file, ref, last_commit | sha256_prefix, proves}]`, `gate_ref`, `confidence`, `gaps[]`,
`verified_at`, `verified_by`.

## Vai trò của thẻ (Hoàng chốt 15/09) — CONTEXT KHỞI ĐẦU, không phải kết luận cuối
Mục đích của thẻ là cho Ultron **đúng ngữ cảnh vấn đề ngay từ đầu** để tăng tốc trace: biết ngay vùng/file/
API liên quan, bẫy đã gặp, phần còn thiếu — thay vì mò cả repo. Vì vậy:
- Thẻ **không thay** việc kiểm chứng. Chuẩn cao nhất là **chính xác + chuẩn nghiệp vụ**: mã lỗi, trạng thái,
  luồng, điều kiện phải khớp thực tế.
- Câu hỏi cần độ chính xác cao (trả lời tester/khách, trước khi sửa code, bàn giao) ⇒ dùng thẻ để **đọc đúng
  1-2 file bằng chứng và verify lại** rồi mới kết luận — vẫn nhanh hơn nhiều lần so với trace mò.
- Câu hỏi thường, đúng phạm vi thẻ, thẻ còn hạn ⇒ trả lời từ thẻ nhưng **nói rõ mốc (nhánh + commit)**,
  `confidence`, và phần `gaps`.
- Đọc thẻ xong mà thấy mâu thuẫn với hiểu biết hiện tại ⇒ trace thật, **không bẻ kết luận cho khớp thẻ**.

## Quy trình 4 bước khi được hỏi
1. **Tra**: khớp `aliases` của thẻ với câu hỏi (không phân biệt hoa/thường, khớp theo từ).
2. **Đọc thẻ = lấy context**: xác định vùng/file/API cần kiểm, bẫy, `gaps`; đối chiếu với câu hỏi. Cần độ
   chính xác cao ⇒ verify lại file bằng chứng rồi mới kết luận; luôn nói rõ mốc + `confidence` + `gaps`.
3. **Kiểm hạn (BẮT BUỘC)**: mỗi `evidence` có `last_commit` phải khớp
   `git -C <repo> log -1 --format=%H origin/dev-sit -- <file>`; file ngoài git so `sha256sum`.
   Lệch ⇒ `git diff <last_commit>..origin/dev-sit -- <file>`, trace lại **chỉ file đó** rồi cập nhật thẻ.
4. **Ghi thẻ**: sau mỗi lần trace đầy đủ, viết/cập nhật thẻ ngay (chi phí gần 0). Thẻ mới ⇒ thêm 1 dòng registry.

## Luật cứng (đã trả giá để biết)
- **Cổng kiểm hạn là bắt buộc.** Trả lời từ thẻ không kiểm hạn = trí nhớ không hạn dùng ⇒ sai mà không ai biết.
- **Kiểm hạn phải theo REF, không theo bản checkout.** Đo 15/09: 3/7 file bằng chứng lệch giữa bản local và
  `origin/dev-sit` (app payroll controller, ETagType, failure consumer) ⇒ gate bằng local là "FRESH" giả.
- **alias chỉ giữ ở MỘT chỗ — trong thẻ.** registry giữ bản sao aliases thì sẽ lệch (đã xảy ra: thẻ có alias mới,
  registry cũ ⇒ tra hụt). registry chỉ giữ id/file/title.
- **Alias phải thu từ câu hỏi thật** (cách tester/dev diễn đạt), không tự nghĩ ra; câu diễn đạt lạ vẫn trượt ⇒
  bổ sung alias sau mỗi lần trượt.
- **API path không lấy từ graph UA** — graph hay sai thứ tự đoạn path; thẻ ghi path đã chốt bằng source
  (xem skill `ua-source-trace`).
- **Nói rõ mốc**: thẻ ghi nhánh/ref + commit; câu trả lời kèm mốc.
- Thẻ `confidence: medium` phải nói rõ cho người hỏi; phần `gaps` chưa gom thì vẫn phải trace như thường.

## Công cụ đã có (không tự viết lại — dùng cái này)
- `python3 ~/.hermes/scripts/bizcard.py list | find "<câu hỏi>" | check [--fetch] [--quiet] | verify <id> | stamp <id>`
  - `find` khớp alias → in kết luận + cổng 2 tầng; MISS ⇒ exit 3, phải trace thường.
  - `check` exit 1 = có lệch cứng (KHÔNG dùng thẻ làm kết luận); `--quiet` im khi sạch.
  - `stamp <id>` chỉ cập nhật vân tay + `verified_at` sau khi đã verify tay, KHÔNG sửa nội dung thẻ.
- `~/.hermes/scripts/bizcard_gate.py` (chỉ nhắn DM khi có việc, chống lặp 1 tin/ngày) gắn ở
  `schedules.yaml` action `bizcard-gate` — 08:00 mỗi ngày, 0 token.

## Pitfalls đã đo được
- Tín hiệu `fix|bugfix|hotfix` bắt thừa cả `prefix`/`suffix` ⇒ chỉ dùng để *cảnh báo*, exit code
  tầng mềm vẫn 0.
- Khớp alias **không bỏ dấu** (cố ý) ⇒ câu gõ không dấu sẽ MISS; phải gom alias không dấu từ chính
  cách tester/dev hay gõ.
- Tầng cứng một mình là **không đủ**: đã gặp thẻ báo 0/4 file lệch nhưng vùng theo dõi có 5 commit
  sau ngày chốt — nếu chỉ so file bằng chứng thì trả lời với vẻ rất chắc chắn trong khi nền đã đổi.

## Cổng 2 tầng + theo dõi chủ động (phát hiện "tuần đó có người fix")
- Mỗi thẻ khai `watch_paths[]` = **vùng nghiệp vụ** (module/thư mục), không chỉ file bằng chứng.
- **Tầng cứng**: file bằng chứng đổi SHA ⇒ thẻ sai chắc chắn, phải trace lại.
- **Tầng mềm**: `git log --since=<ngày tạo thẻ> origin/dev-sit -- <watch_paths>`; có commit ⇒ đánh dấu
  "cần rà" và in kèm ai/ngày/nội dung; commit `fix|bugfix` ⇒ rà ngay.
- **Chủ động**: `git fetch origin dev-sit` chạy được từ máy này (kiểm chứng 15/09) ⇒ cron 0 token
  fetch + in báo cáo thẻ nào lệch, kể cả khi không ai hỏi.
- **Giới hạn**: fix ở repo khác (dvnh-common, vietbank-digital), migration/DB/feature flag ⇒ tầng này
  không thấy. Vì vậy câu trả lời luôn kèm mốc (nhánh + commit) và cảnh báo khi vùng vừa có commit sau ngày chốt.

## Số đo (15/09, câu "luồng chi lương hàng loạt")
| Đường | Chi phí |
|---|---|
| Grep thuần | 1.026.483 token / 23 lượt |
| Lai UA + grep chốt | 204.636 token / 6 lượt |
| Thẻ + cổng kiểm hạn | ~2.200 token / 2 lượt (tra + đọc), 0 gọi MCP |

## Khi nào KHÔNG dùng thẻ
Câu hỏi mới; câu về phần đã lệch; cần bằng chứng cho quyết định quan trọng (sửa code, bàn giao, kết luận
cho khách) ⇒ trace thật, rồi cập nhật thẻ.
