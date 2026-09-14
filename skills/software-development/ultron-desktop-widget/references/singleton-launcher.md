# Widget desktop phải là SINGLETON (một icon duy nhất)

## Triệu chứng đã gặp thật (2026-09-14)

Hoàng gửi ảnh màn hình hoa lá + 2 icon tròn xanh cười: *"Sao trên màn hình anh lắm Icon thế"*.
Nguyên nhân: widget bị khởi động **2 lần lệch 14 giây**, mỗi lần vẽ 1 icon:

| Nguồn | Ghi nhận qua |
|---|---|
| `systemd --user` (unit `ultron-widget.service`, enabled) | ppid = `/lib/systemd/systemd --user` |
| `gnome-shell` khôi phục phiên làm việc cũ | ppid = `/usr/bin/gnome-shell`, scope `app-gnome-ultron\x2dwidget-<pid>.scope` |

⇒ **Giữ systemd làm nguồn duy nhất**, và chặn mọi nguồn khác bằng guard trong `run.sh`.

## Guard đã cài trong `~/ultron-widget/run.sh`

1. `flock -n` trên một file lock (chống race khi 2 lần gọi cùng lúc).
2. `pgrep -u "$(id -u)" -f 'python[^ ]*[[:space:]]+([^[:space:]]*/)?ultron_widget\.py'` → có thì in 1 dòng + `exit 0`.
3. `ULTRON_WIDGET_FORCE=1` để bỏ qua guard khi cần debug.

**Đừng dùng `pgrep -f ultron_widget.py` trần** — nó khớp cả command line của shell/agent có chứa chuỗi đó
(đo được 4 tiến trình nhiễu) ⇒ sẽ khoá cứng launcher vĩnh viễn. Phải neo vào **trình thông dịch** như pattern trên.

## Pitfall khi KIỂM CHỨNG (đã tự sập bẫy)

- Chạy `timeout 30 ./run.sh` khi **không** có widget nào → nó **khởi động widget thật**, rồi `timeout`
  giết luôn ⇒ icon biến mất khỏi màn hình người dùng. Muốn test đúng: để 1 widget đang chạy rồi mới gọi
  `./run.sh` (phải thấy dòng "bỏ qua lần gọi này" + số tiến trình không đổi).
- Sau mọi lần test, kiểm tra lại `systemctl --user is-active ultron-widget` và **bật lại nếu inactive**:
  `systemctl --user start ultron-widget.service` (rồi `pgrep -af 'python.*ultron_widget\.py'` để xác nhận).
- Đếm tiến trình cho chuẩn: `pgrep -c -f 'python.*ultron_widget\.py'` (đừng đếm `pgrep -af ... | grep -vc sh -c`).

## Vị trí liên quan

- Unit: `~/.config/systemd/user/ultron-widget.service` (enabled → tự lên khi đăng nhập).
- Launcher: `~/ultron-widget/run.sh`; desktop entry `~/.local/share/applications/ultron-widget.desktop`.
- Trạng thái widget: `~/.config/ultron-widget/state.json`; log có dòng "icon 48px hiển thị tại (x,y)".
- Hotkey toµn cục: `ctrl+alt+u`.

## Nút thoát (thêm 2026-09-14 theo yêu cầu Hoàng)

Hoàng: *"Ở Icon phải có 1 nút exit dấu x nhỏ để anh dễ thoát chứ"*. Đã thêm 2 đường thoát:

| Chế độ | Đường thoát |
|---|---|
| TEXT (có panel) | nút `×` góc trên phải thanh tiêu đề (cạnh nút `—` thu nhỏ) |
| Mọi chế độ (kể cả VOICE) | chuột phải vào icon → menu có mục **"Thoát Ultron"** (cạnh "Mở/Đóng chat") |

**Gotcha:** ở `mode: voice` (state `~/.config/ultron-widget/state.json`) **panel không tồn tại** ⇒ nút `×`
không với tới được, phải thoát bằng menu chuột phải. Khi kiểm chứng nút `×` phải chuyển sang TEXT trước.

Thoát = `exit 0` (unit `ultron-widget.service` để yên, không hồi). Bật lại: `systemctl --user start ultron-widget.service`.
Sau khi sửa code widget phải **restart service** mới áp dụng — bản đang chạy là mã cũ cho tới lúc đó.
Ảnh panel để gửi bằng chứng: chụp riêng cửa sổ bằng `QWidget.grab()` (đừng chụp toàn màn hình).
Thay đổi nằm ở `ui.py` (nút ×, menu) + `ultron_widget.py` (log/hành vi thoát), test ở `tests/verify_exit_button.py`.
