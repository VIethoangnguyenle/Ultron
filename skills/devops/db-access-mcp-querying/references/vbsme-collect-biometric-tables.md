# VBSME — bảng dữ liệu thu thập sinh trắc & chẩn đoán lệnh duyệt bị chặn

Dùng khi tester báo lệnh treo ở duyệt cuối kèm lỗi dạng "chưa thu thập / hết hạn thu thập sinh trắc học".

## Ranh giới các tầng (đừng lẫn)

| Tầng | Ở đâu | Ý nghĩa |
|---|---|---|
| Dữ liệu thu thập gốc (eKYC) | `VBEKYCSTORAGE.SUCCESS_COLLECT` | khách đã thu thập gì, khi nào, giấy tờ hạn nào, đã xác thực dữ liệu dân cư (`STATUS_C06`) + đồng bộ ngân hàng (`BANK_SYNCED`) chưa; kèm `STATUS_BIO`, `EXPIRE_DATE_CARD`, `REQUEST_COLLECT_ID`, `CHANNEL_ID` |
| Trạng thái phía SME | `VBSMEONL.OMNI_CUSTOMER` | SME *nghĩ* khách đang thế nào: `STATUS_COLLECTED`, `EXPIRE_DATE_COLLECTED`, `EXPIRED_DATE` (hạn giấy tờ) |
| Nhật ký đồng bộ | `VBSMEONL.OMNI_UPDATE_COLLECT_METADATA` | `STATUS_C06`, `DATE_ISSUE_C06`, `STATUS_BIOMETRIC`, `STATUS_BANK`, `CHANNEL`, `CREATED_DATE` — từng lần đồng bộ + mã kết quả |
| Lượt gọi FacePay | `VBSMEFACE.REQUEST_FACE_PAY` (+ `REQUEST_FACE_PAY_HIS`, `HTE_REQUEST_FACE_PAY`) | 1 dòng / 1 lượt gọi, **ghi cả lượt fail** (`IS_SUCCESS=0`, `LIST_ERROR_CODE`), có `SERVICE_CODE`, `TRACE_NO`, `CIF`, `TIME`, `AMOUNT` |
| Điều kiện xác thực của lệnh | `VBSMEONL.OMNI_WORKFLOW_STAGE_SCHEME`, `AD_AUTH_METHOD`, `OMNI_WORKFLOW_STAGE_CUSTOMER` | cấp duyệt cho phép phương thức nào (Soft OTP / FacePay + Soft OTP) và ai thuộc cấp đó |
| Bước xử lý của lệnh | `VBSMEONL.OMNI_TRANSACTION_PHASE`, `OMNI_ACTIVE_TRANS_REQ(_STAGE)` | timeline từng bước (response code, third-party error) |

Sai phổ biến: thấy dữ liệu eKYC còn hạn rồi kết luận "không thể lỗi hết hạn". Lỗi thường thuộc tầng
*điều kiện FacePay*, không thuộc tầng *dữ liệu thu thập* — phải kiểm cả ba tầng.

## Luồng chẩn đoán (5 bước)

1. `OMNI_TRANSACTION` theo `TRACE_NO` → `ID`, `STATUS`, `CUSTOMER_ID`, `COMPANY_ID`.
2. `OMNI_TRANSACTION_PHASE WHERE TRANSACTION_ID = <id> ORDER BY ID` → timeline. **Số dòng "khởi tạo luồng duyệt cuối" = số lần user bấm** (bấm lại sau khi fail); không có bản ghi duyệt ⇒ chặn ở bước xác thực, không phải bước soạn lệnh.
3. **Lượt gọi FacePay có xảy ra không?** Tra `REQUEST_FACE_PAY` / `REQUEST_FACE_PAY_HIS` / `HTE_REQUEST_FACE_PAY` theo CIF + ngày lỗi, và kiểm mốc `MAX(TIME)` của bảng. Ngày lỗi trống (ngày khác có) ⇒ chặn trước khi gọi FacePay ⇒ nghi phạm ở điều kiện thu thập của tài khoản duyệt.
4. **Đối chiếu tài khoản duyệt cùng cấp** (khác biệt giữa các tài khoản là manh mối chính):

```sql
SELECT c.USERNAME, c.FULL_NAME, c.CIF_NO, c.STATUS_COLLECTED,
       TO_CHAR(c.EXPIRE_DATE_COLLECTED,'DD/MM/YYYY') AS HET_HAN_THU_THAP,
       TO_CHAR(c.EXPIRED_DATE,'DD/MM/YYYY')         AS HET_HAN_GIAY_TO
FROM VBSMEONL.OMNI_WORKFLOW_STAGE_CUSTOMER ws
JOIN VBSMEONL.OMNI_CUSTOMER c ON c.ID = ws.CUSTOMER_ID
WHERE ws.WORKFLOW_STAGE_ID = <stage_id>;
```

5. **Đối chiếu dữ liệu thu thập đúng CIF**: `SELECT * FROM VBEKYCSTORAGE.SUCCESS_COLLECT WHERE CIF = '<cif>'` + `OMNI_UPDATE_COLLECT_METADATA WHERE CIF_CORE = '<cif>'`.

## Mẫu kết luận (dùng lại được)

(a) Lệnh đang ở đâu, dừng ở bước nào; (b) FacePay đã được gọi chưa; (c) dữ liệu thu thập của người
duyệt còn gì / thiếu gì so với tài khoản đối chứng; (d) **đã chứng minh bằng dữ liệu vs còn suy luận**;
(e) hướng đi tiếp khả thi.

- Không có log môi trường (SIT không có log) ⇒ nói thẳng chưa chỉ đích danh được điểm chặn, đừng khẳng định.
- Mã lỗi app hiện ra có thể không có trong repo lẫn bảng mã lỗi backend (là key phía app) ⇒ chỉ map về
  nhóm mã lỗi backend tương ứng, đừng nhận đã tìm thấy đúng chuỗi đó.
- **Gợi ý khắc phục phải sống sót qua ràng buộc nghiệp vụ người hỏi nêu**: lệnh vượt hạn mức ⇒ bắt buộc
  FacePay + Soft OTP ("chỉ Soft OTP" vô hiệu); app chưa có chức năng thu thập lại ("xoá & đăng ký lại"
  vô hiệu). Hướng còn dùng được: dev đẩy lại dữ liệu thu thập cho đúng CIF; dùng tài khoản khác cùng cấp
  duyệt đang đủ điều kiện; đổi tham số test (bỏ qua FacePay ở SIT) hoặc hạ số tiền dưới mốc buộc FacePay.
