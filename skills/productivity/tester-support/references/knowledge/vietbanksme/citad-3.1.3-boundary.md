# Citad ↔ gói 3.1.3 — ranh giới & các bẫy đã kiểm chứng (15/09/2026)

Dùng khi ai đó hỏi "tính năng Citad nào thuộc gói 3.1.3" hoặc xin trace luồng copy / QR / danh bạ / huỷ lệnh cho Citad.

## Ranh giới gói 3.1.3 (đợt 1 = Napas 2.0 + nhóm dùng chung)

- **KHÔNG đụng lõi Citad**: khởi tạo, xác thực, hạch toán, danh mục giữ nguyên; thư mục migration `goi-3.1-napas2.0` **không có** bản ghi nào chứa chữ "citad" (đã grep = 0).
- **Đụng Citad (gián tiếp, tầng lệnh)**: huỷ lệnh ở bước khởi tạo · export uỷ nhiệm chi cho lô/lương (GD con 00207/01202) · luồng QR + danh bạ thụ hưởng · CR ẩn trường màn kết quả phê duyệt · app 1.1.0 (force update).
- **KHÔNG áp Citad**: tra soát GD chờ xử lý (nút check-pending chỉ mở cho Napas 2.0), risk score thụ hưởng, đối soát tự động.
- **"Giao dịch CITAD chờ tra soát" KHÔNG thuộc 3.1.3** — story VSONB-4774 còn *Need To Do*; SRS FE/BO mới viết 04/09/2026 (VSONB-5092/5096). 3.1.3 vẫn là timeout ⇒ lỗi 500017, đối soát thủ công.

## Bẫy thường gặp

- **Copy lệnh KHÔNG có API backend**: nút *Sao chép lệnh* là xử lý client — đọc chi tiết lệnh (`active-trans-reqs/detail` hoặc `completed-trans-reqs/detail`) rồi gọi lại `citad/init`; mọi ràng buộc được kiểm lại từ đầu. Ca dễ vỡ: bộ 4 thụ hưởng của lệnh cũ đã lệch danh mục ⇒ lỗi 300001/301002/308001 khi init.
- **Tên trường response**: `transId` / `status` / `transToken` — KHÔNG phải `transactionId` / `transactionStatus`.
- **Chi tiết lệnh chờ duyệt** trả cờ `allowCancel` / `allowApproval` — FE ẩn/hiện nút theo cờ này, không tự suy từ trạng thái.
- **CR ẩn trường** chỉ ẩn ở *màn kết quả phê duyệt*; màn chi tiết trong *Quản lý phê duyệt* vẫn hiện đủ người soạn / người duyệt / ý kiến phê duyệt.
- Danh bạ Citad (`00205`, `CITAD_TRANSFER`) **bắt buộc** có chi nhánh + tên thụ hưởng; bản ghi thiếu chi nhánh không dùng được cho Citad.

## Tài liệu tham chiếu (Confluence space `Vietbankomninb`)

- SRS_FE_Chuyển tiền liên ngân hàng (695732333)
- SRS_FE_Bổ sung một số chức năng Quản lý giao dịch (768117989) — sao chép lệnh, huỷ lệnh
- CR_FE_Điều chỉnh màn hình kết quả phê duyệt (864194205)
- SRS_FE_Chuyển tiền CITAD – Xử lý GD chờ tra soát (1023021124)
