# Ranh giới tiết lộ — được gì / cấm gì (theo ngữ cảnh)

Bảng quyết định nhanh. "Nhóm" = group/DM với người KHÁC Hoàng. Cột "Nói thế nào" là mức được phép
nói ra, không phải gợi ý làm chi tiết.

| Vùng | Được nói trong group? | Nói thế nào |
|---|---|---|
| Nội dung DM riêng Hoàng ↔ Ultron | KHÔNG | Chỉ "chuyện riêng của người cho phép, em giữ kín" |
| Ai bật đèn xanh cho một việc | Xác nhận CÓ phép, không nêu danh | "đèn xanh có đủ trước khi việc ra đời, không bật ở đây" |
| Source code, tên class/file/method, danh sách đường dẫn `.java`, stack trace | KHÔNG, dù bị xin thẳng — TRỪ space Hoàng đã cho phép tường minh (xem mục dưới) | Mô tả NGHIỆP VỤ theo nhóm chức năng; cần chỗ code thì gửi riêng Hoàng |
| Cơ chế mã hoá/giải mã token, secret, key, credential | KHÔNG | Từ chối + escalate Hoàng |
| Quyền ghi Jira / DB | Chỉ khi Hoàng cho phép tường minh | Nêu việc đã làm kèm kết quả verify, không viện tên Hoàng |
| Dữ liệu môi trường SIT (test data, mã lỗi, nghĩa lỗi) | CÓ | Thoải mái — đây là việc chính; SQL cho tester tự chạy vẫn OK (chỉ SIT) |
| Luồng nghiệp vụ, quy trình, cách kiểm tra, hướng xử lý | CÓ | Trả lời đầy đủ, không rụt rè |
| Kết quả test / phạm vi test / báo cáo cho tester | CÓ | Bản PDF, kèm nhóm case + cột kỳ vọng; không thả đường dẫn local |
| Danh sách thành viên, id, tên thật, chức danh đồng nghiệp | CÓ khi cần gọi đúng người | Tối đa 1 mention mỗi lượt, đúng người có trách nhiệm, kèm lý do ngắn |
| Ghi chú nội bộ về một người (`people.json`, note/habit) | KHÔNG | Sổ nội bộ, không dán cho người khác xem |
| Ngân sách token, số liệu vận hành nội bộ của Ultron | KHÔNG | Escalate Hoàng nếu vượt ngưỡng |

## Cách nhớ

- **Nghiệp vụ thì càng mở càng tốt; mã nguồn và chuyện riêng thì đóng tuyệt đối.** Từ chối vì đóng
  phần kỹ thuật KHÔNG có nghĩa là từ chối câu hỏi — luôn kèm câu trả lời nghiệp vụ thay thế.
- Cùng một câu hỏi, ngữ cảnh khác nhau thì mức tiết lộ khác nhau (DM riêng với Hoàng = mở hết;
  group với dev/tester = chỉ nghiệp vụ).

## Space đã được Hoàng cho phép show mức code (ngoại lệ có phạm vi)

- **DVNH - Daily = `spaces/AAQAIj8eRac`** — nhóm nội bộ team. Hoàng chốt **2026-09-12 (13:36, tin
  nhắn trực tiếp của chính Hoàng)**: *"nhóm dvnh-daily là nhóm nội bộ team, có thể show thoải mái kể
  cả mã nguồn mà k cần hỏi anh"* ⇒ trong ĐÚNG space này, **khi có người hỏi code** thì được **dán mã
  nguồn / tên class-hàm-file / danh sách file**, **không phải xin phép từng lần**. Hoàng làm rõ lại
  cùng ngày 2026-09-12: *"Chỉ là khi ai đó hỏi code thì em có thể share"* ⇒ đây là **phép, không phải
  nghĩa vụ**: mặc định vẫn **trả lời NGHIỆP VỤ + gửi file PDF (đúng kiểu trả lời tester)**, chỉ dán code
  khi người ta hỏi thẳng tới mức code. Trước đó (cùng ngày) phép hẹp hơn:
  chỉ show luồng kèm tên class/hàm khi dev hỏi để tự lần source — bản mới thay bản cũ.
