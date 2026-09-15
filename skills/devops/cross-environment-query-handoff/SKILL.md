---
name: cross-environment-query-handoff
description: "Use when handing a query to another env, or proving which env a log/DB source covers."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [handoff, cross-environment, sql, evidence, tester-support, schema-drift, live, sit]
    related_skills: [vbsme-db-lookup, vbsme-error-diagnosis, tester-support]
---

# Cross-environment query & report handoff

Dùng khi bạn viết một câu query / báo cáo mà **người khác sẽ chạy hoặc kiểm ở môi trường bạn không vào được**
(SIT → UAT/LIVE, nội bộ → hạ tầng bank/đối tác, máy tester → DB nhà bank), hoặc khi kết luận của bạn dựa
trên log/dữ liệu mà bạn không thể đọc trực tiếp.

Nguyên tắc gốc: **môi trường khác không bảo đảm cấu trúc giống nhau, và "tôi chạy sạch ở đây" không phải
"nó chạy được ở kia".** Câu query/báo cáo phải tự đứng được ở nơi nó sẽ chạy.

## Khi dùng

- Tester/dev/bank nhận query của bạn để tự chạy trên môi trường họ có quyền (bạn chỉ có DB SIT).
- Cần chứng minh "dữ liệu có tồn tại không" ở môi trường không truy cập được.
- Kết luận phải rút ra từ log mà log chỉ ghi một phần sự thật (không ghi số bản ghi, không ghi nội dung).

## Quy trình giao query cho người khác chạy

1. **Chốt môi trường đích + ai chạy + họ có quyền gì.** (SIT? UAT? LIVE? user nào? tool nào?) Không có
   thông tin này thì câu query không viết được đúng. Chốt luôn **tên DB/schema của môi trường đích** — không
   biết thì đưa câu dò hoặc xin tên/ảnh danh sách kết nối, đừng viết chung chung kiểu "bảng này".
2. **Viết bản “cột lõi” trước.** Chỉ dùng những cột chắc chắn tồn tại từ lâu và là cột nghiệp vụ cốt lõi;
   cột trang trí (số tham chiếu, mã phản hồi, kênh, thông tin bổ trợ) để **lần chạy sau**. Ít cột mà chạy
   được > đủ cột mà lỗi.
3. **Gửi kèm một câu dò cột** để cả hai bên cắt lại nhanh thay vì đoán:
   `SELECT table_name, column_name, data_type FROM all_tab_columns WHERE table_name IN ('BẢNG_1','BẢNG_2') ORDER BY table_name, column_id;`
   — nếu user thiếu quyền `ALL_TAB_COLUMNS` thì dùng `USER_TAB_COLUMNS`; qua một số cổng truy vấn phải
   prefix owner của dictionary view (vd `SYS.ALL_TAB_COLUMNS`), viết trần bị chặn.
4. **Nói đúng mức tin cậy của mình.** Câu chuẩn: *"em chạy thử trên môi trường X thấy execute sạch; môi
   trường Y em không có quyền vào DB"*. Không bao giờ nói như thể đã kiểm chứng ở nơi bạn không chạy.
   Kèm 1 dòng "lệch cấu trúc giữa X và Y là phát hiện đáng báo dev/DB" khi phát hiện lệch.
5. **Dự đoán kết quả để họ đối chiếu** — nói trước sẽ thấy dòng nào (mã nào, trạng thái nào, bước nào),
   và kết quả ra sao thì kết luận gì. Người chạy không đọc được ý định của bạn trong câu SQL.
6. **Vòng lặp sửa lỗi phải ngắn.** Khi họ dán lỗi vào, chỉnh đúng chỗ lỗi, không viết lại từ đầu.

## Ghi hẳn tên DB / schema / bảng trong câu query

Người chạy không đọc được ý định của bạn: câu query phải tự chỉ đúng nơi lấy dữ liệu — `SCHEMA.BẢNG`, và nếu môi
trường đích có nhiều DB/instance thì phải nói rõ **DB nào**, kèm tên kết nối/link nếu truy vấn chéo.

- **Đừng trả lời kiểu "bảng cùng tên, chỉ khác kết nối".** Người nhận không có nghĩa vụ biết schema hai bên trùng
  tên; họ copy nguyên văn câu của bạn vào phiên đang mở. Ghi `SCHEMA.BẢNG` ngay trong câu SQL.
