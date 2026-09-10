---
name: ultron-scheduled-actions
description: Use when Ultron needs a scheduled task — edit the config.
---

# Việc định kỳ: sửa config, KHÔNG tạo cron job

## Nguyên tắc (Hoàng chốt 2026-09-10)
Mọi việc dạng "chạy lúc X", "mỗi sáng", "một lần vào ngày Y" → thêm một **action vào
`~/.hermes/schedules.yaml`**. **KHÔNG tạo cron job mới.**

Vì sao: mỗi job (nhất là one-shot) để lại một record trong `jobs.json` + delivery rows + file khoá
`.fire-*.lock`, và kéo theo cả lớp edge-case one-shot (catch-up window, dispatch claim,
"wedged one-shot removal", terminal record chờ retention sweep dọn). Dùng xong không ai dọn → rác
trong `~/.hermes/cron/`. Một dispatcher + một file config thì: thêm việc = 1 dòng, tắt việc =
`enabled: false`, one-shot **tự hết hạn** nên không bao giờ thành rác.

Ngoại lệ: việc cần một *session LLM* (đọc/nghĩ/sinh nội dung) vẫn phải là cron job thật —
dispatcher chỉ chạy script. Việc thuần script/định kỳ thì dùng config.

## Cấu trúc
- Config: `~/.hermes/schedules.yaml` — danh sách action
- Dispatcher: `~/.hermes/scripts/daily_dispatch.py`
- Cron duy nhất: **`ultron-daily`** (every 2m, `no_agent`, script=`daily_dispatch.py`, deliver=local)
- State: `~/.hermes/schedules.state.json` — `{id: {date, tries, ok, alerted}}`
- Log: `~/.hermes/cron/dispatch.log`; lỗi → `~/.hermes/escalations/` (cron escalate chuyển cho Hoàng)

## Lệnh
```bash
P=~/.hermes/hermes-agent/venv/bin/python
$P ~/.hermes/scripts/daily_dispatch.py --list      # lịch + kết quả hôm nay
$P ~/.hermes/scripts/daily_dispatch.py --dry-run   # xem sẽ chạy gì, không đổi gì
$P ~/.hermes/scripts/daily_dispatch.py --run <id>  # chạy ngay 1 action
$P ~/.hermes/scripts/daily_dispatch.py --prune     # liệt kê action hết hạn/đang tắt (KHÔNG tự xoá)
```

## Trường của một action
`id` (bắt buộc), `when` "HH:MM", `script`, `args`, `enabled`, `days` [mon..sun],
`date` (one-shot đúng ngày), `until` (hết hạn), `retry` (số lần thử/ngày, mặc định 1),
`catch_up_minutes` (mặc định 120 — gateway down lúc tới giờ thì vẫn chạy khi còn trong cửa sổ).

## Pitfalls (đã dính thật)
- **Phải ghi nhận cả lần LỖI vào state.** Nếu chỉ ghi khi thành công, action lỗi sẽ chạy lại mỗi
  tick (2 phút/lần) và tạo một file escalation mỗi lần → spam. Thiết kế hiện tại: thử tối đa
  `retry` lần/ngày, và **báo lỗi đúng 1 lần/ngày**.
- **`HERMES_HOME` là con dao hai lưỡi.** Khi test với `HERMES_HOME=<tmp>`, nhớ `unset HERMES_HOME`
  sau đó — biến còn sót trong session làm các lệnh sau đọc nhầm config test (đã dính 1 lần).
- **Test an toàn:** luôn test bằng `HERMES_HOME` trỏ thư mục tạm, để không gửi gì ra group và
  không ghi escalation thật về DM Hoàng.
- **`no_agent` + stdout:** stdout rỗng = không gửi gì; có stdout = gửi tới `deliver`. Dispatcher
  cố tình im lặng khi không có việc — giữ đúng kiểu watchdog.
- **Quyết định phải dựa trên 'ngày đang xét', không phải `date.today()`.** Hàm xét state mà gọi
  `date.today()` bên trong sẽ bất đồng với `now` truyền vào → khi mô phỏng ngày khác, action *đã
  chạy* vẫn báo "tới giờ" (test giả xanh, đã dính). Truyền `today` vào thay vì đọc đồng hồ hệ thống.
- **Đổi máy:** `schedules.yaml` đã được thêm vào `~/Ultron/sync.py`, nếu tạo file config mới ở
  cấp thư mục `~/.hermes/` thì kiểm tra lại sync, không là mất khi restore.
