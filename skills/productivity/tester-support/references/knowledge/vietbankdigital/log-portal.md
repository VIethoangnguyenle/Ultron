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
  ở `VBSMEONL.AD_MESSAGE`, nhưng mã riêng của digital (`40205043`, `40210019`) thì KHÔNG có ở đó.
- **NỘI BỘ — KHÔNG đưa ra câu trả lời cho tester:** mỗi dự án có bảng mã lỗi riêng; cùng một số mã
  có thể mang nội dung khác nhau (đã gặp ở `500050`). Vì vậy trả lời tester digital thì LUÔN tra
  `VBDIGIONL.AD_MESSAGE` — tuyệt đối không tra bảng của dự án khác, và cũng KHÔNG nhắc/so sánh với
  dự án khác trong group (Hoàng chốt 15/09: kiến thức dự án nào chỉ dùng trong group dự án đó).
- `40205043`, `40210019`: không có trong `VBDIGIONL.AD_MESSAGE` ⇒ nhiều khả năng là mã core/đối tác,
  không phải mã message.

## 6. Quyền truy cập DB (đã mở 15/09)
- Hoàng cho phép 15/09: mở READ-ONLY cho toàn bộ DB của dự án digital.
- Đã thêm vào source `default_agent` (key mà Hermes đang dùng) 6 entry read-only: `VBDIGIONL`,
  `VBDIGIEKYC`, `VBDIGIFACE`, `VBDIGISOTP`, `VBDIGILOGS`, `VBDIGIOFF`. Đã verify độc lập: `list_databases` trả 14 DB.
- `VBDIGIOFF`: ĐÃ MỞ read-only 15/09 (cùng instance `127.0.0.1:2114` / `DVNHTEST`, entry `VBDIGIOFF`).
  Kiểm chứng 15/09: 23 bảng — nhóm giao dịch OFF/lô/định kỳ: `OMNI_TRANSACTION*`, `OMNI_TRANSACTION_BATCH_GIFT`,
  `OMNI_TRANSACTION_SCHEDULE*`, `OMNI_AUTO_PAYMENT_*`, `OMNI_SAVING_PRODUCT_METADATA`, `AD_SERVICE*`, `AD_TRANS_TYPE`.
  **KHÔNG có bảng `AD_MESSAGE`** ⇒ tra mã lỗi vẫn phải vào `VBDIGIONL`.
- Cổng ở `127.0.0.1:8443/mcp`, chạy bằng user unit `mcp-db-tools`; server TỰ hot-reload config
  (`fs.watchFile` ~1s) nên sửa config không cần restart service.
- **Pitfall:** session MCP đang mở giữ SNAPSHOT quyền cũ → sửa quyền xong, phiên Hermes đang chạy vẫn
  chỉ thấy quyền cũ cho tới khi mở session MCP mới (restart gateway). Muốn tra ngay mà chưa restart:
  gọi thẳng cổng bằng key của source `vietbank_omni` (đọc trong `.env` của `Db-Access`, KHÔNG in ra ngoài).
- Các DB đang có entry connection cho digital: VBDIGIONL / VBDIGIEKYC / VBDIGIFACE / VBDIGISOTP /
  VBDIGILOGS (tất cả `127.0.0.1:2114` service `DVNHTEST`, riêng LOGS là mongo `localhost:27018/omnivietbank`).

## 4. Repo & graph
- 3 repo con là git thật (git.vnpay.vn), KHÔNG phải `not-a-git-repo` như `meta.json` ghi.
- Quy tắc lấy mã nguồn để dựng graph (Hoàng chốt 15/09) + đã kiểm chứng:
  ```
  vietbank-omni        → nhánh dev-sit        (local & origin đều khai common_version = 5.0.8)
  viet-bank-omni-ekyc  → nhánh dev            (khai common_version = 4.6.11.2 — KHÁC omni)
  dvnh-common          → tag v5.0.8 = 1092139e (2026-08-26), theo common_version của vietbank-omni
                         (working tree hiện là 5.0.9 ⇒ KHÔNG lấy working tree)
  ```