- **Hai DB riêng thì `SCHEMA.BẢNG` trong cùng phiên vẫn không đủ** — schema của instance khác không nhìn thấy được.
  Đưa đúng 1 trong 2 đường: (a) câu query để chạy *trong phiên kết nối tới DB đó*, (b) câu chéo instance có
  `@<DB_LINK>`, kèm câu dò link.
- **Không biết tên schema/link của môi trường đích** (mình không có quyền vào đó) → gửi câu dò tên
  (`all_tables` theo owner / `all_db_links`) **và xin tên DB/schema** rồi điền sẵn vào câu query, đừng để họ tự ghép.

## Đọc lỗi của môi trường khác (không hoảng, không đổ cho query sai)

- `ORA-00904: "X": invalid identifier` = **cột X không tồn tại ở môi trường đó**. Oracle trỏ vào **một vị trí
  xuất hiện** của định danh (thường là nhánh thứ 2 của `UNION ALL`), không phải cả câu ⇒ bỏ/nuôi cột đó
  rồi chạy lại, còn các cột khác chưa chắc đã có ⇒ cứ theo bước 2-3 ở trên.
- Lỗi phân quyền / không thấy bảng (vd `ORA-01031`, `ORA-00942`) = khác schema owner, khác quyền user —
  không phải query sai.
- **Cột chỉ một nhánh `UNION` có** → nuôi bằng kiểu rõ ràng: `CAST(NULL AS VARCHAR2(50))` cho Oracle.
- Môi trường đích thường **rỗng với dữ liệu của bạn** (SIT không chứa dữ liệu môi trường thật) ⇒ nói
  trước "0 dòng ở đây là bình thường" để người chạy không tưởng query sai.

## Kỷ luật bằng chứng — số liệu ghi nhận vs suy luận

Khi kết luận dựa trên log/nhật ký mà nguồn **không ghi con số bạn cần**, đây là chỗ mất uy tín nhanh nhất.

- **Phân biệt rõ hai thứ khi viết báo cáo:** (a) điều nguồn ghi lại (bộ lọc đã dùng, thời điểm, mã kết quả,
  http status) và (b) điều mình **suy ra**. Ghi nhãn cho (b): *"đây là suy luận"*.
- **Không được nâng suy luận thành số liệu.** Ví dụ điển hình: log tầng API chỉ ghi 1 dòng/lượt gọi, **không
  ghi số bản ghi trả về** ⇒ không được viết "log cho thấy báo cáo trả rỗng" hay "log cho thấy vẫn có dữ
  liệu". Con số "0 bản ghi" là **quan sát trên màn hình của người dùng**, không phải số liệu log.
- **Muốn chứng minh số bản ghi** thì phải đổi tầng bằng chứng: dữ liệu nguồn (DB), hoặc ảnh chụp/kết quả
  người dùng trích ra, hoặc báo cáo màn hình — không suy từ log vận hành.
- **Không suy hành vi của môi trường mình có quyền sang môi trường đích.** Cùng một bản ghi ở trạng thái trung gian
  có thể *có* bản ghi hạ nguồn ở env này mà *không có* ở env kia ⇒ nhờ người có quyền chạy 1 câu đếm tồn tại, và
  ghi rõ kết luận đã kiểm ở env nào.
- **Cột ngày/giờ kiểu `modifiedDate` có thể là cột chết cho một số chuyển trạng thái.** Trước khi dùng nó để
  định thời điểm sự kiện (kiểu "bị huỷ ngay lúc tạo"), **kiểm trên mẫu**: lọc toàn bộ bản ghi cùng trạng thái
  trong một payload danh sách rồi so `createdDate` với `modifiedDate`. Nếu 100% bằng nhau ⇒ cột không được cập
  nhật cho chuyển trạng thái đó ⇒ không suy ra được thời điểm; phải viết "xảy ra trước mốc dữ liệu còn giữ".
- **Người dùng sẽ replay từng câu của bạn** (nhất là tester leader). Sai thì **đính chính thẳng + phát hành
  bản cập nhật (v2)** kèm 1 câu nói rõ điểm sửa; không bảo vệ câu cũ, không im lặng sửa ngầm.
- Báo cáo kiểu "các bước đầy đủ" vẫn phải giữ nguyên: nguồn dữ liệu, các bước tra, trích nguồn, kết luận,
  việc cần làm, phụ lục.

## Ví dụ đã trả giá

- Query union hai bảng lệnh (đang xử lý vs đã hoàn tất) chạy sạch trên SIT, tester chạy nguyên văn trên LIVE
  → `ORA-00904: "STATUS": invalid identifier` (bản LIVE thiếu cột `STATUS`). Cách xử lý đúng: gửi bản cột
  lõi + câu dò cột, nói rõ "SIT sạch / LIVE em không có DB".
