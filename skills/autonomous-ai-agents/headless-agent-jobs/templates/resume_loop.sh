#!/bin/bash
# Hẹn chạy tiếp job agent headless qua mốc hạn mức, lặp tới khi xong — thay cho việc nhớ bằng đầu.
#
# Dùng: sửa RESET_HHMM, danh sách repo + file đánh dấu hoàn thành, và engine command.
# Chạy nền: terminal(background=true, notify=true).
set -u

RESET_HHMM="2112"          # mốc reset hạn mức, dạng HHMM
LOG=/tmp/resume_loop.log

# (1) đợi mốc reset
while [ "$(date +%H%M)" -lt "$RESET_HHMM" ]; do sleep 60; done

# (2) guard: đang có run khác ghi cùng chỗ thì bỏ lượt này, đừng thành writer thứ hai
if pgrep -f "codex exec" >/dev/null || pgrep -f "agy.real" >/dev/null || pgrep -f "claude -p" >/dev/null; then
  echo "co run khac dang chay — bo luot nay $(date)" >> "$LOG"; exit 0
fi

for i in 1 2 3 4 5 6; do
  for R in /path/repo-a /path/repo-b; do
    ART="$R/.ua/knowledge-graph.json"
    [ -f "$ART" ] && { echo "skip $R (da co artifact) $(date)" >> "$LOG"; continue; }
    ( cd "$R" && timeout 17000 claude -p "/understand $R --language vi --no-auto-update Chay full repo nay, KHONG hoi lai, tu quyet va hoan thanh ca 7 phase." \
        --dangerously-skip-permissions >> "/tmp/resume_$(basename "$R").log" 2>&1 )
    echo "attempt $i $R exit=$? $(date)" >> "$LOG"
  done
  [ -f /path/repo-a/.ua/knowledge-graph.json ] && [ -f /path/repo-b/.ua/knowledge-graph.json ] \
    && { echo "ALL DONE $(date)" >> "$LOG"; break; }
  sleep 3600
 done
