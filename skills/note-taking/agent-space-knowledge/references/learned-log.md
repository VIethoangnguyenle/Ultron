# Learned log — Agent Space

Append-only. Mỗi mục: ngày + điều học được + nguồn (ai nói). Chỉ ghi kiến thức BỀN VỮNG
(quyết định, convention, cấu trúc, cách vận hành) — không ghi chit-chat.

## 2026-09-10 (seed — backfill 35 tin nhắn đầu tiên)

- Chị Nguyên (PP) muốn Ultron nâng cấp thành trợ lý đi sâu kiến trúc; Ultron đã nêu cần Hoàng
  cấp tài liệu kiến trúc + sơ đồ hệ thống. Chưa có chốt từ Hoàng. (Nguyên, 09:24)
- Chị Nguyên đề nghị Ultron dạy rule bảo mật cho agent Kitty; Ultron trả lời việc train phải do
  sếp Hoàng quyết. (Nguyên, 10:13)
- Chuẩn hành xử khi quá phạm vi: hỏi lại Hoàng rồi trả lời sau — chị Nguyên xác nhận đây là
  cách đúng. (Nguyên, 10:19)
- Ultron tự nêu nguyên tắc chống trả lời sai: không suy diễn từ trí nhớ, luôn tra nguồn thật với
  mã lỗi/dữ liệu/luồng xử lý. (Ultron, 09:21)
- Kitty là agent khác đang hoạt động trong space (users/114664300353544982656). (Kitty, 09:26)

## 2026-09-10 (lần học 17:30 — 2 tin mới, KHÔNG có kiến thức mới)

- Chị Nguyên nhắc lại đúng 1 việc đã ghi ở mục seed: ngoài phạm vi thì "hỏi lại anh Hoàng để
  ảnh hướng dẫn phương án" — không phải dữ liệu mới, chỉ xác nhận lại convention đã có.
  (Nguyên, 10:19)
- Về đề nghị train rule bảo mật cho Kitty: việc này ĐÃ được escalate cho Hoàng và escalate
  forwarder đã gửi thành công (marker `1789035602-kitty-security-rules.json` trong log cron
  `ultron-escalate`). ⇒ Lần sau gặp lại chủ đề Kitty/train trong space thì KHÔNG escalate lại
  (tránh spam Hoàng); chỉ chờ Hoàng trả lời rồi mới hành động. (Ultron, ghi lúc 17:30)

## 2026-09-10 (ghi chú vận hành 17:40 — poller bắt nhầm tin của chính Ultron)

- Marker `mention_pending/spaces_AAQASaFjh6M_messages_h85yYiXo8eE.A3-VPdgPiT4.json` (poller
  escalate 17:36) KHÔNG phải câu hỏi của đồng nghiệp: sender là `users/107189931083311611240`
  = chính Ultron (bot), nội dung là câu Ultron đáp lại lời trêu của Hoàng
  ("@Ultron Làm chị Nguyên nóng là mày bị reset đó biết chưa") — có tag @Hoàng nên bị poller bắt.
  ⇒ Xử lý: KHÔNG reply vào group (tự trả lời mình = spam, nguy cơ loop với chính mình),
  KHÔNG escalate (xã giao, không có việc gì cho Hoàng). Chỉ xoá marker.
- `mention_poller.py` hiện chỉ bỏ qua tin do HOÀNG gửi, CHƯA lọc sender là bot/Ultron
  (`users/107189931083311611240`). Đề xuất (chờ Hoàng duyệt, KHÔNG tự sửa script):
  thêm điều kiện skip `sender == ULTON_BOT_USER` để giảm marker rác + chặn rủi ro
  Ultron tự reply chính mình. (Ultron, ghi lúc 17:40)
