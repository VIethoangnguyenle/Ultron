# Đích gọi ra hệ thống ngoài — tra theo môi trường

## Nơi khai (vbsme & họ omni)

- Repo app: `config/application-thirdparty-config.yml` → `common.client.external.<tên-đối-tác>.uri`.
  Hầu hết là `${ENV_VAR}` ⇒ source không chứa giá trị, chỉ chứa key + danh sách sub-path nghiệp vụ.
- Giá trị chạy thật theo môi trường: cây deploy `test-workload/vnp-ocp-svc/<app>/<cluster>/` — các
  `config-map-*thirdparty*.yaml` là configmap đã triển khai, URI điền cứng: `uri: http://10.x.x.x:port`.
- `.env` trong repo app = cấu hình dev local; trùng giá trị với SIT là chuyện thường nhưng **không** phải
  bằng chứng cho môi trường được hỏi.

## Chốt cluster ↔ môi trường

- Mở file deploy của app trong cùng thư mục cluster (`ib-<app>.yaml`, `appserver-service.yaml`, …) và đọc
  `host:` ⇒ `vbsme-sit.vnpaytest.vn` = SIT. Không suy môi trường từ tên thư mục cluster.
- Một cluster phục vụ nhiều app (vbsme, vietbank-omni, namabank-sme…): mỗi app có configmap riêng, phải đọc
  đúng configmap của app đang được hỏi.

## Bảng đã chốt (đọc lại từ config khi cần — đừng coi là hằng số)

```
CONFIG KEY                     APP/CỤM           ĐÍCH GỌI RA
vnpay-payment-gateway (vbsme)  vbsme SIT         http://10.22.18.120:8070
billing-gw (omni)              vietbank-omni SIT http://10.22.18.120:8070/vnp
eKYC thirdparty                vbsme SIT         10.22.18.209:19033 (cổng eKYC, không phải payment gateway)
```

## Khi trả lời

- Một bảng ngắn trong code block + **một** câu nêu nguồn (file deploy/thư mục nào). Không kèm danh sách path
  dài cho người ngoài nhóm.
- Nói rõ đây là **đích** gọi ra, và **IP nguồn/egress** để đối tác whitelist không nằm trong config app.
- Kết luận lấy từ config trong repo ⇒ ghi rõ là bản trong repo; chỉ khẳng định "đang chạy" khi đã đọc được
  configmap sống trên cluster.

## Bảo mật

- File `*-thirdparty*.yaml` chứa cả `private-key`/`public-key` của đối tác ⇒ trích đúng dòng `uri`, không dán
  cả block, không đưa giá trị key sang group/kênh ngoài phạm vi được phép.
