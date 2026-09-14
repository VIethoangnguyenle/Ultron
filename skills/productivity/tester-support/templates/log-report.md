# Tra log: <MÃ LỖI / HIỆN TƯỢNG> — <TÊN DỰ ÁN>

> Mẫu bắt buộc cho mọi báo cáo tra log gửi tester/dev (Hoàng chốt 2026-09-14).
> **Đầu ra là FILE PDF** (Hoàng sửa lại cùng ngày 14/09: *"gửi file cho tester… luôn ưu tiên file PDF để
> mô tả nhé, kể cả log em cũng để ở trong đó"*) — viết `.md` theo mẫu này rồi convert:
> `python3 ~/.hermes/scripts/md2pdf.py <file>.md -o <file>.pdf`; `.md` chỉ là bản nháp nội bộ.
> Giữ đủ 7 mục, viết bằng NGÔN NGỮ NGHIỆP VỤ (không tên class/file/hàm, không dán source).
> Che token/secret/mật khẩu/PII trong mọi đoạn trích log.

**Người yêu cầu:** <tên + users/id> · **Nhóm:** <tên group/space>
**Thời điểm tra:** <dd/mm/yyyy HH:MM> · **Người thực hiện:** Ultron (trợ lý Hoàng NLV)
**Môi trường:** SIT / UAT / LIVE · **Thời điểm lỗi tester báo:** <dd/mm/yyyy HH:MM>

---

## 1. Yêu cầu & phạm vi

- **Câu hỏi nguyên văn của tester:** "..."
- **Cần trả lời:** <câu hỏi cụ thể: vì sao lỗi? giao dịch có tới đối tác không? tiền đã bị trừ chưa? ...>
- **Phạm vi tra:** <khoảng thời gian> · <service/hệ thống> · <mã tham chiếu: mã giao dịch / mã lỗi / số điện thoại che PII>

## 2. Dữ liệu đầu vào đã dùng

| Nguồn | Chi tiết (không dán nội dung log ở đây) |
|---|---|
| Log | <môi trường + tên service> |
| Khoảng tải | <từ giờ> → <đến giờ>, <số file> |
| Từ khoá tra | <requestId / mã GD / mã lỗi / số ĐT che PII> |
| Số bản ghi khớp | <N> |

## 3. Các bước tra (đầy đủ — người khác đọc lại làm được)

| Bước | Việc đã làm | Kết quả |
|---|---|---|
| 1 | Khoanh vùng lỗi → xác định service chứa log | <service X> |
| 2 | Tải file log trong khoảng thời gian lỗi | <N file, từ ... đến ...> |
| 3 | Lọc theo mã giao dịch / requestId | <N dòng khớp> |
| 4 | Dựng timeline các bước xử lý | <số bước: REQUEST → CALL_* → RESPONSE> |
| 5 | Đối chiếu bước lỗi với mã lỗi tra được | <mã lỗi nằm ở bước ...> |
| 6 | Kiểm tra giả thuyết khác (nếu có) | <loại trừ được gì> |

## 4. Dòng log quan trọng (trích nguyên văn, đã che secret/PII)

```
<dòng log 1 — kèm thời gian chính xác>
```
→ Nghĩa nghiệp vụ: <giải thích ngay bên dưới, không dùng thuật ngữ code>

```
<dòng log 2 — ví dụ phản hồi từ đối tác/core bank>
```
→ Nghĩa nghiệp vụ: <...>

| Thời điểm | Bước xử lý | Kết quả | Ghi chú |
|---|---|---|---|
| HH:MM:SS | <nhận yêu cầu> | OK | |
| HH:MM:SS | <gọi đối tác/core> | LỖI <mã> | <ý nghĩa> |

## 5. Kết luận (ngôn ngữ nghiệp vụ)

- **Hiện tượng tester thấy:** <...>
- **Nguyên nhân gốc:** <...>
- **Bằng chứng:** <trích ở mục 4 / thời điểm cụ thể>
- **Điểm mấu chốt (nếu có):** <vd: mã VBGxxx = lỗi từ core bank, kèm nguyên văn đoạn gọi sang bank>

## 6. Việc cần làm / đề xuất

- [ ] <việc cho tester kiểm lại>
- [ ] <việc cho dev/BA nếu cần>
- [ ] <theo dõi thêm nếu chưa kết luận được>

## 7. Phụ lục

- **Đường dẫn log gốc:** <link> (chỉ Ultron/người có quyền mở; tester qua kênh đã cấp)
- **Giới hạn của báo cáo:** <chưa xác minh được gì / cần thêm dữ liệu gì>
- **Ghi chú:** <...>

---

### Checklist trước khi gửi

- [ ] Không có tên class/file/hàm/hằng số, không có source code, không stack trace
- [ ] Không có token/secret/mật khẩu/PII trong đoạn trích log
- [ ] Đủ 7 mục; mục 3 đủ bước để làm lại được
- [ ] Tin nhắn Chat chỉ ngắn: kết luận + file đính kèm (không dán log dài)
- [ ] Đã gửi file thật lên group (không thả đường dẫn local) và kiểm tra lại tin đã tới thread đúng
