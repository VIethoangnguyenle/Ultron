#!/bin/bash
# Doi cong webhook (cho Siri goi vao) song lai, roi tu test route /webhooks/siri va bao DM Hoang.
# Chay TACH ROI qua systemd-run nen song duoc qua lan gateway khoi dong lai.
set -u
unset HERMES_HOME
TSIP=100.82.132.36
PORT=9443
REP=/home/zane/.hermes/reports/siri_bridge_report.txt
TOK=$(cat /home/zane/.hermes/state/siri_token.txt)
mkdir -p /home/zane/.hermes/reports
: > "$REP"
say() { echo "[$(date '+%F %T')] $*" >> "$REP"; }

say "start: doi cong webhook http://$TSIP:$PORT/health (toi da ~8 phut)"
CODE=000
for i in $(seq 1 96); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "http://$TSIP:$PORT/health" 2>/dev/null || echo 000)
  if [ "$CODE" = "200" ]; then say "health -> 200 sau ${i} lan thu (~$((i*5))s)"; break; fi
  sleep 5
done
[ "$CODE" = "200" ] || say "FAIL: health khong len sau ~8 phut (code cuoi=$CODE)"

say "--- test 1: POST co token (ky vong 200/202)"
curl -s -i --max-time 30 -X POST "http://$TSIP:$PORT/webhooks/siri" \
  -H 'Content-Type: application/json' -H "X-Gitlab-Token: $TOK" \
  -d '{"text":"ping test cong Siri bridge - tra loi dung 1 cau xac nhan ngan."}' >> "$REP" 2>&1

say "--- test 2: POST KHONG token (phai bi chan, khac 2xx)"
curl -s -o /dev/null -w 'no-token -> %{http_code}\n' --max-time 30 -X POST "http://$TSIP:$PORT/webhooks/siri" \
  -H 'Content-Type: application/json' -d '{"text":"x"}' >> "$REP" 2>&1

say "--- test 3: body sai dinh dang JSON (xem co ra 400 khong)"
curl -s -o /dev/null -w 'bad-json -> %{http_code}\n' --max-time 30 -X POST "http://$TSIP:$PORT/webhooks/siri" \
  -H 'Content-Type: application/json' -H "X-Gitlab-Token: $TOK" -d 'khong-phai-json' >> "$REP" 2>&1
say "done"

{
  echo "Cổng cho Siri đã test xong anh 👋"
  echo
  echo "• health: $CODE"
  grep -E "^(no-token|bad-json|HTTP/1.1)" "$REP" | head -8
  echo
  echo "Chi tiết đầy đủ: /home/zane/.hermes/reports/siri_bridge_report.txt"
} > /tmp/siri_ping_msg.txt
python3 /home/zane/.hermes/scripts/gchat_send_text.py --space spaces/0dniIqAAAAE --text-file /tmp/siri_ping_msg.txt >> "$REP" 2>&1 || say "FAIL: gui DM"
