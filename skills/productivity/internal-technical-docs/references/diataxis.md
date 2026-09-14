# Khung Diátaxis — chọn LOẠI tài liệu trước khi viết

Nguồn tham khảo: https://diataxis.fr/ và skill `documentation-writer` của `github/awesome-copilot`
(Hoàng gửi link 14/09/2026, dặn *"em có thể tham khảo skill này để viết tài liệu giúp anh"*).

Bốn loại tài liệu có bốn mục đích khác nhau. Trộn lẫn mà không ghi rõ ranh giới là lỗi phổ biến nhất
khiến tài liệu bị đọc là "nói chung chung".

| Loại | Mục đích | Giọng văn | Người đọc |
|---|---|---|---|
| **Tutorial** (học) | Dạy người mới đi từ đầu tới kết quả thành công | Dẫn dắt, có thứ tự | Chưa biết gì |
| **How-to** (việc) | Giải một việc cụ thể | Mệnh lệnh, từng bước | Đã biết cơ bản, cần công thức |
| **Reference** (tra) | Mô tả chức năng/"máy móc" để tra cứu | Khô, trung tính, có bảng | Cần đúng một chi tiết |
| **Explanation** (hiểu) | Giải thích vì sao, bối cảnh, đánh đổi | Thảo luận | Cần hiểu để tự quyết |

## Chốt 4 điều trước khi viết

Gửi 1 tin ngắn nêu 4 điều dưới đây — nhưng **tự chọn phương án mặc định hợp lý rồi viết luôn**, không ngồi
chờ trả lời (Hoàng: *"cho anh pdf trước"*).

1. **Loại tài liệu** — tutorial / how-to / reference / explanation; tài liệu dài thường nhiều loại ⇒ ghi rõ
   mục nào thuộc loại nào (1 dòng dưới mục lục).
2. **Đối tượng đọc** — người mới hay người đã biết nghề (tester · dev/BA · quản lý).
3. **Mục tiêu** — sau khi đọc, người đó LÀM được gì / TRA được gì.
4. **Phạm vi — nhất là phần LOẠI TRỪ**: cái gì KHÔNG nằm trong tài liệu. Với tài liệu công cụ thì loại trừ
   chi tiết dự án (xem SKILL.md, mục "Phân biệt TÀI LIỆU CÔNG CỤ vs TÀI LIỆU DỰ ÁN").

## Nguyên tắc viết (4 điều, không thương lượng)

- **Rõ ràng** — câu ngắn, mỗi câu một ý, không viết vòng.
- **Chính xác** — số liệu/phiên bản/giấy phép đọc từ MÁY, không đoán; câu lệnh phải chạy được thật.
- **Hướng người đọc** — mỗi tài liệu giúp MỘT đối tượng cụ thể đạt MỘT mục tiêu cụ thể.
- **Nhất quán** — thuật ngữ và cách xưng hô thống nhất trong suốt tài liệu và với các bản trước đó.

## Khi Hoàng đưa file Markdown khác làm ngữ cảnh

Dùng để hiểu giọng điệu, thuật ngữ, chuẩn trình bày của bộ tài liệu — **không copy nội dung** trừ khi
Hoàng yêu cầu rõ. Không tự tra nguồn ngoài trừ khi được đưa link và yêu cầu (đúng tinh thần skill gốc).

## Áp vào bộ tài liệu Ultron

- Mục 1, 2, 5–8 → **Explanation** (hệ thống là gì, vì sao, phạm vi, an toàn, vận hành).
- Mục 3, 4, Phụ lục A → **Reference + How-to** (làm được gì · dùng thế nào · câu lệnh mẫu).
- Mục 9 → **How-to** thuần (quy trình xử lý một yêu cầu, từng bước).
- Mục 2.4 → **Explanation** cho công cụ cốt lõi (cơ chế đọc hiểu mã nguồn + nguyên tắc làm việc).
