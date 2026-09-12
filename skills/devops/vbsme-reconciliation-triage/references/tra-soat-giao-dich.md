# Tra soát giao dịch (tra cứu trạng thái theo yêu cầu khách)

Lớp việc: tester báo *"user X bấm Tra soát giao dịch báo lỗi <mã>"*, hoặc *"giao dịch đang chờ tra soát mãi không đổi"*.

## 1. Khái niệm

- Nút **Tra soát / Kiểm tra trạng thái** ở danh sách lệnh đã hoàn tất = chủ động hỏi lại đối tác kết quả của **một** giao dịch đang chờ.
- Khác **job đối soát** (tự chạy theo lịch, quét theo lô). Nhưng cả hai đều hỏi đối tác theo **TRN** → cùng nguồn sự thật, khác cơ chế kích hoạt.
- Tra soát có chặn bấm liên tục (bấm quá nhanh → mã riêng kiểu "vui lòng thử lại sau"), đừng nhầm mã đó với mã lỗi nghiệp vụ.

## 2. Điều kiện để tra soát chạy được

```
Giao dịch đã có KẾT QUẢ CUỐI (thành công / thất bại)  -> trả luôn trạng thái, không gọi đối tác
Giao dịch đang CHỜ XỬ LÝ / TIMEOUT                     -> phải có ĐỦ:
     + mã tham chiếu (TRN) lưu trên giao dịch
     + ngày tham chiếu lưu trên giao dịch
Các trường hợp khác                                    -> TỪ CHỐI (mã dùng chung 500004)
```

## 3. Vì sao mã từ chối gây hiểu nhầm

Mã dùng chung cho nhiều màn (kiểu "yêu cầu không hợp lệ"); bảng mã lỗi chỉ có **một** câu chữ mặc định, thường chẳng liên quan tới tra soát. Trả lời theo **điều kiện chặn**, và nói rõ câu chữ mặc định không phải nguyên nhân (tránh tester mở bug theo câu chữ đó).

## 4. Bảng/trạng thái để kiểm chứng (SIT, qua db-access)

- **Danh sách lệnh hiện nút Tra soát**: lệnh đã duyệt xong nhưng kết quả giao dịch chưa chốt (trạng thái "chờ đối soát" trên bảng lệnh đã hoàn tất, không phải trạng thái trên giao dịch).
- **Giao dịch** (`OMNI_TRANSACTION`): trạng thái (Chờ duyệt / Chờ xử lý / Timeout / Thành công / Thất bại), **TRN lưu trên giao dịch**, **ngày tham chiếu**.
- **Metadata đối tác** (`OMNI_NAPAS_TRANS_METADATA`, cùng ID giao dịch): TRN + thời điểm đối tác trả TRN → dùng để phát hiện "đối tác đã trả TRN mà giao dịch vẫn trống".
- **Lịch sử bước xử lý** (`OMNI_TRANSACTION_PHASE`): bước cuối là "duyệt lệnh cuối thành công/thời gian chờ, **chờ tra soát**" + mã lõi trả về (mã *đang xử lý* kiểu `068` = chưa có kết quả cuối) → biết luồng đã đi tới đâu.

## 5. Biến thể "treo kép" — dấu hiệu cần báo dev

Lệnh nằm ở nhánh chờ tra soát, nhưng bản ghi **giao dịch vẫn giữ trạng thái Chờ duyệt và không có TRN/ngày tham chiếu** (dù metadata đối tác đã có TRN):

1. Bấm Tra soát → **từ chối (500004)** vì không đủ điều kiện ở mục 2.
2. Job đối soát lọc theo **trạng thái Chờ xử lý/Timeout + bắt buộc có TRN** (và chỉ với 2 dịch vụ chuyển tiền NAPAS, trong cửa sổ `scan_days` ngày) ⇒ **không bao giờ nhặt** giao dịch này → treo vô thời hạn cho tới khi xử lý tay.

Kết luận nghiệp vụ để trả tester: **bất thường ở bước duyệt cuối khi đối tác trả mã đang xử lý — giao dịch chưa được chuyển sang Chờ xử lý và chưa lưu mã tham chiếu**; không phải lỗi thao tác, không phải lỗi riêng user. Đây là việc của dev, không phải hướng dẫn tester thao tác lại.

## 6. Cách chứng minh khi SIT không có log (db-access)

