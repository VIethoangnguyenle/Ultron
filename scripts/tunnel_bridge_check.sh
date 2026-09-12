#!/usr/bin/env bash
# Kiểm tra cầu nối 2 dịch vụ nội bộ ra tailnet (nằm trong nginx của Hoàng: omni-sme-proxy).
#   :9445 -> git.vnpay.vn (GitLab nội bộ)
#   :9446 -> console-cmc-test-rke03.backendofficetest.vn (console test)
# Không cần Tailscale đang bật mới chạy được test — chỉ để biết cầu có sống không.
set -uo pipefail
IP="$(cat "$HOME/.hermes/state/tailnet_ip.txt" 2>/dev/null | tr -d '[:space:]')"
[ -n "$IP" ] || { echo "chưa có IP tailnet trong ~/.hermes/state/tailnet_ip.txt"; exit 1; }

echo "cầu nối (proxy trong omni-sme-proxy):"
for p in 9445 9446; do
  ss -tln 2>/dev/null | grep -q ":$p " && echo "  :$p đang listen" || echo "  :$p KHÔNG listen  ← kiểm lại config nginx"
done
echo "gọi thử qua IP tailnet $IP:"
curl -s -o /dev/null -m 10 -w '  :9445 GitLab  -> HTTP %{http_code} %{redirect_url}\n' "http://$IP:9445/" || echo "  :9445 KHÔNG gọi được"
curl -s -o /dev/null -m 10 -w '  :9446 Console -> HTTP %{http_code} %{redirect_url}\n' "http://$IP:9446/" || echo "  :9446 KHÔNG gọi được"
echo "chặn mạng LAN (phải là 403):"
LAN="$(ip -4 -o addr show scope global 2>/dev/null | awk '$2!="tailscale0"{sub(/\/.*/,"",$4); print $4; exit}')"
[ -n "$LAN" ] && curl -s -o /dev/null -m 8 -w "  từ $LAN:9445 -> HTTP %{http_code}\n" "http://$LAN:9445/"
