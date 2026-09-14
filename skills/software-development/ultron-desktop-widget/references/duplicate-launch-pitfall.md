# Pitfall: widget bị khởi động trùng ⇒ nhiều icon nổi trên desktop

## Triệu chứng

Hoàng thấy "lắm icon" tròn xanh cười trên màn hình — thực tế là **2 tiến trình widget cùng chạy**,
mỗi tiến trình vẽ 1 icon.

## Nguyên nhân đã gặp thật

Hai nguồn cùng khởi động widget, lệch nhau vài giây:

| Nguồn | Cách nhận biết |
|---|---|
| systemd user unit `ultron-widget.service` | ppid = `/lib/systemd/systemd --user` |
| gnome-shell khôi phục phiên làm việc cũ | ppid = `/usr/bin/gnome-shell`, kèm scope `app-gnome-ultron\x2dwidget-<pid>.scope` |

Bản systemd là bản chính thức (bật/tắt được, tự hồi khi chết) ⇒ **giữ bản systemd, tắt bản gnome-shell**.

## Cách xử lý

1. Đếm cho chắc (đừng tin `pgrep -fc` trần — nó khớp cả shell bọc lệnh):
   `ps -eo pid,ppid,lstart,cmd | grep ultron_widget.py | grep -v grep`.
2. Giữ bản do systemd quản, `kill <pid>` bản do gnome-shell.
3. Chống lặp lại ở gốc: `run.sh` phải có **guard chống chạy trùng** (thoát ngay nếu đã có tiến trình
   `ultron_widget.py` đang chạy) **+ `flock`** chống race khi 2 nguồn gọi cùng lúc. Chỉ thêm guard,
   không đổi hành vi khác của `run.sh`; để `ULTRON_WIDGET_FORCE=1` bỏ qua guard khi cần debug.

## Ranh giới

Khi sửa widget: KHÔNG đụng `~/.hermes` (config/scripts/schedules), KHÔNG restart gateway,
KHÔNG đụng 2 unit `siri-speak`/`siri-chat`, KHÔNG sửa `ultron-widget.service`.
