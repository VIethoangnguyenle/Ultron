# Mở lại Tailscale + cổng Siri + cầu nối dịch vụ nội bộ

## 0. Bản đồ cổng (sau khi tắt/mở lại)

| Cổng | Dịch vụ | Ai vào được |
|---|---|---|
| `tailnet_ip:9444` | cổng nói Siri (`siri_speak.py`, unit `siri-speak`) | dải CGNAT tailnet |
| `tailnet_ip:9443` | gateway webhook (`/webhooks/siri`) | dải CGNAT tailnet |
| ~~`0.0.0.0:9445` / `:9446`~~ | cầu nối GitLab / console qua nginx `omni-sme-proxy` — **ĐÃ BỎ** (xem §3) | — |
| `0.0.0.0:443/10443` | link log UAT/PILOT (stream TCP → `10.22.17.219:10443`) | như cũ |

## 1. Mở lại Tailscale (node `vbsme-log-gw`, IP đọc từ state)

```bash
# đọc danh tính cũ: state volume `tailscale-state` phải còn (teardown cố ý KHÔNG xoá)
docker run -d --name tailscale --net=host --cap-add NET_ADMIN --cap-add NET_RAW \
  --device=/dev/net/tun \
  -e TS_HOSTNAME=vbsme-log-gw \
  -e TS_STATE_DIR=/var/lib/tailscale \
  -e TS_USERSPACE=false \
  -e TS_AUTHKEY="$(cat ~/.hermes/state/tailscale_authkey.txt)" \
  -v tailscale-state:/var/lib/tailscale \
  tailscale/tailscale:latest
```

Thiếu `TS_STATE_DIR` / `TS_USERSPACE=false` ⇒ state nằm trong RAM, node tự tạo machine key mới mỗi
lần restart (đã từng gây 28 restart + IP đổi). Node vào tailnet xong thì ghi IP mới:

```bash
docker exec tailscale tailscale ip -4 | head -1 > ~/.hermes/state/tailnet_ip.txt
```

## 2. Bind lại cổng nói + gateway vào IP mới

- Cổng nói `siri_speak.py` đọc IP động qua `_tailnet_ip()` ⇒ chỉ cần nạp lại unit:
  `systemctl --user kill -s TERM siri-speak` rồi chờ ≥9s (guard chặn `restart`; `Restart=always` tự dựng lại).
- Gateway `:9443` bind IP lúc khởi động ⇒ phải restart gateway: gọi claude đọc `~/.hermes/scripts/gw_restart.txt`
  (hẹn `systemd-run` tách rời rồi restart — KHÔNG tự restart từ trong gateway).
- Đổi Shortcut iPhone nếu IP đổi: `http://<tailnet_ip>:9444/siri/say`, header `X-Gitlab-Token`, ô
  *Get Dictionary Value* key `text`. Dùng tên MagicDNS (`<node>.<tailnet>.ts.net`) thì không phải sửa nữa.

## 3. Cầu nối dịch vụ nội bộ qua nginx — **ĐÃ BỎ, đừng tự dựng lại**

Hoàng chốt bỏ cả 2 route (`git.vnpay.vn` + `console-cmc-test-rke03…`): dịch vụ nội bộ đi qua proxy gãy
ngay ở bước SSO/redirect (IdP `s2o.vnpay.vn` callback về tên miền thật; GitLab cũng cùng kiểu) ⇒ **nginx proxy
không phải đường đi cho loại dịch vụ này**. Config `omni-sme-proxy` đã trả về nguyên trạng, khối `stream` TCP
link log UAT/PILOT giữ nguyên. Recipe dưới đây chỉ còn giá trị tham chiếu — **không tự thêm lại vào nginx của anh**.

Nếu được yêu cầu dựng lại:
File: `/home/zane/Desktop/notes/tricks/omni-sme-proxy/nginx.conf` (bind-mount → `/etc/nginx/nginx.conf`
của container `omni-sme-proxy`, network host, restart policy always). Hai server `http` listen `9445`/`9446`,
`allow 100.64.0.0/10; allow 127.0.0.1; deny all;`, `access_log off`, upstream resolve động
(`resolver 127.0.0.53` + `proxy_pass https://$up$uri...`), `proxy_ssl_verify off`,
`proxy_redirect https://$up/ /`, `proxy_cookie_domain ~\.<domain> $host`.

Vì bind `0.0.0.0` + allow-list CGNAT nên: Tailscale tắt vẫn start bình thường, LAN vào bị 403, tailnet vào OK.
Kiểm tra: `~/.hermes/scripts/tunnel_bridge_check.sh`.

### ⚠️ Bẫy bind-mount theo inode — bẫy CHUNG cho mọi config bind-mount, không riêng nginx

Bind-mount **file** gắn theo **inode**, không theo path. Sửa file bằng cách ghi-thay-inode (tạo file mới rồi rename/atomic-write —
rất nhiều tool làm vậy, kể cả tool `patch`) ⇒ **container vẫn đọc inode cũ**, `nginx -s reload` xong config mới
KHÔNG có hiệu lực mà `nginx -t` vẫn báo ok (vì nó test file trong container = bản cũ).

Cách xử lý:
1. Ghi **tại chỗ** để giữ inode: `python3 -c "import shutil; shutil.copyfile('/tmp/new.conf','<path>')"`
   (kiểm: `stat -c %i <path>` trước/sau phải giống nhau).
2. Đối chiếu container có thấy bản mới: `docker exec <ct> grep -c '<dấu hiệu mới>' /etc/nginx/nginx.conf`.
3. Chỉ `nginx -s reload` (không downtime).
4. Nếu đã lỡ thay inode rồi: `docker restart <ct>` để nó gắn lại theo path, rồi mới reload được.

Trước mọi thay đổi trên nginx phục vụ link log của tester: **backup file trước** (bản gốc để ở
`~/.hermes/etc/nginx-tunnel/omni-backup-*.conf`) và validate bản mới bằng container rác **cùng image với
container đang chạy** (`docker run --rm --net=host -v /tmp/new.conf:/etc/nginx/nginx.conf:ro "$IMG" nginx -t`)
— image khác có thể lệch `include`/module nên `nginx -t` sẽ nói dối.

## 4. Điểm cần biết

- Teardown 17h30 (hoặc giờ Hoàng đặt) chỉ cần `tailscale down` + `docker rm` (GIỮ volume `tailscale-state`).
- Cầu nối `:9445/:9446` **đã bỏ**; nếu có dựng lại thì nó tự vô hiệu khi Tailscale xuống (allow-list CGNAT) — không cần tắt riêng.
- Dịch vụ login bằng SSO trỏ về tên miền thật (console qua `s2o.vnpay.vn`, GitLab cũng vậy) ⇒ proxy nginx KHÔNG đủ.
  Đừng dựng lại route: đường đúng là **subnet router** của Tailscale (advertise dải mạng + split DNS) — cần Hoàng
  duyệt route trong admin console.
