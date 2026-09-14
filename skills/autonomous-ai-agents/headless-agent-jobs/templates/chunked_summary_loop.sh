#!/bin/bash
# Vá field summary cho artifact lớn (graph UA) theo TỪNG MODULE.
#
# Vì sao không chạy 1 lượt: ~10k mục trong một run ⇒ OOM-kill (exit 137), nội dung vẫn là template rác.
# Mỗi lượt ≤ ~1.600 mục; chạy tuần tự; mỗi lượt backup trước, chỉ sửa field cho phép, ghi temp rồi rename.
#
# Dùng: sửa REPO + mảng chunks (thư mục module cấp 1) rồi: bash chunked_summary_loop.sh
# Chạy nền: terminal(background=true, notify=true).
set -u

REPO="/path/to/repo"
KG="$REPO/.ua/knowledge-graph.json"
LOG="/tmp/ua_summaries.log"

cp -n "$KG" "/tmp/kg_backup_before_summaries.json"   # backup TRƯỚC khi sửa
cd "$REPO" || exit 1

# Mỗi dòng = 1 lượt. Gom module nhỏ lại, đừng để lượt nào vượt ~1.600 mục.
chunks=(
  "module-lon-nhat"
  "module-lon-thu-2"
  "module-vua"
  "module-nho-1 module-nho-2 module-nho-3"
)

for c in "${chunks[@]}"; do
  echo "=== CHUNK [$c] $(date) ===" >> "$LOG"
  timeout 5400 agy --model gemini-3.1-pro-high --effort high --print-timeout 90m \
    --dangerously-skip-permissions -p "Repo: $REPO . File .ua/knowledge-graph.json đang có mô tả (summary) dạng template rác cho nhiều node. NHIỆM VỤ: viết lại summary TIẾNG VIỆT THẬT cho TẤT CẢ node có filePath thuộc các module: $c . Với mỗi file trong module đó, đọc code thật rồi viết mô tả 1-2 câu nêu đúng chức năng/nghiệp vụ cụ thể (KHÔNG lặp lại tên class, KHÔNG dạng 'Lớp X cung cấp cấu trúc và phương thức cho X.java'). CHỈ được sửa trường summary của các node thuộc module được giao; TUYỆT ĐỐI không đổi id, không thêm/bớt node hay edge. Ghi ra file tạm rồi rename đè lên .ua/knowledge-graph.json (không ghi trực tiếp để tránh hỏng file). KHÔNG hỏi lại, tự quyết mọi bước, làm hết các node được giao." >> "$LOG" 2>&1
  echo "exit=$? $(date)" >> "$LOG"
done
echo "ALL DONE $(date)" >> "$LOG"
# Xong mới báo hoàn thành: python3 scripts/verify_ua_graph.py "$REPO/.ua"
