# Lấy log UAT VBSME (portal nội bộ)

Tester hỏi "check log" cho user/lệnh ở môi trường UAT → tải log TRỰC TIẾP từ portal (read-only, curl -k), không cần VPN client đặc biệt:

```
https://10.22.17.219:10443/omni-sme/                      → danh sách service
https://10.22.17.219:10443/omni-sme/<service>/            → danh sách file log theo pod
https://10.22.17.219:10443/omni-sme/<service>/<pod>.log   → tải file log
```

- Service thường dùng: `approval-service` (danh sách chờ duyệt, khởi tạo duyệt/duyệt hàng loạt), `napas-service` (247/chuyển tiền, điểm rủi ro),
  `transfer-service`, `bank-service`.
- File log đặt tên theo pod, mỗi pod một file; lấy file có ngày sửa mới nhất của service cần xem.
- Portal hiển thị dạng Apache index: mỗi dòng có tên file + ngày sửa + dung lượng.
- Sau khi tải: index bằng vblog.py của skill `vnpay-log-analyzer` rồi tra `user <username>` / `grep <trace_no>`.
- Nếu portal không tới được (ngoài mạng nội bộ) → xem `~/Desktop/notes/tricks/omni-sme-proxy/README.md`.
