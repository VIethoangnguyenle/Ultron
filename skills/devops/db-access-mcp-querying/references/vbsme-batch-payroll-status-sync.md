# VBSME — đồng bộ trạng thái LÔ/LƯƠNG khi yêu cầu duyệt đã kết thúc

Dùng khi màn danh sách vẫn hiện "Chờ duyệt" nhưng màn chờ duyệt trống và mở chi tiết báo lỗi mã dùng chung.

## Bảng liên quan

| Bảng | Vai trò |
|---|---|
| `OMNI_PAYROLL_TRANSACTION` / `OMNI_BATCH_TRANSACTION` | bản ghi lệnh chi lương / chuyển tiền theo lô — màn danh sách đọc bảng này |
| `OMNI_PAYROLL_TRANSACTION_ITEM` / `OMNI_BATCH_TRANSACTION_ITEM` | từng người nhận; nối cha bằng `PAYROLL_TRANSACTION_ID` / `BATCH_TRANSACTION_ID` |
| `OMNI_ACTIVE_TRANS_REQ` | yêu cầu duyệt ĐANG mở (nguồn của màn "chờ duyệt") |
| `OMNI_COMPLETED_TRANS_REQ` | yêu cầu duyệt đã kết thúc (duyệt / từ chối / huỷ) |
| `OMNI_TRANSACTION` | giao dịch gốc (lịch sử giao dịch), nối qua `TRANSACTION_ID` |
| `OMNI_TRANSACTION_PHASE` | vết phase của giao dịch |

Hai bảng cha có cùng bộ cột (gồm `TRANS_REQ_ID`, `TRANS_REQ_CREATED_DATE`, `TRACE_NO`, `USERNAME`, `STATUS`,
`MODIFIED_DATE`). Bảng ITEM **không có cột ngày** — chỉ đổi được `STATUS`.

## Trạng thái số

- `OMNI_(PAYROLL|BATCH)_TRANSACTION.STATUS`: 0 chờ duyệt · 1 chờ xử lý · 2 đang xử lý · 3 chờ duyệt huỷ · 4 đã huỷ ·
  5 hoàn thành · 6 đã từ chối · 7 thất bại · 8 chờ retry
- `...(ITEM).STATUS`: 0 chờ xử lý · 1 thành công · 2 thất bại · 3 timeout · 4 chờ duyệt huỷ · 5 đã huỷ ·
  6 chờ retry · 7 chờ duyệt · 8 đã từ chối
- `OMNI_TRANSACTION.STATUS`: 0 khởi tạo · 1 chờ duyệt · 2 đang duyệt · 3 thành công · 4 thất bại · 12 đã huỷ
- ⚠️ `docs/enum-db-mapping.md` có cột "Mô tả" bị lệch một dòng so với cặp Name/Value ⇒ chỉ tin **cặp Name + Value**
  và comment cột trong DB (`sql_get_columns`), đừng đọc cột mô tả.

## Điều kiện "lệch"

```sql
WHERE t.STATUS = 0
  AND t.TRANS_REQ_ID IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM <SCHEMA>.OMNI_ACTIVE_TRANS_REQ a WHERE a.ID = t.TRANS_REQ_ID)
```

- Yêu cầu duyệt đã kết thúc nằm ở `OMNI_COMPLETED_TRANS_REQ`; cũng gặp ca mất hẳn khỏi cả hai bảng ⇒ tiêu chí
  phải là **NOT EXISTS ở bảng ACTIVE**, đừng join sang bảng COMPLETED.
- Bản ghi con của nhóm này thường đứng ở `STATUS = 7` (chờ duyệt) ⇒ phải đổi cùng lúc, không chỉ đổi cha.

## Luồng huỷ thật của app (để bám theo)

`Cancel{Payroll,Batch}TransactionConfirmExecutor`: giao dịch gốc → `TRANSACTION_CANCELED` (12) + tạo dòng phase;
cha lô/lương → `CANCELED` (4); toàn bộ bản ghi con → `CANCELED` (5).

## Triệu chứng phía người dùng

1. Màn "chờ duyệt" (đọc `OMNI_ACTIVE_TRANS_REQ`) không có bản ghi.
2. Mở chi tiết / danh sách người nhận: bước "On Pending Approval check permission" không tìm thấy yêu cầu ⇒
   exception `NOT_FOUND` gắn **mã dùng chung** 999003 (thông báo "hệ thống đang bảo trì…" — KHÔNG phải bảo trì,
   đừng đọc thông báo để kết luận nguyên nhân).

## Script dọn dữ liệu

`vietbank-sme-omni/ops/fix_orphan_pending_approval_batch_payroll.sql` — báo cáo → backup → update → kiểm chứng,
`DEFINE SCHEMA_NAME` để người chạy điền, phần cập nhật `OMNI_TRANSACTION` để sẵn dạng comment cho chủ dự án chốt.
