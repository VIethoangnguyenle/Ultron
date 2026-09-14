# VietBank SME — chi tiết riêng cho triage "báo cáo không tìm thấy GD"

Ví dụ đã gặp: *Báo cáo chi tiết GD chuyển khoản* (BO) lọc theo mã giao dịch SME trả 0 bản ghi.

## 1. Giải mã mã giao dịch SME (`TRACE_NO`)

`TRACE_NO` = **3 số prefix + ngày trong năm (DOY) + số tuần tự** ⇒ 6 ký tự đầu = `<prefix><DOY>`:

| Mã SME | Ngày tạo suy ra |
|---|---|
| `006236…` | ngày 236 → 24/08 |
| `006237…` | ngày 237 → 25/08 |
| `006254…` | ngày 254 → 11/09 |

- Suy ra được **ngày** (không có giờ). Đối chiếu ngay `fromDateStr/toDateStr` tester đang lọc.
- Prefix 3 số đầu khác nhau theo luồng/dịch vụ (thấy cả `006` và `016` cho cùng loại dịch vụ) — **đừng suy
  ý nghĩa prefix** khi chưa kiểm chứng bằng dữ liệu thật.
- `REF_NO` / `REF_THIRD_PARTY` = mã giao dịch phía core bank / đối tác (ô "Mã giao dịch core banking"), khác
  hẳn mã SME.

## 2. Bảng tham số log BO ↔ ô trên màn hình

Báo cáo trên BO gọi API báo cáo của backend (1 hop) → log BO ghi nguyên tham số ⇒ biết chính xác tester lọc gì:

| Tham số trong log BO | Ô trên màn hình |
|---|---|
| `responseCode` | Mã giao dịch SME |
| `refNo` | Mã giao dịch core banking |
| `branchCode` | Chi nhánh/PGD |
| `companyCifNo` | CIF doanh nghiệp |
| `createdCifNo` / `createdUserName` / `lastApprovedCifNo` / `lastApprovedUserName` | người tạo / người duyệt |
| `transactionStatus` | Trạng thái |
| `fromDateStr`, `toDateStr` (`yyyyMMddHHmmss`) | khoảng ngày |
| `pageNumber`, `pageSize` | phân trang |

## 3. Truy vòng đời lệnh trong log SME (UAT/LIVE)

- Lệnh nằm rải ở NHIỀU service pod: napas/transfer (tạo & gửi) + approval (bước duyệt) + worker.
  Chỉ đọc log màn báo cáo/BO là không đủ.
- Streaming grep để khỏi tải file vài chục MB: `curl -k -s -m 280 "<log_source>/<pod>.log" | grep -a "<trace_no>"`.
- Field hữu ích trong JSON: `trace_no`, `transactionId`, `status`, `currentStageLevel`/`maxStageLevel`,
  `current_vi_stage_name` (Soạn lệnh / Duyệt…), `company_cif_no`, `company_name`, `branchCode`, `username`,
  `amount`, `serviceCode`, `senderAccount`, `beneAccount`/`beneBankName`.
- Lệnh `PENDING_APPROVED` (`currentStageLevel=1/2`, "Soạn lệnh") = chưa phát sinh giao dịch ⇒ **không có dòng
  nào** trong báo cáo chi tiết GD chuyển khoản. Đó là hành vi thiết kế; muốn báo cáo gồm cả lệnh chờ duyệt/hủy
  thì là yêu cầu mới cho BA/dev.
- Cách tìm bản ghi "anh em" để đối chiếu chéo: cùng doanh nghiệp + cùng ngày + cùng số tiền + cùng tài khoản
  thụ hưởng, nhưng trạng thái đã duyệt (khách thường tạo lại lệnh thứ 2 sau khi lệnh đầu không duyệt).

## 4. Thứ tự loại trừ thực tế đã dùng

1. Sai khoảng ngày (ảnh chụp cho thấy lọc 01/07–01/08 trong khi lệnh tạo 24/08) → tự nó đủ ra 0 bản ghi.
2. Bộ lọc khớp (đúng CIF, đúng chi nhánh, khoảng ngày bao 24/08) mà vẫn 0 bản ghi → chuyển sang vòng đời lệnh.
3. Log SME: lệnh vẫn `PENDING_APPROVED` suốt 24→26/08 (poll lặp lại), chưa từng qua bước duyệt ⇒ chốt nguyên nhân.
4. Đưa tester tra mã lệnh "anh em" đã duyệt để xác nhận quy tắc báo cáo.
