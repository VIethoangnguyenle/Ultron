# eKYC — VietBank SME (ghi 15/09/2026)

## Nguồn
- Source: `vietbank-sme/viet-bank-ekyc-sme` (nhánh local `pilot_hotfix_13_08`, 591 file .java).
- Graph: node path `viet-bank-ekyc-sme/...` (vd `client_gateway/cg-base/...`: `BaseResponse`, `BaseVbgClient`).
- Log:
  - `https://10.22.17.219:10443/omni-sme/ekyc-appserver/` (mới nhất 06/03/2026 — file 655 KB, 875 dòng, 22 ERROR)
  - `https://10.22.17.219:10443/omni-sme/ekyc-facepay/` (mới nhất 22/08/2026 — chỉ log khởi động, 6,3 KB)
- DB: `VBSMEEKYC` (read-only, 25 bảng: `CUSTOMER_EKYC`, `MESSAGE_EKYC`, `EKYC_ERROR`, `CARD_INFO*`,
  `HTE_REQUEST_FACE_PAY`, `CIF_BYPASS_EKYC`, `FACEPAY_FAILED_INTERVALS`, …) + `VBEKYCSTORAGE` (dùng chung 2 dự án).

## Mã lỗi eKYC
- Bảng riêng: `VBSMEEKYC.MESSAGE_EKYC` (112 dòng) và `VBSMEEKYC.EKYC_ERROR`.
- **KHÔNG** nằm trong `AD_MESSAGE` (bảng mã lỗi chung của SME) ⇒ hỏi mã lỗi eKYC thì tra bảng eKYC.

## Trace log — ví dụ thật
```
[2026-03-05 16:59:08.863] - [VBB860820598508754] [] [POST:/api/v1/ekyc/collect/nfc] Config app fwd to wfm: ...
```
requestId dạng `VBB…` (không có `OMNI`), app `EkycAppserverApplication` / `FacePayApplication`, profile có tiền tố `ekyc-`.

## Phân biệt với Digital (bắt buộc kiểm trước khi kết luận)
- Tên file log eKYC **giống nhau** ở 2 dự án (`ekyc-appserver-*`, `ekyc-facepay-*`) ⇒ KHÔNG dùng tên file.
- Phân biệt bằng: đường dẫn portal (`/omni-sme/`), tiền tố requestId (`VBB…`), tên profile (`ekyc-database-config`…).

## Hạn chế
- Log eKYC hiện là bản cũ; testers hỏi sự cố mới mà không có log ⇒ báo không có log, không suy diễn từ file cũ.
