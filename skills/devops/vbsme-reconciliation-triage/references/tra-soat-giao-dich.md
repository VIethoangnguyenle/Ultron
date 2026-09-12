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

## 12. Hai đường chốt trạng thái ghi lại khác bộ trường

Đường **job đối soát** và đường **nút cập nhật/tra soát** đều hỏi đối tác theo TRN và nhận cùng kết quả, nhưng phần **ghi lại** khác nhau:

| Trường trên giao dịch (`OMNI_TRANSACTION`) | Job đối soát | Nút cập nhật/tra soát |
|---|---|---|
| Trạng thái | ghi | ghi |
| Mã giao dịch core banking (REF_NO) | ghi | ghi |
| `RESPONSE_CODE` (mã phản hồi SME) | **không ghi lại** ⇒ **đã fix 12/09/2026**: ghi `00` = thành công, mã lỗi lõi = thất bại | ghi: `000` = thành công, `01` = thất bại |
| `RESPONSE_MESSAGE` (nội dung phản hồi) | **không ghi lại** ⇒ **đã fix**: `Thành công` khi thành công, mã lỗi lõi khi thất bại | ghi: **mã lõi** trả về (vd `00`) |
| Lịch sử bước xử lý (`OMNI_TRANSACTION_PHASE`) | ghi mốc đối soát | ghi mốc đối soát |
| Bảng rủi ro NAPAS / hoàn hạn mức khi thất bại | có | có |

- Dấu hiệu nhận biết sớm: dữ liệu **đã được lấy về** (đối tác trả kết quả, payload có cả mã lẫn nội dung) nhưng bước cập nhật **không dùng** những trường đó ⇒ DB giữ nguyên giá trị cũ chứ không phải "không lấy được".
- Hệ quả tester thấy: giao dịch do job chốt thành công vẫn hiển thị `500069` + *"…đang được xử lý…"* ⇒ **thông tin tự mâu thuẫn** trên báo cáo chi tiết giao dịch chuyển khoản.
- Kết luận nghiệp vụ: "hai cách chốt trạng thái chưa ghi lại cùng bộ thông tin; cần dev xác nhận là thiếu sót hay chủ đích, và thống nhất quy ước mã giữa 2 đường". **Cập nhật 12/09/2026: đã kết luận là thiếu sót, Hoàng đã chốt quy ước và đã fix đường job (xem mục 12.2).** Khi trả lời tester: đừng hứa sửa thay dev, chỉ nêu hiện trạng + việc đã/đang làm. Muốn biết kết quả thật của giao dịch do job chốt → đọc mốc đối soát trong lịch sử bước xử lý hoặc log lượt job, **không** đọc 2 cột phản hồi trên báo cáo.
- Kiểm chứng bằng dữ liệu (SIT, db-access):

```sql
SELECT ID, CODE, STATUS, REF_NO, RESPONSE_CODE, RESPONSE_MESSAGE, MODIFIED_DATE
FROM VBSMEONL.OMNI_TRANSACTION
WHERE CODE = '<trace>';
```

So 2 giao dịch cùng kết cục nhưng khác đường chốt (một cái để job chốt, một cái bấm nút) — chênh lệch nằm đúng ở 2 cột phản hồi là bằng chứng đủ để dev không hỏi lại.

Ảnh/báo cáo tester gửi có thể thuộc **UAT** (báo cáo chi tiết giao dịch chuyển khoản trên màn VietinBank) — db-access chỉ đọc được các DB SIT ⇒ tra trace/REF_NO đó ở `VBSMEONL` sẽ **không ra dòng nào**. Khi đó lấy ảnh + đọc code làm bằng chứng, đừng kết luận "không tìm thấy giao dịch".

### 12.1 Ba phép thử để kết luận "bug (thiếu sót)" hay "chủ đích"

1. **Dữ liệu có đi theo luồng không**: đối tác trả kết quả → bước trung gian **đã set** cả mã lẫn nội dung phản hồi vào đối tượng mang sang bước ghi, nhưng bước ghi **không đọc** 2 trường đó ⇒ kết luận "hệ thống không có dữ liệu" là sai; trường tồn tại mà không ai dùng là dấu hiệu làm thiếu.
2. **Đường khác có ghi cùng dữ liệu từ đúng nguồn đó không**: nút cập nhật ghi đủ 2 trường từ chính câu trả lời đó ⇒ hai đường lấy cùng dữ liệu mà một đường bỏ ⇒ không thể là quy ước nghiệp vụ.
3. **Có ghi "giá trị thay thế" ở tầng khác không**: bước ghi của job vẫn ghi mã/nội dung **cố định** cho mốc lịch sử (thành công sau đối soát = mã thành công của hệ thống; thất bại = mã lỗi hệ thống + mô tả tiếng Anh) thay vì mã lõi thật ⇒ có ý định ghi nhận kết quả nhưng ghi ở **tầng lịch sử**, bỏ tầng giao dịch.

