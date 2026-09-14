---
name: config-driven-behaviour-triage
description: "Use when a config limit or flag did not fire."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [config, ad-config, limit, threshold, root-cause, vbsme, dvnh]
    related_skills: [vbsme-error-diagnosis, vbsme-db-lookup, vbsme-flow-explainer]
---

# Config-driven behaviour triage ("config là X mà sao không chặn / sao không lỗi?")

Dùng khi ai đó (dev hoặc tester) nói một ngưỡng/cờ/rule trong config **không có tác dụng**: limit không chặn,
flag không ăn, thời gian tối đa không nổ lỗi, giá trị đổi rồi mà hành vi y nguyên.

**Nguyên tắc:** đừng kết luận "không phải bug" từ việc đọc giá trị config trong DB. Giá trị đọc được ≠
giá trị instance đang chạy ≠ giá trị nhánh code đang thực thi. Loại hết 4 lớp dưới rồi mới kết luận.

## 4 lớp phải loại (theo thứ tự)

1. **Ngữ nghĩa so sánh** — đọc đúng dòng `if`: operator là `>` hay `>=`? Đơn vị so là gì (ngày / tháng /
số bản ghi / số tiền)? Input thực tế bằng bao nhiêu? **Tính bằng tool, không nhẩm** (vd `|DAYS.between(from, to)|`
giữa 2 mốc ngày). Strict `>` ⇒ input đúng bằng ngưỡng KHÔNG bị chặn — đây là hành vi hiện tại, không phải bug;
muốn chặn biên thì phải `>=` hoặc hạ ngưỡng 1.
2. **Đúng key chưa** — một limit nghiệp vụ thường có NHIỀU key anh em, giá trị khác nhau giữa key và giữa env.
Query hết theo prefix trước khi kết luận:
`SELECT CODE, VALUE, IS_ACTIVE, STATUS FROM <SCHEMA>.AD_CONFIG WHERE CODE LIKE '%<từ khoá>%' ORDER BY CODE`.
Check cả `IS_ACTIVE` (0 = row tắt) và `STATUS` (row chưa confirm cũng đổi hành vi âm thầm).
3. **Giá trị đang CHẠY** — config thường được cache local theo từng instance, SQL edit trực tiếp KHÔNG có hiệu lực
ngay và các instance lệch nhau. Xem `references/ad-config-cache.md` cho cơ chế AD_CONFIG (TTL, reload Kafka).
4. **Request có vào nhánh đó không** — cùng một chủ đề thường có nhiều handler/biến thể (tra cứu thường vs HBK vs POS;
export vs export_v2 dùng chung prefix path). Vào nhánh khác thì gate không chạy, config đúng cũng vô nghĩa.
Xác định handler theo endpoint mà client thực gọi, không theo tên màn hình.

## Recipe bisect biên (tự xác minh, không cần log)

Gọi đúng API/UI đó với 3 mốc:

1. **Đúng bằng ngưỡng** và **ngưỡng + 1** → phân biệt `>` với `>=`.
2. **Vượt xa** (vd 400 ngày / 10.000 bản ghi): vẫn OK ⇒ gate không chạy (sai nhánh) **hoặc** giá trị runtime
   lớn hơn rất nhiều so với giá trị đọc trong DB.
3. Kết quả khớp "ngưỡng + 1" nhưng lệch giá trị đọc trong DB ⇒ **cache chưa hết TTL / sai env**.

Log là bằng chứng tốt nhất khi gate nổ: dòng TRACING thường in luôn **giá trị runtime**
(dạng `Exceed max duration %d days for ... DaysDiff: %d`) — đọc số ở đó là biết instance đang dùng config nào.

## Shape câu trả lời (bắt buộc)

- Trả lời **theo lớp**, mỗi lớp 1–2 câu + **cách tự kiểm ở lớp đó**, thay vì khẳng định suông.
- Luôn kèm recipe bisect biên để người hỏi tự xác minh trong ~1 phút.
- Kết bằng **một** câu hỏi chốt (env nào / giá trị đọc từ đâu / đã reload chưa) hoặc đề nghị soi log nếu
  có requestId + khoảng thời gian. Không hỏi dồn nhiều câu.
- Câu hỏi này thường đến từ dev (nhóm nội bộ) ⇒ được phép nêu endpoint/handler/tên config; với tester thì
  giải thích nghiệp vụ + gửi PDF.

## References

- `references/ad-config-cache.md` — cơ chế cache + reload của AD_CONFIG (dvnh-common / vbsme), và ví dụ
  limit tra cứu lịch sử giao dịch đã kiểm (3 key anh em, đơn vị NGÀY, so sánh strict `>`, dòng log mang giá trị runtime).
