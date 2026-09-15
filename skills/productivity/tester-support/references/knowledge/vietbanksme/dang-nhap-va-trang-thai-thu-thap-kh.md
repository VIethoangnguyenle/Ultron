# Đăng nhập ↔ trạng thái thu thập thông tin KH (vietbanksme) — ghi 15/09/2026

Doc đầy đủ (đã gửi group VBB SME): `vietbank-sme/docs/flows/dang-nhap-trang-thai-thu-thap-kh-flow.md` (+ .pdf).

## Chốt nghiệp vụ
- Login (App `POST /api/v1/app/auth/login`, Web/IB `POST /api/v1/web/auth/login`) — dùng CHUNG 1 luồng xử lý ⇒ luật thu thập áp cho cả 2 kênh.
- Ngay sau khi mật khẩu hợp lệ, hệ thống check giấy tờ của CHÍNH người đăng nhập: `OMNI_CUSTOMER.EXPIRED_DATE` trống hoặc đã qua ⇒ chặn (100042 nếu là đại diện, 100041 nếu nhân viên thường).
- Trạng thái thu thập đã = "đã thu thập" ⇒ bỏ qua bước đối chiếu eKYC.
- Chưa thu thập/chưa xác định ⇒ gọi eKYC Internal theo CIF (`checkExistingCustomer`), thứ tự tra: (1) kho mới `VBSMEEKYC.CUSTOMER_EKYC` — CÓ bản ghi ⇒ trả ERROR-CUSTOMER-EXISTS **không kèm kênh** (proto default = MB) ⇒ SME coi là DONE_COLLECT, tự đồng bộ, KHÔNG bắt thu thập lại; (2) kho mới trống, `VBEKYCSTORAGE.SUCCESS_COLLECT` CÓ bản ghi ⇒ trả EXISTS + **kênh thật** (thêm 1 dòng vào kho mới) ⇒ kênh `SME` ⇒ ép NOT_COLLECT = BẮT thu thập lại; kênh khác (OMNI/OLD_TELLER/EKYC_PLUS/VNEID_ONBOARD) ⇒ DONE_COLLECT; (3) cả 2 kho trống ⇒ NOT_COLLECT.
- Chỉ NGƯỜI ĐẠI DIỆN (REPRESENT=1) chưa thu thập mới nhận `nextStep = REQUIRE_COLLECT` (login vẫn thành công) → app mở luồng thu thập. Nhân viên thường không bị đẩy sang thu thập (chỉ chặn nếu giấy tờ hết hạn).
- Check tiếp các người đại diện khác của công ty: công ty không có đại diện → 100040; đại diện giấy tờ hết hạn → 100042; đại diện chưa thu thập → 100043 (kèm hotline).
- Luồng thu thập: `POST /api/v1/app/onboard/collect/status` → `POST /api/v1/app/onboard/collect/confirm` (kiểm tra token eKYC, đối chiếu CIF/tên/DOB/số giấy tờ, verify chip, update sinh trắc học sang eKYC) ⇒ ghi `STATUS_COLLECTED=2` + `EXPIRED_DATE` = ngày hết hạn giấy tờ (không thời hạn ⇒ 01/01/2999; cột `EXPIRE_DATE_COLLECTED` KHÔNG dùng, luôn rỗng).
- Cảnh báo gần hết hạn giấy tờ (KHÔNG chặn): API `POST /api/v1/app/auth/warnings`; message 100049 = NEARLY_EXPIRED_DATE_COLLECTED.

## Mã lỗi liên quan
- 100041 EXPIRED_DATE_COLLECTED_USER · 100042 EXPIRED_DATE_COLLECTED_OWNER · 100043 NOT_COLLECTED_OWNER · 100040 COMPANY_NOT_HAVE_OWNER · 100012 NEED_SUPPORT_FOR_LOGIN_ANOTHER_DEVICE · 100036 EXPIRED_PASSWORD_SYSTEM_DATE
- Thu thập: 200002 UPDATE_COLLECT_BIOMETRIC_FAIL · 200004 EKYC_TOKEN_INVALID · 200005 INVALID_ID_NUMBER_INFO · 200010 USER_ALREADY_COLLECTED (gọi confirm khi đã thu thập)
- Lưu ý: `AD_MESSAGE` lookup mã lỗi SME = 100000+ordinal; riêng mã cảnh báo (AuthWarning 100001..100008 trong comment code) KHÔNG tra theo cách này — tra theo tên (vd NEARLY_EXPIRED_DATE_COLLECTED = 100049).

## Cấu hình SIT (VBSMEONL.AD_CONFIG)
- `system.session_timeout_collect` = 600 (giây) — phiên thu thập.
- `auth.warning_expired_collect_duration` = 15 · `auth.warning_expired_collect_owner_duration` = 1 (ngày) · `auth.warning_nearly_expired_password` = 1 (bật cảnh báo).
- `expire.token.time.ekyc` = 1000000000 · `ekyc.token.duration` = 10000000000.

## Bẫy test
- Ngày hết hạn giấy tờ để TRỐNG cũng bị coi là hết hạn ⇒ login bị chặn (hay bị nhầm là bug).
- Kho eKYC có data KHÔNG có nghĩa là đã thu thập xong: bảng `VBEKYCSTORAGE.SUCCESS_COLLECT.CHANNEL_ID` quyết định — `SME` ⇒ SME bắt thu thập lại; `OMNI`/`OLD_TELLER`/`EKYC_PLUS`/`VNEID_ONBOARD` ⇒ SME chấp nhận là đã thu thập.
- Trạng thái thu thập bên SME có thể lệch với eKYC (hệ thống tự đối chiếu lại) ⇒ đọc cả 2 nguồn trước khi kết luận.
- LÝ DO "cố tình" coi bản ghi kênh SME là chưa thu thập: bản ghi do chính luồng SME tạo mà hợp đồng SME chưa cập nhật ⇒ lần thu thập trước đứt giữa đường ⇒ cho làm lại để hồ sơ/C06 bên SME khớp eKYC. Đây là CHỦ Ý (log "force reCollect"), không phải bug.
- ĐA HỢP ĐỒNG: trạng thái thu thập lưu THEO TỪNG hồ sơ/hợp đồng (`OMNI_CUSTOMER.STATUS_COLLECTED`), sinh trắc học lưu THEO CIF (1 CIF dùng chung cho mọi hợp đồng của người đó) ⇒ cùng 1 người có thể có hợp đồng "đã thu thập" và hợp đồng "chưa thu thập" (SIT có thật). Đăng nhập vào hợp đồng "chưa thu thập" mà kho eKYC được chấp nhận ⇒ tự đồng bộ hợp đồng đó (không bắt làm lại); chỉ nhánh NOT_COLLECT mới bắt chạy lại luồng thu thập cho hợp đồng đó.
- DB: `VBSMEONL.OMNI_CUSTOMER` (STATUS_COLLECTED 0/1/2, EXPIRED_DATE, REPRESENT, CIF_NO) · `VBSMEEKYC.CUSTOMER_EKYC` · `VBEKYCSTORAGE.SUCCESS_COLLECT` (bản ghi sinh trắc học: CIF, CHANNEL_ID, EXPIRE_DATE_CARD, STATUS).
