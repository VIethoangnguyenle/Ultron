# Danh mục dịch vụ (DB) vs khai báo mã dịch vụ trong code — vbsme

Tài liệu NỘI BỘ: dùng để trả lời, KHÔNG dán ra group (tên class/hằng số là thông tin nội bộ).

## Kiến thức nền

- **Danh mục dịch vụ thật nằm ở DB**, không phải ở code:
  - `VBSMEONL.AD_SERVICE`: một dòng = một dịch vụ (`CODE` 5 số, `TYPE` = 3 số đầu, `VI_NAME`/`EN_NAME`,
    `IS_ACTIVE`, `STATUS`, cờ `IS_FINANCIAL`/`IS_APPROVAL`, `CODE_CORE`, `SERVICE_ID`).
  - `VBSMEONL.AD_SERVICE_TYPE`: nhóm dịch vụ (`002` Chuyển khoản, `010` Giao dịch phi tài chính,
    `011` Quản lý lệnh phi tài chính, `012` Chuyển tiền chi lương, `013`/`014` Hủy chi lương / hủy lô,
    `016` Duyệt–từ chối hàng loạt, `017` Tiện ích SDK...).
  - Runtime đọc danh mục qua entity JPA trỏ `@Table(name = "AD_SERVICE")` / `AD_SERVICE_TYPE` và nạp
    cache (`SERVICE_FACTORY = "AD_SERVICE"`) — dùng cho hạn mức, phân quyền, hiển thị, đối soát.
- **`ServiceCodeConstants` KHÔNG phải bản sao danh mục.** Mỗi service có một bản riêng (auth-service,
  transfer-service, bank-service, napas-service, onboard-service, ekyc common). Chúng chỉ khai báo những
  mã mà code **phải rẽ nhánh** — chủ yếu làm tham số `@CheckAppVersion(serviceCodes = ...)` (chặn phiên
  bản app tối thiểu theo từng chức năng, logic ở `CheckVersionAppAspect`) và vài chỗ so sánh mã khi xử lý.
- ⇒ Một mã **có trong `AD_SERVICE` mà không có hằng số là bình thường**, không phải bug — và ngược lại.
  Danh mục = "toàn bộ dịch vụ hệ thống biết"; khai báo trong code = "mã mà code phải tự phân biệt".

## Ví dụ đối chiếu (đã kiểm chứng bằng grep toàn workspace)

- CÓ trong code: `00709` (đổi mật khẩu), `00801`/`00802` (kích hoạt / gia hạn Soft OTP), `01014` (cho phép
  đăng nhập thiết bị khác), `01003`/`01004`/`01005` (đăng ký/hủy biến động số dư), `00711`, `00703`...
- KHÔNG có trong code (chỉ nằm trong danh mục): `01101`, `01002` (nhật ký giao dịch), `01006` (hướng dẫn
  sử dụng), `01007` (FAQ), `01010`–`01013` (báo cáo / in chứng từ HBK, POS-mPOS).
- `01101` – "Phê duyệt yêu cầu người dùng", nhóm `011` – Quản lý lệnh phi tài chính: luồng phê duyệt được
  quyết theo **lệnh/yêu cầu đang được duyệt** (loại giao dịch + trạng thái duyệt + cấp duyệt), không quyết
  theo mã dịch vụ ⇒ mã này tồn tại chỉ để phục vụ danh mục.

## Recipe chứng minh

1. `SELECT CODE, TYPE, VI_NAME, IS_ACTIVE, STATUS FROM VBSMEONL.AD_SERVICE WHERE CODE = '<mã>'` rồi tra tên
   nhóm ở `VBSMEONL.AD_SERVICE_TYPE WHERE CODE = '<TYPE>'`.
   (Hiện trạng SIT: nhóm `011` chỉ có `01101` + 1 dòng rác `Pentest1234560` `IS_ACTIVE=0`.)
2. `cd /home/zane/Desktop/work/vietbank/vietbank-sme && grep -rn --include=*.java -w "<mã>" vietbank-sme-omni dvnh-common viet-bank-ekyc-sme`
3. Grep vài mã anh em hai chiều để chỉ ra sự lệch (xem mục ví dụ ở trên).
4. Cần đối chiếu khai báo: `mcp__understand_anything__get_node_source(node_id=<class ServiceCodeConstants của service>, project="vietbank-sme")`.

## Pitfalls

- `query_nodes` là tìm mờ theo khái niệm: literal `01101` → 0 node; tên chung `AdService` → 868 match nhiễu.
  Literal → grep; đường dẫn → `search_by_file_path`.
- Dữ liệu SIT hay lẫn bản ghi test (`Pentest123456`, `a`, `12`) trong cùng bảng danh mục.

## Hình dạng câu trả lời trong group (dev hỏi)

- Nghiệp vụ thuần: "danh mục dịch vụ" vs "khai báo mã dịch vụ trong code" — KHÔNG nêu tên class/hằng số/file.
- Nêu cơ chế: danh mục là dữ liệu chuẩn nạp lúc chạy; khai báo trong code chỉ cho chỗ cần rẽ nhánh (điển
  hình: chặn phiên bản app tối thiểu theo từng chức năng).
- Kèm 2 nhóm ví dụ (có/không có trong code) để họ tự kiểm chứng; trả lời thẳng trong chat, không dựng file.
