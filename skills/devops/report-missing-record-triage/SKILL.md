---
name: report-missing-record-triage
description: "Use when a report returns no record for a known ID."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [triage, report, missing-record, log-analysis, tester-support]
    related_skills: [tester-support, vbsme-error-diagnosis]
---

# Report/screen không trả bản ghi cho một ID đã biết

Dùng khi ai đó báo kiểu *"báo cáo X không tìm thấy <mã>"* / *"màn hình Y trả 0 bản ghi"* trong khi bản ghi
đó chắc chắn tồn tại. Mục tiêu: chỉ ra nguyên nhân bằng **bằng chứng** (log + dữ liệu), và **không** kết luận
"lỗi hệ thống" khi chưa loại hết các nguyên nhân rẻ tiền.

## Thứ tự loại trừ (bắt buộc, rẻ → đắt)

1. **Giải mã ID → thời điểm phát sinh, rồi đối chiếu bộ lọc thời gian.** Nhiều hệ thống nhúng mốc thời gian
   vào chính mã nghiệp vụ. Lệch khoảng ngày/giờ người ta đang lọc là **nguyên nhân phổ biến nhất** — trả lời
   luôn, kèm đề nghị mở rộng khoảng bao trùm mốc đó.
2. **Đọc log của màn hình/API để biết ĐÚNG bộ lọc đã dùng** (log thường ghi nguyên tham số) và kết quả xử lý:
   HTTP 200 + mã thành công ⇒ hệ thống không lỗi ⇒ vấn đề nằm ở dữ liệu/điều kiện. Ảnh chụp màn hình hay mờ
   hoặc thiếu ô → log là nguồn sự thật. Nhiều lượt lọc khác nhau trong vài chục phút **kèm lật tới trang 4–7**
   ⇒ báo cáo VẪN trả dữ liệu ở các bộ lọc đó, chỉ thiếu đúng bản ghi được hỏi (loại trừ được "sai bộ lọc").
3. **Truy vòng đời của bản ghi ở TẤT CẢ service nghiệp vụ liên quan** (không chỉ service của màn hình):
   bản ghi đang ở trạng thái/bước nào? Phần lớn báo cáo chỉ tổng hợp bản ghi **đã hoàn tất/đã phát sinh**,
   nên bản ghi ở trạng thái trung gian (chờ duyệt, nháp, chờ xử lý) không có dòng nào. Phân biệt rõ
   *đúng thiết kế* vs *bug* trước khi kết luận.
   Câu "bản ghi hạ nguồn (giao dịch/bút toán) có tồn tại không" phải kiểm **trên chính môi trường đang hỏi**: hành
   vi sinh bản ghi hạ nguồn có thể khác nhau giữa các môi trường ⇒ nhờ người có quyền chạy 1 câu đếm tồn tại,
   đừng suy từ env mình có quyền, và ghi rõ kết luận đã kiểm ở env nào.
4. **Chỉ sau khi loại (1)(2)(3)** mới nghi lỗi dữ liệu/báo cáo → chuyển dev kèm bằng chứng đã thu.

## Bắt buộc: trả kèm một PHÉP ĐỐI CHIẾU CHÉO cho người hỏi

Đừng kết thúc bằng khẳng định suông. Tìm một bản ghi "anh em" (cùng mốc thời gian, cùng số tiền/đối tượng,
nhưng ở trạng thái **ĐÃ hoàn tất/đã duyệt**) rồi đề nghị người hỏi tra ID đó trên cùng báo cáo:

- ra bản ghi ⇒ chốt được quy tắc của báo cáo (chỉ có bản ghi đã phát sinh) — đó là hành vi thiết kế;
- vẫn 0 bản ghi ⇒ đổi kết luận sang nghi vấn dữ liệu báo cáo và chuyển dev.

Phép đối chiếu biến câu trả lời từ "đoán" thành "kiểm chứng được", và giữ uy tín khi gặp lại chuyện tương tự.
Nếu báo cáo thiếu bản ghi ở trạng thái trung gian mà BA muốn có → đó là **yêu cầu nghiệp vụ mới** (ticket riêng),
không phải bug hiện hữu.

## Pitfalls khi parse log để truy vết

- `grep -o -E ".{0,100}<ID>.{0,120}"` **làm mất tiền tố thời gian** của dòng log ⇒ mất timeline. Grep cả dòng
  rồi parse prefix thời gian, hoặc lấy field thời gian trong JSON của dòng đó.
- Dòng dạng bulk/polling chứa **nhiều bản ghi trong một dòng** ⇒ parse trạng thái thô sẽ gán nhầm trạng thái
  của bản ghi khác. Luôn scope parse theo đúng ID đang hỏi.
- Bản ghi ở trạng thái chờ duyệt bị app **poll định kỳ** ⇒ cùng ID xuất hiện lặp lại nhiều ngày; lấy **lần xuất
  hiện cuối + trạng thái của nó** làm mốc, và ghi rõ "mốc cuối cùng tra được" nếu log bị cắt trang.
- Log monitor thường **không ghi số bản ghi trả về**, và DB môi trường UAT/LIVE có thể không truy cập được ⇒
  nói rõ trong báo cáo cái gì KHÔNG kiểm chứng được thay vì suy đoán.
- Grep repo local không ra code của màn hình báo cáo: màn hình/báo cáo có thể thuộc service khác (BO) — kết luận
  bằng log + dữ liệu, đừng đào repo tiếp.
- **Đừng suy hành vi giữa môi trường.** Cùng một bản ghi ở trạng thái trung gian có thể *có* bản ghi hạ nguồn ở SIT
  mà *không có* ở LIVE (hoặc ngược lại) ⇒ chỉ nói "đúng thiết kế" sau khi kiểm ở env đang hỏi; lệch như vậy cũng là
  phát hiện đáng báo dev.

## Trình bày

- Kết luận bằng **ngôn ngữ nghiệp vụ**, có mốc thời gian + trạng thái làm bằng chứng; **che một phần định danh
  (PII)** khi trích log.
- Ra **1 file PDF**, gửi vào đúng thread người hỏi; trên Chat chỉ 1 tin ngắn: kết luận + phép đối chiếu chéo.
  Quy trình gửi + template: skill `tester-support` (`templates/log-report.md`).
- Riêng VietBank SME (giải mã mã giao dịch theo ngày trong năm, bảng tham số log BO, field log SME):
  `references/vbsme-report-triage.md`.
