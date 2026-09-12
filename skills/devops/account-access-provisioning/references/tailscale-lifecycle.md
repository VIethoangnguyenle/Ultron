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
  - Việc làm: `tailscale down` (**KHÔNG** `logout`) → `docker stop` → `docker rm` (GIỮ volume
    `tailscale-state`) → scrub file log. `logout`/`docker rm -v` làm mất danh tính node ⇒ lần bật lại
    sau sinh node mới + IP mới, phải sửa lại SOUL/skill/Shortcut; giữ state thì tái dùng được node + IP cũ.
- Chạy lại nhiều lần vô hại (idempotent); container không tồn tại → vẫn dọn log sót.

## Dọn dấu vết log — phạm vi đúng

Hai đường dọn: (a) teardown hằng ngày (`tailscale_teardown.py`, tự scrub trong `purge_traces`);
(b) lượt dọn theo yêu cầu *"xoá toàn bộ log hệ thống về việc X"* → `~/.hermes/scripts/scrub_matter_logs.py`
(**mặc định dry-run**, `--apply` mới xoá; đổi danh sách marker ở đầu file để dùng cho việc khác).

- Marker nhận diện: `tailscale/Tailscale/tailscaled`, `vbsme-log-gw`, IP tailnet (đọc động) + IP node cũ,
  **`tskey-`** (auth key), `siri-speak`/`siri_speak`, và tên miền nội bộ đã đưa ra ngoài.
- **Đừng lấy chuỗi số trần (`9443`, `9444`…) làm marker** — khớp bừa vào báo cáo deliverable và file dump JSON,
  cắt mất nội dung thật. Dùng tên miền / tên unit / IP đầy đủ.
- **Log xoay vòng `agent.log.1` có suffix `.1`** ⇒ lọc theo `.log` sẽ bỏ sót đúng bản cũ; nhận theo tên chứa `.log.`.
  File log lớn (≥5MB) bị cap kích thước ⇒ phải xử lý theo kiểu stream từng dòng.
- `~/.hermes/logs/process-results/proc_*.json` (cache kết quả tool) dính dấu vết ⇒ **xoá cả file**; cắt 1 dòng
  trong JSON blob là hỏng cấu trúc mà chẳng giữ được gì.
- `~/.hermes/reports/**` là **deliverable**, KHÔNG phải log — không quét.
- File toàn dòng dấu vết → xoá hẳn; file lẫn → lọc bỏ đúng những dòng đó. Scrub xong **rà lại** bằng
  `grep -rlE '<marker>' <các root>` phải ra rỗng rồi mới được nói "sạch".
- **KHÔNG BAO GIỜ** đụng: `webhook_subscriptions.json` (route Siri), `siri_token.txt`, `tailscale_authkey.txt`
  (cần để bật lại), `config.yaml`, `state.db`, `schedules.yaml`, `scripts/`, `skills/` — mất là mất luôn
  khả năng bật lại. (Dry-run từng định scrub `webhook_subscriptions.json` → đã chặn bằng giới hạn suffix
  file log + danh sách `PROTECTED_NAMES`.)
- **Ngoài tầm tay (cần root, không có sudo):** systemd journal (`sudo journalctl --rotate --vacuum-time=1s`),
  `/var/log/{syslog,kern.log}`, log của docker daemon. Log *container* Tailscale mất cùng container khi `docker rm`.
  Báo thẳng phần này thay vì để Hoàng tưởng đã sạch.
- **Auth key lộ trong log ⇒ scrub xong vẫn phải nhắc Hoàng revoke/regenerate** trên admin Tailscale
  (`login.tailscale.com/admin/settings/keys`) rồi ghi key mới vào `~/.hermes/state/tailscale_authkey.txt` (600).

## Hệ quả cần nhớ trước khi hứa
- Cổng Siri bridge (`hermes webhook` bind vào IP tailnet) **chết theo** sau 17h30.
- Đường đọc log UAT/LIVE cho tester ở nhà cũng chết theo.
- Webhook adapter chỉ log lỗi bind chứ không làm sập gateway → tắt Tailscale an toàn cho Hermes.

## Bật lại (khi Hoàng yêu cầu)
Dựng lại container Tailscale theo hướng dẫn ở SKILL.md, `tailscale up` lại, rồi khởi động lại
`hermes-gateway` để cổng webhook bind lại vào IP tailnet. Mở private cho đúng người được cấp.