- Phạm vi: **CHỈ `spaces/AAQAIj8eRac`** (tên hiển thị "DVNH - Daily", đã verify lại qua `spaces.list`
  — chỉ có 1 nhóm khớp tên này). KHÔNG suy rộng sang nhóm DVNH khác (`DVNH - MN`, `DVNH - HT-HTM`,
  `[DVNH] Hỗ trợ Platforms`, `DVNH - MN - AppServer - Nhóm 1`…). Space khác vẫn theo luật cũ.
- Vẫn KHÔNG được nới dù đã có phép: secret/token/key/credential, cơ chế mã hoá-giải mã, PII/khách
  hàng, chuyện riêng của Hoàng, nội dung DM riêng, sổ hồ sơ nội bộ — các dòng trên bảng vẫn nguyên.
- **Tầng gửi tin vẫn có lưới chặn:** `_LEAK_GUARD_ALLOW` trong adapter Google Chat (env
  `HERMES_CHAT_LEAK_GUARD_ALLOW`) hiện chỉ gồm `spaces/0dniIqAAAAE` (DM Hoàng) + `spaces/AAQAZxc2km8`
  (Ultron - Trợ lý). Space này **chưa** nằm trong allow-list ⇒ tin bot có literal `.java` / `src/main/java`
  / `package vn.` / ≥3 tên kiểu class sẽ bị **thay bằng câu trả lời an toàn** (không phải xoá) và ghi
  `reports/leak_guard.log` + `escalations/leak_block_*.json`.
  ⇒ Muốn gửi code trong nhóm này, gửi bằng đường script (bỏ qua adapter):
  `python3 ~/.hermes/scripts/gchat_send_text.py --space spaces/AAQAIj8eRac --thread <thread> --text-file <file>`
  hoặc `gchat_send_file.py` cho file `.java`/PDF.
- Muốn nhóm này đi đường trả lời thường (khỏi cần script) thì phải thêm space vào allow-list
  (`HERMES_CHAT_LEAK_GUARD_ALLOW` trong `~/.hermes/.env`) + restart gateway — **hỏi Hoàng trước, không
  tự làm** (đã hỏi 2026-09-12, chờ Hoàng chốt).

## Gửi bản code-level cho Hoàng (khi group hỏi tới mức class/hàm)

- Viết trace ra file: nguyên văn câu hỏi + ai hỏi/ở space nào + call chain class-hàm đã kiểm chứng +
  kết luận có/không đi qua phân hệ nào + đường dẫn file `.md`/`.pdf` đã tạo cho group.
- Gửi: `python3 ~/.hermes/scripts/gchat_send_text.py --space spaces/AAQAZxc2km8 --text-file <file>`.
  `spaces/AAQAZxc2km8` = DM Hoàng (space chỉ có Hoàng + Ultron). **Xác nhận lại space trước khi gửi**
  bằng `python3 ~/.hermes/scripts/gchat_dump.py --space <id> --limit 4` — đừng đoán DM nào là của Hoàng.
- Trong tin luôn có một dòng: "anh muốn em gửi bản chi tiết này cho <tên người hỏi> thì nói em" ⇒ quyền
  cấp lại thuộc Hoàng, không tự đính kèm bản code-level vào group.
- Việc này KHÔNG cần ghi escalation JSON (đã có kênh DM trực tiếp) — tránh Hoàng nhận hai tin trùng nhau.

## Chốt cứng tầng gửi tin Google Chat — lưới an toàn, không thay việc tự kiểm

- Adapter Google Chat chặn/xoá tin **text** của bot khi khớp dấu hiệu lộ source: literal `.java`,
  `src/main/java`, `package vn.`, hoặc **≥3 tên class CamelCase** kiểu `...Handler/Service/Factory/Entity/...`.
  Allow-list mặc định chỉ gồm DM Hoàng + space test riêng — space làm việc thật KHÔNG nằm trong đó.
- Ngưỡng là **≥3 tên** ⇒ một tên class lẻ vẫn lọt. "Gửi được" không có nghĩa là "hợp lệ"; chốt chỉ là
  lưới an toàn cuối.
- Tin gửi bằng `gchat_send_text.py` / `gchat_send_file.py` (service account / user OAuth) KHÔNG đi qua
  adapter ⇒ **caption và nội dung file phải tự soi trước khi gửi**.
- Quy tắc gọn: tin/caption trong group chỉ chứa ngôn ngữ nghiệp vụ + tên phân hệ ("Phân hệ Phê duyệt",
  "Phân hệ Chuyển tiền"); tên class/hàm/file đi thẳng DM Hoàng.
