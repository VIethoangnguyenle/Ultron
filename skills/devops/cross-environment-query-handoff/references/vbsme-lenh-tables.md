# VietBank SME — bảng LỆNH (`*_TRANS_REQ`) và ca SIT↔LIVE lệch cột

Đây là ca thật làm nên các quy tắc trong SKILL.md: query lệnh theo CIF doanh nghiệp + ngày soạn lệnh,
chạy sạch trên SIT nhưng lỗi trên LIVE.

## Bảng nào chứa gì

| Bảng | Chứa gì | Dấu hiệu |
|---|---|---|
| `OMNI_ACTIVE_TRANS_REQ` | lệnh **CHƯA xong** — đang soạn / chờ duyệt / đang xử lý | có `TRANSACTION_ID` (NULL nếu chưa sinh giao dịch) |
| `OMNI_COMPLETED_TRANS_REQ` | lệnh **ĐÃ xong** — đã duyệt / bị từ chối / duyệt thất bại | có `REF_NO` (mã tham chiếu ngân hàng) |
| `OMNI_ACTIVE_TRANS_REQ_STAGE` / `OMNI_COMPLETED_TRANS_REQ_STAGE` | từng bước duyệt của lệnh | khoá theo lệnh |
| `OMNI_TRANSACTION` | giao dịch phát sinh từ lệnh | `TRACE_NO`, `TRANS_REQ_ID` |

**Muốn "mọi lệnh theo CIF + ngày soạn" thì PHẢI `UNION ALL` cả ACTIVE + COMPLETED** — chỉ tra một bảng là
mất đúng nhóm lệnh chưa xong (lệnh đang chờ duyệt nằm ở ACTIVE, không có dòng nào ở COMPLETED). Đây là
gốc của ca "lệnh chờ duyệt không xuất hiện trong báo cáo chi tiết GD chuyển khoản".

## Cột quan trọng

| Cột | Ý nghĩa |
|---|---|
| `TRACE_NO` | mã lệnh/GD SME |
| `COMPANY_CIF_NO` | CIF **doanh nghiệp** — đúng filter "CIF KHDN" của màn BO |
| `COMPANY_NAME` | tên doanh nghiệp |
| `CREATED_DATE` | **ngày soạn lệnh** — mốc "thời gian tạo lệnh" (khác mốc hạch toán) |
| `USERNAME` / `FULL_NAME` | người tạo lệnh |
| `LAST_APPROVED_USERNAME` / `LAST_APPROVED_CIF_NO` | người/CIF duyệt cuối |
| `CURRENT_STAGE_LEVEL` / `MAX_STAGE_LEVEL` | bước hiện tại / tổng bước → `1/2` = mới xong *Soạn lệnh*, còn chờ *Duyệt lệnh* |
| `CURRENT_VI_STAGE_NAME` | tên bước hiện tại ("Soạn lệnh", "Duyệt lệnh") |
| `SENDER_ACCOUNT`, `BENE_BANK_CODE`/`BENE_BANK_NAME`, `BENE_ACCOUNT`, `AMOUNT` | TK nguồn, NH/TK thụ hưởng, số tiền |
| `STATUS` | COMPLETED: 0 = bị từ chối, 1 = đã duyệt, 2 = duyệt thất bại. ACTIVE: có thể NULL toàn bộ — và bản LIVE có thể **không có cột này** → đọc trạng thái qua `CURRENT_STAGE_LEVEL`/`MAX_STAGE_LEVEL`, đừng dựa vào `STATUS` |

## Query mẫu — lệnh soạn ngày D của CIF doanh nghiệp X (bản "cột lõi")

```sql
SELECT r.nguon                                           AS NGUON_LENH,   -- DANG_XU_LY | DA_XONG
       r.trace_no                                        AS MA_GD_SME,
       r.company_cif_no                                  AS CIF_KHDN,
       TO_CHAR(r.created_date,'DD/MM/YYYY HH24:MI:SS')   AS NGAY_SOAN_LENH,
       r.username                                        AS NGUOI_TAO,
       r.amount                                          AS SO_TIEN,
       r.current_stage_level || '/' || r.max_stage_level AS BUOC,
       r.current_vi_stage_name                           AS BUOC_HIEN_TAI
FROM (
        SELECT 'DANG_XU_LY' AS nguon, trace_no, company_cif_no, created_date, username, amount,
               current_stage_level, max_stage_level, current_vi_stage_name
        FROM   OMNI_ACTIVE_TRANS_REQ
        UNION ALL
        SELECT 'DA_XONG', trace_no, company_cif_no, created_date, username, amount,
               current_stage_level, max_stage_level, current_vi_stage_name
        FROM   OMNI_COMPLETED_TRANS_REQ
     ) r
WHERE r.company_cif_no = 'CIF_KHDN'
  AND r.created_date  >= DATE 'YYYY-MM-DD'
  AND r.created_date  <  DATE 'YYYY-MM-DD' + 1
ORDER BY r.created_date;
```

Thêm `REF_NO` (chỉ bảng COMPLETED có) thì nuôi ở nhánh ACTIVE: `CAST(NULL AS VARCHAR2(50)) AS ref_no`.

Đọc kết quả: **lệnh chờ duyệt** = `NGUON_LENH = DANG_XU_LY` + `BUOC = 1/2`; lệnh xong = `DA_XONG`.
Có kết quả trong DB mà báo cáo/màn hình không ra ⇒ lỗi ở tầng báo cáo (chuyển dev), không phải lỗi dữ liệu.

## Ca lệch cột SIT↔LIVE (vì sao có mục này)

Bản bổ sung cột `STATUS` cho cả hai nhánh chạy sạch trên SIT, nhưng trên LIVE trả
`ORA-00904: "STATUS": invalid identifier` tại nhánh COMPLETED ⇒ bản LIVE thiếu cột. Quy trình xử lý nằm ở
SKILL.md (bản cột lõi + câu dò cột + nói đúng mức tin cậy + báo dev về lệch schema).

## Qua `db-access`: prefix `SYS.` cho dictionary view

`SELECT column_name, data_type FROM SYS.ALL_TAB_COLUMNS WHERE owner = '<SCHEMA>' AND table_name = '<BẢNG>' ORDER BY column_id;`
— viết trần `ALL_TAB_COLUMNS`/`ALL_TABLES` bị cổng chặn (phải có prefix schema).

## Kiểm chứng

Query mẫu execute sạch trên SIT (`VBSMEONL`). SIT **không chứa dữ liệu UAT/LIVE** ⇒ chạy với CIF/mã GD
của LIVE ra 0 dòng là bình thường, không phải query sai — nói trước với người chạy.