1. Lọc giao dịch của user (`OMNI_CUSTOMER` → `OMNI_TRANSACTION` theo username/alias) rồi join bảng lệnh đã hoàn tất để biết lệnh nào đang chờ đối soát.
2. So TRN/ngày tham chiếu **trên giao dịch** với TRN trong **metadata đối tác** — có TRN ở metadata mà giao dịch trống ⇒ đúng biến thể mục 5.
3. **Quét theo NGÀY trên toàn môi trường** (`GROUP BY` ngày + trạng thái + có/không TRN, khoảng vài tuần) → tìm mốc đổi hành vi. Mốc rõ ràng thì khẳng định được "không phải riêng user này" và khoanh được thời điểm bắt đầu — luôn làm bước này trước khi kết luận.
4. Báo cáo PDF cho tester (ngôn ngữ nghiệp vụ, không tên class/file): tóm tắt → điều kiện tra soát → bảng trace của user → so sánh trước/sau mốc → nguyên nhân nghiệp vụ + hệ quả (kể cả việc job không nhặt được) → đề xuất dev xác minh.

## 7. Bảng mã trong luồng check-pending (đừng gán sai nguyên nhân)

Trong luồng tra soát, mã `500004` chỉ ném ở **đúng một điểm**: bước tiền xử lý của lệnh check-pending bên phân hệ giao dịch tài chính, sau khi tầng lệnh đã qua hết guard riêng. Điều kiện: giao dịch **không** thoả cả hai nhóm ở mục 2.

```
Trạng thái giao dịch           TRN + ngày tham chiếu   Kết quả khi bấm tra soát
-----------------------------  ----------------------  -----------------------------------
Thành công / Thất bại          -                       Trả kết quả cuối, không lỗi
Chờ xử lý (6) / Timeout (5)    đủ cả hai               Hỏi đối tác -> cập nhật kết quả
Chờ xử lý (6) / Timeout (5)    thiếu 1 trong 2         -> 500004
Chờ duyệt (1), Init (0), Đang xử lý (2/11)...          -> 500004
```

Các nhánh **khác** của cùng luồng — đừng nhầm với 500004:

- Bấm lại trong ~30s (lock theo khách hàng + lệnh) → `501015` "kiểm tra kết quả giao dịch quá nhanh";
- Mã dịch vụ của lệnh không map được sang service đích → `501000` dịch vụ không hỗ trợ;
- Lệnh đã có kết quả cuối rồi → trả luôn SUCCESS/FAILED, không gọi tiếp;
- Đối tác vẫn trả "đang xử lý" → trả notification "giao dịch đang chờ đối soát…", **không** phải lỗi;
- Lệnh không thuộc company đang đăng nhập → lỗi quyền (không phải 500004).
- 500004 ném ra **trước** khi lock chống bấm nhanh được ghi ⇒ bấm lại nhiều lần vẫn ra 500004, KHÔNG ra 501015 — nói rõ điểm này khi tester thắc mắc "sao bấm mãi vẫn cùng một mã".

Giao dịch NAPAS **V1** không bao giờ nằm ở nhánh pending (ở bước duyệt cuối, khi đối tác trả mã đang xử lý thì V1 bị ghi đè sang Thất bại) ⇒ V1 không rơi vào 500004 mà đi nhánh "đã có kết quả cuối".

## 8. Kiểm trạng thái một mã GD: phải đọc CẢ hai tầng

Khi được hỏi "trạng thái giao dịch `<trace>` ở cả lệnh và GD", lấy 4 nguồn rồi trình bày dạng bảng:

1. **Lệnh đã hoàn tất**: trạng thái (5 = chờ kết quả đối soát) + TRN của lệnh.
2. **Giao dịch**: trạng thái + TRN trên giao dịch + ngày tham chiếu + `MODIFIED_DATE`.
3. **Metadata đối tác**: TRN + thời điểm đối tác trả TRN.
4. **Lịch sử bước xử lý**: timeline từng bước (thiết bị, mã phản hồi, mã lỗi đối tác) → biết luồng đã đi tới đâu.

Dấu hiệu quyết định: `MODIFIED_DATE` của giao dịch **đứng im từ lúc tạo lệnh**, trong khi lệnh đã sang "chờ đối soát" + đã có TRN ⇒ bước duyệt cuối **không ghi gì sang giao dịch** (đúng biến thể mục 5). Nêu bằng chứng này ra để dev khỏi hỏi lại.

Lưu ý schema: bảng **lệnh đã hoàn tất** chỉ lưu TRN, **không có cột ngày tham chiếu** — `REF_DATE` nằm trên giao dịch; SELECT nhầm cột đó ở bảng lệnh sẽ lỗi `ORA-00904`.

## 9. Ranh giới với các skill khác

- Tra mã lỗi / vì sao ném mã → `vbsme-error-diagnosis` (mục mã lỗi dùng chung).
- Quy trình log UAT/LIVE + job đối soát theo lô → `references/pending-transaction-reconciliation.md` trong skill này.
- Chuẩn trả lời group + báo cáo PDF + scope-map → `tester-support`.

## 10. Nguyên nhân gốc hay gặp của "treo kép": cập nhật DB thất bại ÂM THẦM vì độ dài BYTE

