# Tester ở nhà không vào được portal log — dùng Tailscale làm cửa riêng

## Dấu hiệu nhận biết (khiếu nại thường gặp)

Tester báo "vào VPN rồi mà link log không mở được". Máy tester Windows, VPN GlobalProtect
(Palo Alto). Kiểm chứng bằng PowerShell:

```powershell
Get-NetAdapter | Format-Table Name, InterfaceDescription, Status -AutoSize   # thấy PANGP Virtual Ethernet Adapter Secure
Test-NetConnection <IP-portal> -Port 10443
```

- `PingSucceeded : True` (đi qua card VPN, ping thông) NHƯNG `TcpTestSucceeded : False`
  → đường mạng có, **TCP bị firewall/policy VPN lọc**. KHÔNG phải lỗi portal, KHÔNG phải
  sai link, và không tự sửa được từ phía mình.
- Nếu máy tester KHÔNG thấy card VPN nào trong `Get-NetIPAddress` mà vẫn có route dải `10.0.0.0/8`
  trỏ on-link ra 1 card lạ (`NextHop 0.0.0.0`) → gói tin tới portal đi vào card đó rồi mất hút.

## Cách xử lý: Tailscale gateway (chạy bằng Docker, KHÔNG cần sudo)

Máy Hoàng (Ubuntu) không có quyền sudo password → dựng Tailscale bằng container:

```bash
docker run -d --name tailscale --net=host \
  --cap-add=NET_ADMIN --cap-add=NET_RAW --device=/dev/net/tun \
  -v tailscale-state:/var/lib/tailscale --restart unless-stopped \
  tailscale/tailscale:latest
# đăng nhập (giữ tiến trình sống để URL còn hiệu lực)
docker exec -d tailscale sh -c 'tailscale up --hostname=<node> --timeout=60m > /tmp/tsup.log 2>&1'
docker exec tailscale cat /tmp/tsup.log        # lấy URL https://login.tailscale.com/a/<id>
```

- **URL đăng nhập chỉ gửi cho Hoàng qua DM**, KHÔNG thả vào group (ai bấm trước là node vào tailnet của người đó).
- Sau khi auth: `docker exec tailscale tailscale status` / `tailscale ip -4` (IP dạng 100.x).
- Vào portal luôn được bằng `https://<ip-tailscale>:10443/omni-sme/` vì nginx proxy đang listen
  `0.0.0.0:443/10443`. Muốn URL đẹp `…ts.net` thì `tailscale serve` — **nhưng đừng bind cổng 443**
  (nginx đã giữ `0.0.0.0:443`), dùng cổng khác (vd `--https=8443`) hoặc vào thẳng IP:10443.
- Giới hạn đúng 1 người: tailnet riêng + tạo auth key **một lần dùng** (hoặc invite đúng email) cho
  máy tester; kèm ACL chỉ mở `tag:<gw>:10443`, phần còn lại mặc định chặn.
- State nằm trong volume `tailscale-state` + `--restart unless-stopped` + docker service `enabled`
  → reboot máy là tự lên lại, không phải bấm link.

## Dọn dẹp sau khi xong (bắt buộc đặt lịch)

Cửa này chỉ nên sống trong buổi cần dùng. Khi dựng xong **hỏi/lấy mốc giờ kết thúc từ Hoàng** rồi đặt
one-shot vào `~/.hermes/schedules.yaml` (skill `ultron-scheduled-actions`, KHÔNG tạo cron job mới):

```yaml
  - id: tailscale-teardown
    when: "17:30"
    date: "2026-09-12"          # one-shot, tự hết hạn sau ngày này
    script: tailscale_teardown.py
```

`~/.hermes/scripts/tailscale_teardown.py` làm: `tailscale logout` → `docker stop/rm tailscale` →
`docker volume rm tailscale-state` → DM báo Hoàng; idempotent, chạy lại vô hại, `--dry-run` để thử.
Dispatcher LUÔN gọi script bằng python (`build_cmd`) → script lịch phải là **.py**, không dùng .sh.

## Bật lại CHỈ khi Hoàng ra lệnh (không đặt lịch định kỳ)

Đây là cửa dùng theo vụ, không phải dịch vụ thường trực: **không** tạo action lặp ngày nào cũng bật.
Sau khi teardown thì node logout + state bị xoá sạch → không có gì tự bật lại (kể cả reboot, vì
container `--restart` đã bị xoá). Muốn dùng lại: chạy lại lệnh `docker run … tailscale/tailscale`
ở trên → **login lại từ đầu** (URL mới, gửi DM Hoàng) → tạo auth key mới cho máy tester.

## Kiểm chứng trước khi báo tester

```bash
docker ps --filter name=tailscale --format "{{.Names}} | {{.Status}}"
docker exec tailscale tailscale status
timeout 8 curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:10443/omni-sme/   # phải 200
```

## Pitfalls

- Đừng gỡ/ sửa container `omni-sme-proxy` (nginx) — nó là đường proxy UAT/LIVE đang chạy sẵn.
- `sudo -n tcpdump` fail vì không có passwordless sudo → đừng hứa capture gói tin.
- Nếu máy tester ping được mà TCP không được MỌI cổng nội bộ → khả năng cao là policy VPN;
  việc mở rule thuộc bên vận hành VPN, phải để Hoàng quyết.
