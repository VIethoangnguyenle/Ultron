# VBSME — kho STH (kho kết quả thu thập sinh trắc học): 4 cột hay bị hỏi "sao trống"

Tester hỏi kiểu *"thu thập mà không lưu ngày sinh / ngày cấp / nơi cấp / quốc tịch"* ⇒ gần như chắc chắn
là đang nhìn **màn hình kho STH**, tương ứng 4 cột của bảng kho STH:

| Cột kho STH | Tester gọi là | Nguồn dữ liệu |
|---|---|---|
| `DATE_OF_BIRTH_NFC` | ngày sinh | dữ liệu chip CCCD (NFC) |
| `NATION_NFC` | quốc tịch | dữ liệu chip CCCD (NFC) |
| `ISSUE_DATE_NFC` | ngày cấp | ngày cấp của hồ sơ thu thập |
| `ISSUE_PLACE_CARD` | nơi cấp | mặt thẻ (OCR), KHÔNG phải chip |

(`GENDER_NFC` = giới tính, `EXPIRE_DATE_CARD` = hạn thẻ; CCCD24 thường trống `ISSUE_DATE_NFC` vì chip
gắn mới không chứa ngày cấp.)

## Ai ghi 4 cột này

- Bản ghi kho STH do **internal-service** ghi ở bước *cập nhật trạng thái sinh trắc học*
  (`updateStatusBiometric`) — không phải bước `collect/nfc`.
- Bản code mới (xem `vietbank-digital/viet-bank-omni-ekyc/.../UpdateStatusBiometricHandler`): build model kho
  STH rồi `.dateOfBirthNfc(...) .genderNfc(...) .nationNfc(...) .issueDateNfc(...) .issuePlaceCard(...)`.
- Bản SME trong workspace `vietbank-sme/` **KHÔNG** set 5 trường này (`SuccessCollectModel` thậm chí
  không có field) ⇒ nếu môi trường đang chạy bản này thì 4 cột **luôn trống**, không phải mất dữ liệu.

## Cách phân biệt bản cũ / bản mới CHỈ BẰNG LOG internal-service

Đọc thứ tự `step` trong cùng 1 request `updateStatusBiometric`:

- **Bản cũ (không ghi 4 trường):** step 1 = `not have success collect model`,
  step 2 = `Update Request Collect for RequestID: ...`
- **Bản mới (có ghi 4 trường):** đảo lại — `Update Request Collect...` trước, rồi mới tới
  `not have success collect model` / `Get Success Collect for Cif ...`.

⇒ Thấy step 1 = "not have success collect model" ở môi trường nào thì môi trường đó chạy bản cũ.

## Bẫy môi trường (nhớ kỹ)

- Cổng log UAT `https://10.22.17.219:10443/omni-sme/` là **môi trường khác** với các DB đọc được qua
  db-access (`VBSMEEKYC`, `VBEKYCSTORAGE`, …). Kiểm chứng: `REQUEST_ID`/`requestId` lấy từ log KHÔNG
  tồn tại trong `VBSMEEKYC.REQUEST_COLLECT` ⇒ **đừng hứa đối chiếu DB của môi trường log**; chỉ kết luận
  từ log + code, và ghi rõ giới hạn này vào mục 7 của báo cáo.
- Log pod ekyc-appserver có thể đứng im vài ngày (vd chỉ ghi tới 14/09) trong khi các service khác vẫn
  nhảy giây — kiểm tra mtime autoindex của vài service để biết cổng log còn sống, rồi mới kết luận
  "hôm nay không có request nào".

## Bẫy nghiệp vụ đã gặp: "nơi cấp" bị lấy từ quê quán trên chip

`ekyc-appserver` (collect/nfc) ghi đè nơi cấp bằng giá trị **quê quán đọc trên chip** rồi mới chuẩn hoá:
chỉ nhận diện được 2 giá trị chuẩn (`CỤC CẢNH SÁT…TTXH` / `…VDC`), còn lại để nguyên chuỗi gốc và log
`reject issuePlace: <giá trị>`. Với ca có quê quán dạng địa chỉ (vd `Phường 12, Quận 8, TP.Hồ Chí Minh`)
⇒ "nơi cấp" sẽ mang địa chỉ quê quán thay vì tên cơ quan cấp in trên thẻ. Khi báo cáo nhớ tách riêng
2 vấn đề: (1) cột trống vì bản build, (2) nơi cấp sai nguồn.
