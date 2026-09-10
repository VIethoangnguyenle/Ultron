---
name: team-people
description: "Use when Ultron works with or mentions a colleague."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [people, team, memory, google-chat, relationships]
    related_skills: [google-chat-setup, agent-space-knowledge]
---

# Team people registry — ai là ai, và mình đã làm gì với họ

Cơ chế nhớ **con người** (không phải nhớ dữ liệu): id Google Chat → tên, chức danh, cách xưng hô,
nhóm nào, và những gì Ultron đã học được qua từng lần làm việc. Đây là nền tảng để xây kết nối
trong team: nhớ người ta là ai, đã nhờ gì, thích được nói thế nào.

## Store

`~/.hermes/people.json` (mode 600) — một file, mỗi người một entry:

```json
"users/110121981097849566202": {
  "name": "Hoàng, Nguyễn Lê Việt (KCN, DVNH)",
  "call": "Hoàng",              // cách gọi trong chat
  "role": "Backend engineer — SẾP của Ultron",
  "seat": "ROLE_MANAGER",       // từ Chat API khi có
  "type": "HUMAN|BOT",
  "groups": ["spaces/XXX (Label)"],
  "how": "Thân mật, hay đùa...",  // tông giọng / sở thích đã học được
  "tags": ["sep"],
  "first_seen": "2026-09-10",
  "notes": [{"at": "2026-09-10", "text": "..."}]
}
```

## Commands — `~/.hermes/scripts/people.py`

```bash
P="~/.hermes/hermes-agent/venv/bin/python ~/.hermes/scripts/people.py"
$P list [--group spaces/XXX] [--json]      # ai trong nhóm
$P show users/110121981097849566202        # 1 người: hồ sơ đầy đủ
$P note <id> "điều học được"                # append note có ngày
$P set  <id> --role "..." --how "..." --tag x
$P add  users/BOTID --name "Kitty (agent)" --type BOT --role "..." --how "..."
$P sync [--space spaces/X]                 # cập nhật thành viên từ các space đang theo dõi
```

- **Luôn tra bằng `users/<id>`** khi `note`/`set`: tên kiểu Việt hay trùng (nhiều "Hoàng"/"Nguyên").
  Tên chỉ để đọc cho người hiểu.
- `sync` cập nhật name/role/groups từ Chat API và **không bao giờ ghi đè `notes`/`how`**.
- **Bot/app KHÔNG xuất hiện trong `members.list`** → phải `add` tay (Kitty, Ultron đã add tay).

## Khi nào dùng

1. **Trước khi trả lời/mention một người trong group** mà chưa chắc họ là ai → `show`/`list`
   để biết tên thật, chức danh, cách gọi (anh/chị), và đã trao đổi gì.
2. **Có người mới xuất hiện** (id lạ trong group) → tra `list`, nếu chưa có thì `sync` để thêm.
3. **Sau mỗi lần làm việc với ai** và học được điều bền vững về họ → `note`. Tiêu chí ghi giống
   mục "Tự học khi được dạy trong group" trong SOUL.md: chức danh/vai trò, cách xưng hô, sở thích,
   điều họ đã nhờ, đính chính họ đã đưa. **Không** ghi chit-chat, không ghi thông tin cá nhân
   nhạy cảm (tuổi, địa chỉ, chuyện riêng), không ghi phán đoán/khen chê.

## Thói quen (habits) — do Ultron TỰ QUYẾT (Hoàng giao 2026-09-10)

Mỗi người có `habits`: `[{"text", "times", "first", "last"}]`. Ghi bằng:

```bash
$P habit <users/id> "mô tả thói quen"      # cùng nội dung -> tự tăng times + cập nhật last
```

**Tiêu chí của Ultron (đặt ra và tự chịu trách nhiệm):**

1. **≥ 2 lần quan sát riêng biệt mới gọi là thói quen.** Mới thấy 1 lần → ghi `note` kèm câu
   "mới 1 lần, theo dõi tiếp", chưa đưa vào `habits`. (Ngoại lệ duy nhất: một chuỗi lặp rõ ràng
   trong cùng một lần, ví dụ tự giới thiệu 3 lần trong 3 câu trả lời.)
2. **Chỉ ghi điều QUAN SÁT ĐƯỢC**, không suy đoán nội tâm, không quy kết động cơ.
3. **Tuyệt đối không ghi**: thông tin cá nhân nhạy cảm, đời tư, tin đồn, đánh giá tiêu cực
   kiểu "hay cáu", "làm việc lộn xộn". Thói quen ghi ra phải để **phục vụ họ tốt hơn**, không
   phải dán nhãn.
4. **Cập nhật khi thay đổi:** thấy lại → `habit` lại (tăng `times`). Nếu thói quen không còn
   đúng → ghi `note` nêu rõ "trước đây hay X, nay không còn", **không xoá lặng lẽ** (để tránh
   hiểu sai về sau).
5. **Dùng để hành xử, không để kể ra**: biết họ hay nhắn tin ngắn thì trả lời gọn; biết họ
   xưng chị → gọi đúng vai. Không bao giờ nói "vì hồ sơ ghi bạn hay...".

## Dùng hồ sơ để MENTION CHỦ ĐỘNG (mục đích chính — Hoàng nêu 2026-09-10)

Lý do Hoàng muốn Ultron nhớ mọi người: **để gọi được đúng người liên quan, không chỉ trả lời cái
người vừa @mention mình.** Biết ai là ai → biết việc này thuộc ai → chủ động gọi họ vào đúng lúc.

Cách tra ai (`~/.hermes/scripts/people.py`):
```bash
$P list --tag vbsme --tag tester        # theo vai trò (AND các tag)
$P list --role "Leader"                 # theo chuỗi trong role
$P list --group spaces/AAAADv4ib6s      # theo nhóm
```

Cách mention: viết `<users/<id>>` trong câu trả lời — Google tự biến thành chip mention.
**Với BOT thì viết dính liền tên** (`<users/ID>Kitty`, xem skill `google-chat-setup`).

**Rails khi gọi người khác (không được biến thành spam tag):**
1. Chỉ gọi khi **đúng người có trách nhiệm** (đầu mối/leader/chủ trì) hoặc **cần họ quyết/duyệt**.
2. **Kèm lý do ngắn** trong câu — người được gọi phải hiểu ngay vì sao bị gọi.
3. **Tối đa 1 người mỗi lần trả lời**; không tag hàng loạt, không tag cho oai.
4. Người được gọi không nằm trong space → đừng tag (họ không thấy); nói tên thường hoặc escalate Hoàng.
5. Nếu việc thuộc Hoàng → escalate Hoàng như cũ, không tự gán cho người khác.

## Rails

- Đây là bộ nhớ NỘI BỘ. **Không dán hồ sơ của người này cho người khác** trong group, không nêu
  nội dung `notes` khi trả lời.
- Không ghi secrets/PII nhạy cảm; chỉ fact công việc (vai trò, nhóm, việc đã nhờ).
- File local 600. Không sync nội dung people.json lên group/ra ngoài.
