# Bản ghi huỷ kẹt ở VBSME — move sang bảng `_CANCEL`

Áp cho VBSME (schema `VBSMEONL`, quyền `write`). Quy trình chung: mục "Move bản ghi giữa bảng gốc
và bảng `_CANCEL`" trong SKILL.md. Câu lệnh: `templates/vbsme-move-customer-to-cancel.sql`.

## Cặp bảng

| Bảng gốc | Bảng đích |
|---|---|
| `OMNI_CUSTOMER` | `OMNI_CUSTOMER_CANCEL` |
| `OMNI_WORKFLOW_STAGE_CUSTOMER` | `OMNI_WORKFLOW_STAGE_CUSTOMER_CANCEL` |

Một ca "huỷ khách hàng" đúng chuẩn để lại dấu vết:

- bản ghi rời `OMNI_CUSTOMER` → nằm trong `OMNI_CUSTOMER_CANCEL`, **giữ nguyên ID**;
- các dòng cấu hình luồng duyệt rời `OMNI_WORKFLOW_STAGE_CUSTOMER` → `OMNI_WORKFLOW_STAGE_CUSTOMER_CANCEL`,
  **giữ nguyên ID + WORKFLOW_ID/WORKFLOW_STAGE_ID + bậc duyệt**;
- bản ghi trong bảng `_CANCEL` của ca chuẩn: `STATUS = 14` (CANCEL), `PRE_STATUS = 13`, `OLD_STATUS = 4`.

## Nhận dạng bản ghi kẹt

Còn nguyên trong `OMNI_CUSTOMER`, `STATUS = NULL`, `PRE_STATUS`/`OLD_STATUS = 14` (dấu vết đã huỷ
nhưng bước move chưa chạy), `IS_ACTIVE = 1`, và **0 dòng** trong `OMNI_CUSTOMER_CANCEL`.

- **Mẫu đối chứng nằm ngay trong dữ liệu**: cùng một CIF có thể có nhiều user khác `COMPANY_ID` —
  lấy ca đã huỷ đúng làm chuẩn để chốt kế hoạch, không cần đọc source code (move thuần dữ liệu).
- **Chỉ move đúng user được yêu cầu**; nói rõ trong tin xác nhận rằng user cùng CIF khác công ty
  không bị đụng.

## Cột bị thiếu ở bảng `_CANCEL`

`OMNI_CUSTOMER_CANCEL` thiếu 6 cột so với `OMNI_CUSTOMER`: `SOTP_EXPIRED_DATE`, `UNLOCK_TIME`,
`ACTIVE_DATE`, `LAST_ACTIVE_DATE`, `NEW_DEVICE_UPDATE_EXPIRED_TIME`, `BYPASS_EKYC`.
⇒ `INSERT` phải liệt kê đúng phần **giao** của 2 bảng; `INSERT ... SELECT *` lệch cột là chết.
Cột `"LEVEL"` của bảng stage phải bọc nháy kép.

## Đo ảnh hưởng & trình duyệt

- Move 1 user = 1 dòng khách hàng + N dòng luồng duyệt (đếm thật bằng `COUNT(*)` trước khi trình).
- Preview của câu `DELETE` chính là bằng chứng ảnh hưởng (liệt kê đủ cột từng dòng sẽ mất) —
  đối chiếu với người yêu cầu trước khi chạy.
- Số cột đủ để đối chiếu nhưng **không dán cột `PASSWORD`/`CHECKSUM`** ra chat.
