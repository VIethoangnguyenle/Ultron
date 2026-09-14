# Log BO-api (cổng live): đọc được gì, KHÔNG đọc được gì

Dùng khi tester hỏi "check log BO xem vì sao báo cáo/màn hình ra 0 bản ghi".

## Có gì trong log
Mỗi lượt gọi API của app BO có **1 dòng duy nhất** dạng:

```
[<ts>] [ INFO] [Logging] [<env>] [<Class.Method>] [?] [req=<uuid>] [user=<USERCODE>] - resp_from_be_api process_time=<ms>,uri=<path>?<query>,http_status=200,code=00,client_version=...,client_ip=...
```

- `user=` → tài khoản BO đã bấm tìm (vd NHIPTB, MAIDTN, YENNT).
- `uri=` → **chứa toàn bộ tham số lọc**: `pageNumber,pageSize,branchCode,companyCifNo,responseCode,refNo,createdUserName,lastApprovedUserName,createdCifNo,lastApprovedCifNo,transactionStatus,fromDateStr,toDateStr`.
  - `fromDateStr/toDateStr` dạng `yyyyMMddHHmmss` → đọc ra "khoảng ngày tester đã tìm".
  - `responseCode=` chính là **mã giao dịch SME** (vd 006236144190841); `refNo=` là mã giao dịch core banking.
  - `transactionStatus=` là **mã trạng thái SME**: 0 khởi tạo · 1 chờ duyệt · 2 đang duyệt · 3 thành công · 4 thất bại · 5 timeout · 6 chờ kết quả · 7 từ chối · 8 khởi tạo lỗi · 11 chờ xử lý · 12 đã huỷ · 14 huỷ lỗi.
- `http_status` + `code` → chỉ nói **cuộc gọi thành công/thất bại về mặt kỹ thuật**.

## KHÔNG có gì trong log
- **Không có số bản ghi trả về**, không có payload/response body, không có SQL, không có tên bảng.
⇒ **Tuyệt đối không được nói "log cho thấy kết quả rỗng" hay "log cho thấy có N bản ghi"**. Log chỉ chứng minh: đã gọi, bộ lọc là gì, gọi thành công hay không.
Muốn biết có bao nhiêu bản ghi → phải xem **màn hình báo cáo** (ảnh tester gửi) hoặc tầng dịch vụ phía sau, không suy ra từ log BO.

## Mẹo tổng hợp nhanh (đếm theo khoảng ngày)
```bash
grep -a 'uri=/api/v1.0/rpt-detail-transaction' bo-api-*.log \
 | grep -o -E 'fromDateStr=[0-9]*&toDateStr=[0-9]*|\[user=[^]]*\]|transactionStatus=[0-9]*' | sort | uniq -c
```
Suy luận được (nhưng phải ghi rõ là *suy luận*): nhiều lượt `pageNumber=2..7` ⇒ danh sách có nhiều trang ⇒ có dữ liệu khớp filter đó.

## Xuất file (Excel) ở BO — log nằm ở ĐÂU (bài học 2026-09-14)

Tester báo *"bấm nút Xuất excel mà không tải được file"* ⇒ **log bo-api KHÔNG đủ**, phải đọc thêm **pod `bo-job`** (job nền BO) — cùng thư mục `bo/` trên portal, tên file có tiền tố `bo-job-*`.

Chuỗi xử lý (theo giờ log, để dựng timeline):

| Bước | Dấu vết trong log | Nghĩa |
|---|---|---|
| 1 | `<Màn hình>Controller.Export` (vd StorageSth) | Test bấm nút xuất; chỉ tạo **phiên xuất**, KHÔNG sinh file tại đây |
| 2 | `ExportDataController.Fetching` | Màn hình hỏi trạng thái file |
| 3 | **pod bo-job**: `Creating job: BO_JOB_GET_DATA-<id>` → `Started read data id=<id>` | Bộ phận chạy nền mới thực sự lấy dữ liệu |
| 4 | **pod bo-job**: `Read data ended with status = Done / Cancel` | `Done` = có file; `Cancel` = không có file cho tester tải |
| 5 | `ExportDataController.PreviewExcel` | Màn hình chờ mở/lấy file, **cắt ở ~10.000ms** ⇒ tester thấy "quay hoài không có file" |

Nguyên nhân hay gặp khi job `Cancel`: **thiếu chuỗi kết nối trong cấu hình UAT** — dạng log `Connection string for key '<Key>' not found in configuration.` + `Job read data exception`. Đây là **lỗi cấu hình môi trường**, không phải lỗi tài khoản tester và không phải lỗi dữ liệu; và **thường ảnh hưởng mọi nghiệp vụ xuất dùng chung kho đó**, không chỉ màn hình tester đang test.

Cách đối chiếu mốc phát sinh (rất nên làm): tải log `bo-job` của **ngày trước** rồi `grep -o "Read data ended with status = [A-Za-z]*" | sort | uniq -c` — nếu hôm trước `Done` hết mà hôm nay `Cancel` ⇒ kết luận "cấu hình/deploy mới làm hỏng", thay vì "chức năng lỗi".

Lưu ý khi trả lời: KHÔNG nêu tên key cấu hình / tên job / tên class ra group — chỉ nói nghiệp vụ ("thiếu cấu hình kết nối tới kho lưu trữ eKYC trên UAT"). Chi tiết kỹ thuật gửi riêng Hoàng.

## Bẫy đã gặp
- Tester hỏi "các lần tìm khoảng thời gian nào" → trả đúng **bảng: khoảng ngày | số lần | từ giờ | đến giờ | tài khoản tìm**; đừng chỉ nói "tìm nhiều lần".
- **Ảnh màn hình có thể khác log**: ảnh chụp 1 lượt tìm (vd khoảng 01/07→01/08) nhưng log có nhiều lượt khác đã bao đúng ngày cần tìm → đừng lấy ảnh làm đại diện cho cả quá trình tìm.
- Lệnh **chờ duyệt (status 1, bước 1/2 "Soạn lệnh")** khác với lệnh **đã duyệt thành công (status 3, bước 2/2)**; khi báo cáo không ra bản ghi, luôn đối chiếu 1 mã "anh em" đã duyệt cùng ngày/cùng tiền để tách nguyên nhân (trạng thái vs lỗi dữ liệu).