Khi mốc "bắt đầu hỏng" (mục 6.3) **trùng thời điểm một dòng thông báo trong bảng mã lỗi được tạo/sửa** → nghi ngay **ghi DB thất bại vì nội dung thông báo vượt ô lưu trữ**, KHÔNG phải logic trạng thái. Dấu hiệu nhận biết:

- Ô lưu nội dung phản hồi trên **giao dịch** hẹp hơn ô trên **lệnh/phase** ⇒ phase vẫn ghi được (DB trông "bình thường") trong khi bản ghi giao dịch không nhích — chi tiết này rất dễ bị bỏ qua.
- Cột `VARCHAR2(n BYTE)` giới hạn **BYTE**, không phải ký tự: tiếng Việt có dấu 2–3 byte/ký tự ⇒ `n` byte chỉ chứa ~`n/3` ký tự có dấu. Thông báo tiếng Việt vượt ô trong khi bản tiếng Anh (thuần ASCII) vẫn vừa.
- Đường ghi này chạy **bất đồng bộ**: lỗi chỉ nằm ở log tầng nền, người dùng vẫn thấy bước trước thành công ("lệnh duyệt thành công") ⇒ triệu chứng là *duyệt xong mà giao dịch không đổi*.

Cách chứng minh bằng dữ liệu (đủ để dev không hỏi lại):

1. Lấy **giới hạn khai báo** của ô thông báo trên giao dịch và trên phase (xem dưới, mục 11) rồi so với `LENGTHB()` nội dung thông báo trong bảng mã lỗi.
2. Lấy **dòng mã lỗi** tương ứng: độ dài byte bản VI/EN + `CREATED_DATE`/`MODIFIED_DATE` của dòng → đối chiếu mốc bắt đầu hỏng.
3. Tìm **giao dịch cũ trước mốc** cùng mã lỗi: nội dung phản hồi lưu trên giao dịch khi đó là bản **ngắn hơn** (≤ giới hạn byte) ⇒ chứng minh trước mốc ghi được, sau mốc thì không.
4. `MAX(LENGTHB(<ô thông báo>))` trên toàn bảng ⇒ chứng minh cột **chưa từng** chứa giá trị vượt giới hạn.
5. Rà toàn bảng mã lỗi: đếm số mã **đang bật** vượt giới hạn byte của từng ô ⇒ danh sách mã khác cùng rủi ro (thường vài chục mã, và các mã cùng nhóm thường dùng **chung một nội dung** nên cùng lỗi).

Kết luận nghiệp vụ để trả tester: nội dung thông báo lúc giao dịch chuyển sang trạng thái chờ **quá dài so với ô lưu trữ của giao dịch** ⇒ bước cập nhật giao dịch không ghi được ⇒ giao dịch đứng ở bước trước, thiếu mã tham chiếu ⇒ từ chối tra soát (500004) và job đối soát bỏ qua. Đề xuất: nới ô (hoặc cắt ngắn nội dung trước khi ghi), rà các mã cùng rủi ro, và xử lý tay các giao dịch đã kẹt.

**Không tự sửa được schema:** Ultron chỉ có quyền ghi DỮ LIỆU (DML), không có quyền DDL trên DB ⇒ gói `ALTER TABLE` phải để bank/dev chạy. Khi Hoàng yêu cầu tạo việc: mở task Jira (project `VSONB`, kèm file .sql đính kèm + nội dung SQL trong mô tả) thay vì tự chạy. Phương án tạm thời nếu chưa kịp DDL: giảm nội dung message đang dài xuống dưới giới hạn byte của cột.

## 11. Đo giới hạn byte của cột bằng db-access

`sql_get_columns` **không** trả về độ dài cột. Lấy giới hạn khai báo bằng:

```sql
SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE, CHAR_LENGTH, DATA_LENGTH, CHAR_USED
FROM SYS.ALL_TAB_COLUMNS
WHERE OWNER = 'VBSMEONL'
  AND TABLE_NAME IN ('OMNI_TRANSACTION', ...)
  AND COLUMN_NAME IN ('RESPONSE_MESSAGE', ...)
```

- Dùng `SYS.ALL_TAB_COLUMNS` (lọc `OWNER`) — `VBSMEONL.USER_TAB_COLUMNS` báo `ORA-00942` vì tool buộc tiền tố schema mà view này không thuộc schema đang kết nối.
- `CHAR_USED = 'B'` ⇒ giới hạn tính theo **byte**; so bằng `LENGTHB()`, đừng so bằng `LENGTH()`.
- Muốn biết "cột có bao giờ chứa giá trị dài chưa": `SELECT MAX(LENGTHB(<cột>)), MAX(LENGTH(<cột>)), COUNT(*) FROM <bảng> WHERE <cột> IS NOT NULL`.
