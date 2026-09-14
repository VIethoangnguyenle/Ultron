# Trace hành trình 1 giao dịch/lệnh (VBSME – LIVE)

Khi Hoàng/tester hỏi "giao dịch X đi qua những bước nào / vì sao báo cáo không có bản ghi" → dựng
**timeline** từ log, không đoán.

## Nguồn log
Cổng log LIVE: `https://10.22.17.219:10443/omni-sme/live/` (`curl -sk`). Khối cần tải:
- tạo lệnh / NAPAS: `sme-napas-*`
- duyệt lệnh: `sme-approval-*`
- báo cáo (BO): `bo-api-*`

Mỗi khối có **nhiều pod**, log chia theo thời gian → phải tải nhiều pod mới phủ hết khoảng ngày.
Log dạng văn bản, mỗi request là 1 header + các dòng JSON tiếp theo:
`[<version>][YYYY-MM-DD HH:MM:SS.mmm] - [requestId] [username] [uri] <message>`.

## Từ khoá tra theo thứ tự
1. **mã GD (traceNo)** → tìm dòng tạo lệnh (`Sending message to topic: transaction.create_trans_req_success`,
   `GRPC: .../createActiveTransReq` — có `stage_level`/`stage_name`, `status`).
2. Trong cùng dòng lấy tiếp **`transactionId`** (mã giao dịch nội bộ) và **`transReqId`** (mã lệnh)
   → dùng 2 mã này tra sang khối duyệt, vì log khối duyệt nhiều khi **không in traceNo**.
3. Mốc hành động: `initFinalApprove` (duyệt cấp cuối), `initReject` (từ chối), `POST:/api/v1/app/napas/confirm`
   (xác thực), `CONFIRM_REJECTED_TRANSACTION_FAILED` (không cập nhật trạng thái).
4. Dòng lỗi dạng text: `VnpayInvalidException: TransactionError:<NAME>:<code>` · `ErrorCode:<NAME>:<code>`.

## Mã lỗi luồng duyệt hay gặp
```
500031   Khởi tạo giao dịch không thành công (đi kèm 501011 = mã giao dịch đã tồn tại)
500070   Trạng thái giao dịch không hợp lệ (chưa có trong AD_MESSAGE của VBSMEONL)
500033   Từ chối giao dịch thất bại
999003   NOT_FOUND – không tìm thấy lệnh
```
Tra nghĩa: `SELECT CODE, VI_CONTENT FROM VBSMEONL.AD_MESSAGE WHERE CODE IN (...)`.

## Kết luận mẫu
Lệnh **chưa duyệt xong ⇒ chưa sinh giao dịch ⇒ báo cáo chi tiết GD chuyển khoản 0 bản ghi là ĐÚNG dữ liệu**
(báo cáo đọc bảng giao dịch, giao dịch chỉ sinh khi lệnh được duyệt). Nếu các lần Duyệt/Từ chối đều
lỗi (500070/500033/999003) ⇒ **lệnh KẸT** → mục "việc cần làm" chuyển dev.

## Pitfalls
- **Không** kết luận "báo cáo trả rỗng" chỉ từ log BO: log BO **không** ghi số bản ghi trả về.
- Một dòng JSON có thể chứa nhiều mã lệnh anh em (…841/842/843/844) → lọc theo ID, đừng gán nhầm lệnh.
- Che PII trước khi đưa vào báo cáo: số điện thoại, số tài khoản, blob mã hoá.
- File gửi tester/Hoàng = **PDF** (`~/.hermes/scripts/md2pdf.py`), gửi file thật bằng
  `gchat_send_file.py --thread "spaces/<SPACE>/threads/<THREAD_ID>"` — **tên thread phải đầy đủ**,
  chỉ truyền `<THREAD_ID>` là lỗi 400 "invalid thread resource name".
