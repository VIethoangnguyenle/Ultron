#!/usr/bin/env bash
# E2E THAT cho widget Ultron: "nguoi dung noi" 1 cau qua loa -> mic -> STT -> cong -> doc to.
# Chay duoc khi man hinh KHOÁ (khong can chuot/phim). Da chay dat that.
# Bang chung: log widget (journalctl -u we2e) + ban ghi monitor.
set -u
export DISPLAY=:0
REPO=/home/zane/ultron-widget
UNIT=we2e
cd "$REPO" || exit 1

# 0) don tien trinh cu
systemctl --user stop "$UNIT" 2>/dev/null
pkill -f ultron_widget.py 2>/dev/null; sleep 2

# 1) cau hoi mau bang giong noi that
python3 - <<'PY'
import asyncio, edge_tts
async def main():
    c = edge_tts.Communicate("Ultron, may gio roi?", "vi-VN-NamMinhNeural")
    await c.save("/tmp/q.mp3")
asyncio.run(main())
PY
ffmpeg -y -loglevel error -i /tmp/q.mp3 -ar 16000 -ac 1 /tmp/q.wav || exit 1

# 2) VAT am luong toi da: duong loa -> khong khi -> mic rat yeu
pactl set-sink-volume @DEFAULT_SINK@ 100%
pactl set-source-volume @DEFAULT_SOURCE@ 100%

# 3) thu monitor TRUOC khi lam gi
MON=$(pactl list short sources | awk '/monitor/{print $2; exit}')
timeout 90 parec -d "$MON" --file-format=wav /tmp/e2e_rec.wav >/dev/null 2>&1 &
REC=$!

# 4) widget tu mo 1 luot noi (~0.8s sau khi len)
systemd-run --user --unit="$UNIT" --collect \
  -p WorkingDirectory="$REPO" \
  -p 'Environment=DISPLAY=:0 ULTRON_AUTOSTART_VOICE=1' \
  ./.venv/bin/python ultron_widget.py || exit 1

# 5) PHAT CAU HOI TRONG CUA SO NGHE (~+4s). Qua ~8s im la luot tu dong lai = test truot vi timing.
sleep 4
paplay --volume=65536 /tmp/q.wav

# 6) doi STT -> cong -> TTS -> doc xong (cong tra loi ~5s, TTS vai giay)
sleep 30
systemctl --user stop "$UNIT" 2>/dev/null; sleep 2; wait $REC 2>/dev/null

# 7) bang chung
ffmpeg -i /tmp/e2e_rec.wav -af volumedetect -f null - 2>&1 | grep -E "mean_volume|max_volume"
journalctl --user -u "$UNIT" --no-pager 2>/dev/null | tail -40

# 8) TRA LAI gain mic — de 100% se nang san nhieu (~2600) va nuot cau noi nho
pactl set-source-volume @DEFAULT_SOURCE@ 70%
echo "XONG. Ky vong trong log: mo mic -> ghi am xong ... co tieng noi -> STT text -> cong tra N ky tu -> face speaking -> paplay -> mo mic lai."