- Báo cáo v1 khẳng định từ log điều log không ghi (số bản ghi) → tester phản biện → phải làm v2 đính chính.

Chi tiết bảng/cột và query mẫu của ca trên (VietBank SME, bảng lệnh `*_TRANS_REQ`):
`references/vbsme-lenh-tables.md` — đọc khi cần dựng câu query theo CIF doanh nghiệp + ngày soạn lệnh; file này
còn có câu quét một lượt tìm mã lệnh trong mọi bảng giao dịch, và ghi chú DB online vs DB offline là hai DB riêng.

## Chứng minh một nguồn log/DB thuộc môi trường NÀO (trước khi hứa với tester)

Dùng khi tester/dev hỏi "em đọc được log môi trường X không?", hoặc khi bạn sắp trả lời dựa trên một nguồn
log/DB mà mình chỉ biết tên thư mục / tên kết nối. **Không suy môi trường từ tên thư mục.**

1. **Nhãn thư mục/kết nối không phải bằng chứng.** Thư mục kiểu `/omni-<dự án>/` có thể phục vụ bất kỳ env nào.
   Đọc nội dung log tìm dấu vết env: banner version lúc khởi động (`<App>-UAT-v1.0.0`, `{ UAT version x.y.z }`),
   tên bucket/đường dẫn storage (`uat-<dự án>-bucket-0N`), host hệ thống lõi mà service gọi (dev/test vs uat/live).
   Nhãn profile (`[sit]`, `[uat]`) thường **không còn** trong pattern log đã deploy ⇒ grep không thấy không có nghĩa
   "không xác định được"; phải soi banner/bucket/host.
2. **Đối chiếu chéo HAI CHIỀU log ↔ DB theo khoá giao dịch** (`traceNo` / `requestId` / `REF_NO`). Trace có trong DB
   mà không có trong log, và trace trong log không có trong DB ⇒ **hai môi trường khác nhau**: log phục vụ env A,
   DB là env B. Nói kết luận này ra cho tester, kèm chú thích "dữ liệu mình đọc là env test".
3. **Đừng probe cây thư mục log để tìm env còn thiếu.** Trên server log autoindex, path top-level không tồn tại trả
   **403 blanket** (không suy ra được gì), còn path lạ nằm dưới thư mục có thật trả **404**. Kết luận "env X không có
   log" phải đến từ nội dung log + đối chiếu dữ liệu, không phải từ việc thử vài path.
4. **Mẫu trả lời tester: chắc / cần gì / đường lui.** "*Log em đọc được là <env A> (thêm bản lưu <env B>). Với
   <env C> em tra được dữ liệu, log chi tiết thì cần file — chị gửi file hoặc chỉ chỗ lấy.*" Khi nguồn log đọc trực
   tiếp được, nói thẳng **"chị không cần gửi file log"** và liệt kê thứ cần đưa: môi trường, username/mã đăng nhập,
   mốc thời gian (ngày + giờ), mã giao dịch/mã tham chiếu.
5. **Thiếu nguồn log cho một env ⇒ DM người có trách nhiệm (Hoàng) xin đường log**, đừng để tester tự đi tìm hạ tầng
   và đừng im lặng nhận việc mình không làm được; trong group chỉ nói 1 câu "em đã hỏi anh Hoàng xin đường log env đó".

## Pitfalls

- Đừng bảo "em đã test rồi" khi test khác môi trường đích — đó là nói quá mức chứng cứ.
- Đừng gửi 1 câu query duy nhất cho môi trường mình chưa từng chạy; luôn kèm đường lui (câu dò cột / bản rút gọn).
- Đừng coi "log báo 200/mã 00" là bằng chứng có dữ liệu — đó chỉ là "lời gọi thành công", không nói gì về số dòng.
- Đừng để người chạy tự đoán cách đọc kết quả; viết sẵn "thấy dòng nào ⇒ kết luận gì".
- Đừng trả lời "cùng tên bảng, chỉ khác kết nối" — ghi hẳn `SCHEMA.BẢNG` (và tên DB/link nếu chéo instance);
  người chạy không có ngữ cảnh của bạn và sẽ chạy y nguyên câu đó.
- Đừng hứa "chỉ cần username là tra được" cho mọi môi trường — kiểm tra nguồn log có phủ đúng env tester đang test trước.
- Đừng dùng nhãn thư mục/tên kết nối làm bằng chứng môi trường; soi banner/bucket/host trong chính nội dung log.
