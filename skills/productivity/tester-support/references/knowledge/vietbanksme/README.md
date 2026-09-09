# KB bổ sung — vietbanksme

Kiến thức bổ sung cho dự án vietbanksme mà **graph + log không nói được**.
Graph (domain-graph.json + knowledge-graph.json) là nguồn CHÍNH — đừng ghi vào đây
những gì graph đã chứa (nghiệp vụ/flow/code).

## Các file (tạo dần khi Hoàng dạy)

- `error-codes.md`  — giải thích mã lỗi: mã là gì, vì sao bị, xử lý ra sao
- `test-env.md`     — môi trường test, account, data mẫu, cách dựng data test
- `known-issues.md` — bug đã biết, limitation, workaround
- `business-rules.md` — luật nghiệp vụ mà graph chưa tóm được

## Quy tắc ghi

- Hoàng luôn nói rõ dự án nào khi dạy. Không rõ → hỏi lại.
- Mỗi mẩu kiến thức ghi đúng 1 file theo chủ đề, ngắn gọn, có cấu trúc.
- Không chứa secret/credential/account thật (nếu có, chỉ lưu pattern/placeholder).
