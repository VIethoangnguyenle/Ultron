# Vòng đời Tailscale gateway (node vbsme-log-gw)

## Luật (Hoàng chốt 2026-09-12)
- **Mọi kết nối Tailscale tắt sau 17h30**, không ngoại lệ qua đêm.
- **Log Tailscale phải bị xoá khỏi hệ thống** — không để lại dấu vết đường vào.
- Không tự bật lại; chỉ bật khi Hoàng yêu cầu.

## Cưỡng chế tự động
- `~/.hermes/schedules.yaml` → action `tailscale-teardown`, `when: "17:30"`, **mỗi ngày**
  (không dùng `date:` nữa; bản one-shot cũ đã bỏ).
- Script: `~/.hermes/scripts/tailscale_teardown.py`
  - `--dry-run`: chỉ in ra sẽ xoá gì (luôn chạy cái này trước khi tin script).
  - `--no-notify`: không DM Hoàng.
  - Việc làm: `docker exec tailscale tailscale logout` → `docker stop` → `docker rm -v`
    (xoá luôn log json của container) → `docker volume rm tailscale-state` → xoá/scrub file log.
- Chạy lại nhiều lần vô hại (idempotent); container không tồn tại → vẫn dọn log sót.

## Dọn log — phạm vi đúng
- Quét `/tmp`, `~/.hermes`, `~/.hermes/{reports,logs,state}` cho file `.log .txt .out .err`.
- Dấu vết nhận diện: `100.120.110.26`, `vbsme-log-gw`, `tailscale`, `Tailscale`, `tailscaled`.
- File toàn dòng dấu vết → xoá hẳn; file lẫn → lọc bỏ đúng những dòng đó.
- **KHÔNG BAO GIỜ** đụng: `webhook_subscriptions.json` (route Siri), `siri_token.txt`,
  `config.yaml`, `state.db`, `~/.hermes/scripts/*`, `~/.hermes/skills/*` — mất là mất luôn
  khả năng bật lại. (Dry-run 2026-09-12 từng định scrub `webhook_subscriptions.json` → đã chặn
  bằng `SCAN_SUFFIXES` chỉ nhận file log + `PROTECTED_NAMES`.)

## Hệ quả cần nhớ trước khi hứa
- Cổng Siri bridge (`hermes webhook` bind vào IP tailnet) **chết theo** sau 17h30.
- Đường đọc log UAT/LIVE cho tester ở nhà cũng chết theo.
- Webhook adapter chỉ log lỗi bind chứ không làm sập gateway → tắt Tailscale an toàn cho Hermes.

## Bật lại (khi Hoàng yêu cầu)
Dựng lại container Tailscale theo hướng dẫn ở SKILL.md, `tailscale up` lại, rồi khởi động lại
`hermes-gateway` để cổng webhook bind lại vào IP tailnet. Mở private cho đúng người được cấp.
