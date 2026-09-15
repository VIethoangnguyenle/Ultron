# VietBank Digital — nguồn log & mã lỗi (đã kiểm chứng 15/09/2026)

## 1. Portal log
- UAT: `https://10.22.17.219:10443/omni-digital/` — Apache autoindex, mỗi service một thư mục.
- LIVE: `https://10.22.17.219:10443/omni-digital/live/`
- File log đặt theo pod: `digital-<service>-<hash>-<pod>.log` (vd `digital-transfer-f6bd59d7d-6b6ts.log`).
- Lấy log: `curl -k -s -o <file> https://10.22.17.219:10443/omni-digital/<service>/<pod>.log`
  rồi index/phân tích bằng `vblog.py` (skill `vnpay-log-analyzer`) — y hệt SME.
- **Chọn file theo ngày sửa mới nhất** trong index (nhiều pod cũ vẫn nằm đó, file cũ rất dễ lấy nhầm:
  gặp file 18KB ngày 29/01 toàn log reload cache, phải đổi sang file 3,5MB ngày 15/09).

### Danh sách service UAT (15/09/2026)
```
api-service              appserver-service     auth-service
bank-service             bo                    card-service
facepay-service          internal-service      media-service
napas-service            nonfinancial-service  notification-service
onboard-service          payment-service       sms-otp-service
transfer-service         worker-service
```
(ngoài ra `UAT/` = log archive cũ, `live/` = môi trường LIVE)

## 2. Nội dung log (giống format dvnh-common/SME)
- Có `requestId`, username, path API, mã lỗi dạng `TransactionError:INVALID_...:<CODE>`,
  request/response JSON đầy đủ → tra theo `requestId` hoặc username được.
- Mã lỗi thật gặp trong log digital: `500050`, `500002`, `40205043`, `40210019`,
  dạng prefix `VBG04...` (vd `VBG040140205043`).

## 3. Tra mã lỗi
- Cơ chế: bảng `AD_MESSAGE` (entity `MessageEntity` trong `vietbank-omni/common/base`) — giống SME.
- **Schema của digital (Hoàng chốt 15/09): lấy danh sách schema của SME rồi thay `SME` → `DIGI`, trừ các ngoại lệ:**
  ```
  Oracle: VBDIGIONL   VBDIGIOFF   VBDIGIFACE   VBDIGISOTP   VBDIGIEKYC
  Mongo : VBDIGILOGS        (VBSMELOGS → VBDIGILOGS)
  Chung : VBEKYCSTORAGE     (dùng chung với SME, KHÔNG đổi tên)
  KHÔNG có: bản RLE cho digital (VBSMERLE không có tương ứng)
  ```
  ⇒ Mã lỗi digital tra ở `VBDIGIONL.AD_MESSAGE`.
- **Trạng thái truy cập (15/09):** cổng db-access CHƯA có connection tới `VBDIGIONL`
  (`Database 'VBDIGIONL' not found or access denied`), và đọc chéo `VBSMEONL` → `VBDIGIONL`
  bị `ORA-01031: insufficient privileges`. Muốn tra mã lỗi digital phải nhờ Hoàng cho phép
  thêm kết nối READ-ONLY rồi giao claude sửa cổng DB (Ultron KHÔNG tự sửa `config.yaml` của
  db-access, KHÔNG tự restart `mcp-db-tools`).
- Đối chiếu tạm trước khi có kết nối: cùng cơ chế AD_MESSAGE nên một số mã dùng chung vẫn tra được
  ở `VBSMEONL.AD_MESSAGE` (`500050` → Soft OTP bị tạm khóa; `500002` → dịch vụ không hỗ trợ),
  nhưng mã riêng của digital (`40205043`, `40210019`) thì KHÔNG có ở đó — phải chờ `VBDIGIONL`.

## 4. Repo & graph
- 3 repo con là git thật (git.vnpay.vn), KHÔNG phải `not-a-git-repo` như `meta.json` ghi:
  `vietbank-omni` (dev-sit) · `viet-bank-omni-ekyc` (master) · `dvnh-common` (feature/kafka-module).
- 15/09: `origin/dev-sit` của vietbank-omni đã đi trước bản local vài commit (`5f175dded` vs `53f7f6124`)
  ⇒ graph hiện có là bản của hôm 14/09, muốn "tươi" phải fetch + dựng lại.
- Chỉ vietbank-omni có nhánh `dev-sit`; 2 repo còn lại không có ⇒ chờ Hoàng chốt nhánh.
