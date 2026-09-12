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

## Cho tester truy cập từ máy khác (proxy qua máy Hoàng)

Máy Hoàng chạy nginx pass-through (docker `--net=host`) trỏ tới `10.22.17.219:10443`; đồng nghiệp cùng mạng vào qua IP máy Hoàng:

```
UAT   https://10.173.18.24/omni-sme/          (wifi: https://10.173.129.230/omni-sme/)
LIVE  https://10.173.18.24/omni-sme/live/     (wifi: https://10.173.129.230/omni-sme/live/)
```

- Cổng 80/443/10443 đều nhận (đường dẫn cũ có `:10443` vẫn chạy).
- Trình duyệt sẽ cảnh báo chứng chỉ (truy cập qua IP) → Advanced → Proceed.
- IP có thể đổi khi đổi mạng → kiểm tra lại `ip -brief addr show eno2 wlo1` trước khi gửi cho tester.
- Muốn chắc proxy còn sống: `curl -sk -o /dev/null -w "%{http_code}" https://10.173.18.24/omni-sme/` (200 = OK).
