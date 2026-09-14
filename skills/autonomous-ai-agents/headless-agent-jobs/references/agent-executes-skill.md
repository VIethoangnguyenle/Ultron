# Làm agent headless TỰ THỰC THI một skill/workflow

Đã kiểm chứng thật: cùng một việc build graph hiểu-nguồn (Understand-Anything), slash command thất bại còn
cách "đọc file skill rồi tự chạy" thành công.

## Vì sao slash command không dùng được trong print mode

`agy --print "/understand <repo>"` → output là một đoạn tóm tắt kiến trúc kèm câu hỏi lại, exit 0 trong <60s,
`.ua/` không được sinh, không có `[Phase N/7]`. Thêm chữ phía sau slash command cũng không cứu được.
Cờ `--disable-slash-commands` trong `--help` ngụ ý mặc định CÓ expand — nhưng thực tế print mode không chạy
workflow của skill. Đừng suy luận từ help, hãy thử và kiểm tra có artifact mới hay không.

## Prompt mẫu (agy)

```bash
cd <repo> && timeout 20000 agy --model gemini-3.1-pro-high --effort high --print-timeout 300m \
  --dangerously-skip-permissions -p "Đọc kỹ file /home/zane/.agents/skills/understand/SKILL.md và thực thi \
  TOÀN BỘ workflow Understand-Anything cho repo: <repo> . Repo đã có .ua/ dở dang (config.json, tmp/, \
  intermediate/) - hãy RESUME từ chỗ dở, KHÔNG làm lại từ đầu. Ngôn ngữ output: vi. Dùng công cụ shell/node \
  của bạn để chạy các script trong skill. KHÔNG hỏi lại, tự quyết mọi bước, hoàn thành cả 7 phase tới khi \
  sinh ra .ua/knowledge-graph.json và .ua/meta.json." > /tmp/ua_<repo>_agy.log 2>&1
```

Ba ý bắt buộc trong prompt, thiếu ý nào cũng trượt: (a) ĐỌC file `SKILL.md`; (b) DÙNG shell/node để chạy
script trong skill; (c) RESUME từ phần dở. Thêm mô tả quy mô repo ("repo lớn, chia nhỏ xử lý có hệ thống")
giúp nó không làm ẩu.

## Thông số agy

- `--effort low|medium|high` = mức suy luận (thứ người dùng gọi là "agy reasoning").
- `--print-timeout 300m` + `timeout 20000` ở ngoài: hai lớp chặn để run không treo vô hạn.
- `--model gemini-3.1-pro-high`: nhóm model còn quota.
- **Redirect ra file rồi đọc lại** (`> /tmp/x.log 2>&1`), ĐỪNG pipe qua `head`/`tail` — pipe làm agy nuốt
  sạch output (exit 0 nhưng rỗng).

## Biến thể engine khác

- codex: `codex exec --sandbox danger-full-access "<prompt đọc SKILL.md + thực thi>"` — hiểu chỉ thị file-skill
giống agy; hạn mức theo tháng nên chỉ dùng khi còn quota.
- claude: nối skill vào `~/.claude/skills/` bằng symlink rồi `claude -p "/understand <repo> --language vi \
  --no-auto-update  Chạy full repo này, KHÔNG hỏi lại, tự quyết và hoàn thành cả 7 phase." \
  --dangerously-skip-permissions` (slash command ở đây CÓ tác dụng).
- Cả 3 đều chạy nền: `background=true, notify=true`, log riêng từng run.

## Dấu hiệu phân biệt "chạy thật" vs "chat suông"

Đang chạy thật: có tiến trình con (`agy.real`), `tmp/` `intermediate/` sinh file mới dần, log có nhắc phase,
file kết quả tăng kích thước. Chat suông: exit 0 sau vài chục giây, chỉ có một đoạn văn tóm tắt, không file mới.

## Artifact của pipeline UA: `.trash-*` là bình thường

Khi graph assemble xong, `tmp/` và `intermediate/` bị move vào `.ua/.trash-<epoch>/`. Thấy chúng "biến mất"
là dấu hiệu run ĐÃ XONG, không phải mất dữ liệu — đừng hoảng và đừng khôi phục.