⇒ Lệch **hai chiều** (job chỉ ghi tầng lịch sử, nút chỉ ghi tầng giao dịch, mỗi bên bỏ trường của bên kia) = **thiếu sót cần bổ sung**, không phải chủ đích. Đề xuất fix: bước ghi của job set thêm 2 trường từ kết quả lõi — nhưng **xin Hoàng chốt quy ước giá trị trước khi sửa** (`000`/`01` kiểu NAPAS như đường nút, hay mã thành công của hệ thống như job đang mang sẵn); hai đường đang dùng 2 kiểu giá trị khác nhau nên không tự chọn.

### 12.2 Quy ước giá trị đã chốt (Hoàng chốt 12/09/2026)

Hai đường dùng 2 kiểu giá trị khác nhau ⇒ Hoàng đã chốt lấy **convention chung của hệ thống** làm chuẩn:

- **Ca thành công**: `RESPONSE_CODE` = `00` (mã thành công của hệ thống) + `RESPONSE_MESSAGE` = *"Thành công"*.
  Căn cứ: DB SIT có **2.018 dòng** thành công đều là `00`/`Thành công`; **không có dòng nào** dùng `000` ⇒ `000` là giá trị lạ chỉ đường nút sinh ra.
- **Ca thất bại**: `RESPONSE_CODE`/`RESPONSE_MESSAGE` lấy từ kết quả tra soát của lõi; nếu rỗng thì fallback mã lỗi hệ thống `99`.
- Đường **nút cập nhật** (`000`/`01` + mã lỗi thô ở cột nội dung) được xác nhận là **chỗ cần sửa ở task sau (backlog riêng)** — KHÔNG sửa trong task job đối soát.
- Còn 1 điểm cần task riêng: bước tra soát đặt *nội dung phản hồi* của ca thất bại = **mã lỗi**, không phải câu mô tả ⇒ muốn đọc được như convention DB phải tra bảng thông điệp (`AD_MESSAGE`).

Cách kiểm chứng nhanh giá trị nào là chuẩn (đừng tin tên hằng số trong code):

```sql
SELECT RESPONSE_CODE, RESPONSE_MESSAGE, COUNT(*) FROM VBSMEONL.OMNI_TRANSACTION
GROUP BY RESPONSE_CODE, RESPONSE_MESSAGE ORDER BY COUNT(*) DESC;
```

### 12.3 Nhận biết giao dịch được chốt bởi đường nào, từ lịch sử bước xử lý

`OMNI_TRANSACTION_PHASE` (cột `PHASE` số, `NAME`, `OMNI_RESPONSE_CODE`, `OMNI_RESPONSE_MESSAGE`, `TRANSACTION_ID`, `CREATED_DATE`):

- Mốc do **job** tạo mang thêm mã/nội dung **cố định** nói rõ "sau đối soát" (kiểu `Success after reconciliation` / `Failed after reconciliation`).
- Mốc do **nút cập nhật** tạo **không** set 2 ô đó (NULL) — quan sát đúng như vậy trên SIT.
- Tên mốc lưu bằng **tiếng Việt** (kiểu "Tra soát thành công, Giao dịch thành công", "Duyệt lệnh cuối timeout, chờ tra soát") ⇒ lọc theo tên phải dùng chuỗi tiếng Việt, đừng lọc theo tên enum trong code.

```sql
SELECT * FROM (
  SELECT t.ID, t.STATUS, t.RESPONSE_CODE, t.RESPONSE_MESSAGE,
         p.NAME, p.OMNI_RESPONSE_CODE, p.OMNI_RESPONSE_MESSAGE, p.CREATED_DATE
  FROM VBSMEONL.OMNI_TRANSACTION t
  JOIN VBSMEONL.OMNI_TRANSACTION_PHASE p ON p.TRANSACTION_ID = t.ID
  WHERE p.NAME LIKE '%Tra soát%'
  ORDER BY p.CREATED_DATE DESC) WHERE ROWNUM <= 15;
```