- Lệch cần Hoàng biết: ekyc khai common 4.6.11.2 còn omni khai 5.0.8 — graph gộp 2 mốc khác nhau,
  đã báo Hoàng; mặc định vẫn theo version của omni (5.0.8) như anh chốt.
- 15/09: `origin/dev-sit` của vietbank-omni đã đi trước bản local vài commit (`5f175dded` vs `53f7f6124`)
  ⇒ graph hiện có là bản hôm 14/09, muốn "tươi" phải fetch + dựng lại.

## 8. eKYC của DIGITAL (ghi 15/09/2026)
- Source: `vietbank-digital/viet-bank-omni-ekyc` (570 file .java, nhánh local `master`; quy tắc graph: nhánh `dev`)
  + phần eKYC trong `vietbank-omni/common/ekyc` & `transaction/business/.../init_transaction`.
- Log: `.../omni-digital/facepay-service/` (mới nhất 08/04/2026 — `ekyc-facepay-f569c9c46-wvj6l.log`, 998 KB,
  6.990 dòng, 26 ERROR) và `.../omni-digital/onboard-service/` (mới nhất 04/08/2026).
- DB: `VBDIGIEKYC` (read-only, 25 bảng: `CUSTOMER_EKYC`, `MESSAGE_EKYC` (272 dòng), `EKYC_ERROR`,
  `CARD_INFO*`, `HTE_REQUEST_FACE_PAY`, `SDK_VERSION`, `FACEPAY_FAILED_INTERVALS`, …) + `VBEKYCSTORAGE` (dùng chung).
- Mã lỗi eKYC tra ở `VBDIGIEKYC.MESSAGE_EKYC` / `EKYC_ERROR` — **KHÔNG** nằm trong `VBDIGIONL.AD_MESSAGE`.
- Trace thật: `[VBB_OMNI13243678706058423] [] [POST:/api/v1/face-pay/payment]`.
- Phân biệt với SME (tên file log eKYC GIỐNG NHAU, không dùng được): dùng đường dẫn portal,
  tiền tố requestId (`VBB_OMNI` vs `VBB`), và profile (digital KHÔNG có tiền tố `ekyc-`).

## 9. Phủ môi trường của cổng log digital (kiểm chứng 15/09/2026)
- Cổng log `omni-digital/` phục vụ **UAT** (log đang chạy) + `live/` (bản lưu LIVE).
  Bằng chứng trong log: `[Digital-UAT-v1.0.0]` (bo), `uat-omnidigital-bucket-02` (media/onboard/appserver/internal),
  banner `{ UAT version 1.4.14 ... }` (napas). KHÔNG thấy bucket/khai báo nào mang nhãn SIT.
- **KHÔNG có nguồn log SIT** trên cổng này (đã thử `/omni-digital/sit/` 404; các path top-level khác đều 403 blanket
  nên không suy ra được gì — đừng probe thêm).
- **Đối chiếu chéo log ↔ DB (15/09):** giao dịch trong DB test (`VBDIGIONL.OMNI_TRANSACTION`, user 0975316905,
  trace `016258090019401`, 09:14) KHÔNG có trong log UAT; ngược lại trace trong log UAT (`016257170009890`,
  `016247140009636`, ...) KHÔNG có trong DB ⇒ **log UAT và DB test là 2 môi trường khác nhau** (giống SME).
  ⇒ Khi tester hỏi ca trên SIT: log chi tiết phải xin file; dữ liệu thì tra được ở DB.
- Log có đủ trường để tra theo **username** (`"username":"0xxxxxxxxx"`), `traceNo`, `requestId`, `cif` ⇒
  tester chỉ cần đưa username + mốc giờ là tra được (không cần file log).
