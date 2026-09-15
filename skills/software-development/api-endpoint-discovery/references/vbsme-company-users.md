# vbsme — endpoint đã chốt bằng recipe (nhánh `origin/dev-sit`)

## "Danh sách người tạo lệnh theo company" = danh sách nhân viên của công ty

```
Endpoint                                                           Định danh              Trả về
POST /api/v1/{app|web}/auth/company/employees                      công ty theo SESSION   employees[]: id, avatar, fullName
                                                                   (body rỗng)
POST /api/v1/{app|web}/auth/notification/balance-change/employees  công ty theo SESSION   + status, userAlias, mobileOtt, email,
                                                                   (app/web tách riêng)   admin/represent; tách currentCustomer
                                                                                          khỏi othersCustomer (trừ chính mình,
                                                                                          sort theo trạng thái rồi tên)
POST /api/v1/integration/vietbank/companies/users                  body `cifNo`           id, userAlias, fullName, admin,
(API đối tác, ký checksum)                                                                representative, userCifNo, phoneNumber
                                                                                          — chỉ nhân viên ACTIVE và là
                                                                                          admin/đại diện
```

2 endpoint đầu **không có tham số company**: công ty lấy theo session đang đăng nhập. Muốn chỉ định công ty
khác thì đi đường `integration-service` (truyền `cifNo`).

## Filter "người tạo lệnh" ở danh sách lệnh

Field nhận là **`createdCustomerId`** (Long) — khớp `id` trả về ở bảng trên:

```
POST /api/v1/{web|app}/completed-trans-reqs
POST /api/v1/{web|app}/active-trans-reqs/processing
```

Lịch sử giao dịch (`GetTransactionHistoriesRequest`) **không** có filter người tạo lệnh.
