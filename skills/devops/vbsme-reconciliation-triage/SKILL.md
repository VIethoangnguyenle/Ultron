---
name: vbsme-reconciliation-triage
description: "Use when a vbsme giao dịch treo/chờ xử lý, hỏi job đối soát ghi lại thông tin gì, hoặc hỏi mã TRN / mã risk core của một giao dịch."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, reconciliation, napas, pending, log, tester]
    related_skills: [vbsme-error-diagnosis, tester-support, vbsme-db-lookup]
---

# vbsme — giao dịch treo "Chờ xử lý" / job đối soát không đổi trạng thái

Dùng khi tester hỏi kiểu: *"job chuyển tiền 247 chạy lúc HH:00 mà giao dịch <trace> vẫn chưa đổi trạng thái"*, *"giao dịch treo chờ xử lý"*, *"kiểm tra nguyên nhân"* cho một giao dịch 247, khách thấy mã **500069**, hoặc *"sao chạy job thì cột mã phản hồi SME/nội dung không đổi mà bấm nút thì đổi"* (câu hỏi về **bộ thông tin mà job đối soát ghi lại** — xem mục dưới).

Đây là quy trình riêng cho **trạng thái treo do đối soát**. Các nguồn chính vẫn là 2 skill nền (user-owned): `tester-support` (scope-map, quy tắc trả lời, khuôn báo cáo .md) và `vbsme-error-diagnosis` (tra mã lỗi, trace journey). Chi tiết đầy đủ của lớp việc này: `references/pending-transaction-reconciliation.md`.

## Rule cốt lõi — trả lời đúng ngay, đừng để tester báo bug sai chỗ

Giao dịch 247 chỉ được **chốt trạng thái cuối** khi lõi trả **thành công** hoặc **thất bại**. Ba mắt xích:

1. Lõi **không phản hồi** ở bước duyệt cuối → khách thấy **500069 "Giao dịch đang chờ xử lý…"** → giao dịch về **Chờ xử lý** (chưa xác định kết quả).
2. Job đối soát hỏi lại lõi theo **TRN**. Lõi trả *"No record found for TRN"* → **không có căn cứ chốt** → job **giữ nguyên** trạng thái.
3. ⇒ "Trạng thái không đổi" là **hành vi đúng của hệ thống**, KHÔNG phải job lỗi/kẹt. Nói rõ điểm này trong câu trả lời.

Thêm 2 điều tester luôn cần biết: TRN có **thời gian sống** (`financial.transaction.napas_v2.trn.ttl_hours`) nên TRN lúc tạo lệnh khác TRN lúc duyệt cuối (**không phải lỗi**); và job chỉ quét giao dịch treo trong **`...napas_v2.reconciliation.scan_days` ngày** → quá cửa sổ đó giao dịch **không còn được quét nữa**, treo tới khi xử lý tay.

## Quy trình 5 bước

1. **Chốt mốc thời gian + mã định danh**: mã giao dịch (trace), user, môi trường (UAT), khoảng thời gian. Giao dịch NAPAS V2 có **TRN riêng** (kèm trong log) — thu thập cả hai mã để grep.
2. **Tải log về local rồi grep** (portal Apache autoindex, `curl -k`):
   - **Log THÁNG HIỆN TẠI nằm ngay ở thư mục service** (`<svc>/sme-<svc>-<pod>.log`); thư mục `<svc>/<YYYY-MM>/` chỉ chứa log **archive của tháng trước** → curl vào đó rỗng, đừng tưởng hết log.
   - Tên file trên index bị cắt bằng `..&gt;` ở phần text → **parse thuộc tính `href`**, đừng lấy text của link.
   - File vài MB, trộn nhiều ngày → tải về `/tmp/<thu-muc>/`, grep local (`grep -c` để đếm, `cut -c1-400`/`head` khi in cho khỏi tràn ngữ cảnh). Trace không thấy ở pod đang xem → tải nốt pod khác **trước khi** kết luận "log không có". Log chứa payload thô (số TK, CIF, tên KH) → **xoá `/tmp` sau khi xong**.
   - Service cần: `napas-service` (bước duyệt cuối / gọi lõi), `worker-service` (**job đối soát**), `approval-service` (danh sách chờ duyệt), `transfer-service`.
3. **Đọc container đối soát trong `worker-service`**: mỗi giao dịch là 1 container `requestId = NapasRecon-<traceNo>`. Đối chiếu 3 kết cục (bảng trong reference) để kết luận giao dịch **đã chốt** / **còn chờ phía NAPAS (bình thường)** / **lõi không có bản ghi (treo vô thời hạn)**.
4. **Thống kê CẢ LƯỢT chạy**, không chỉ giao dịch được hỏi → trả lời được "có phải riêng giao dịch của tôi không". Lỗi kiểu này thường đến **theo đợt** (lõi không phản hồi vài phút → hàng chục giao dịch treo cùng lúc).
5. **Báo cáo cho tester = file `.md` đủ các bước**, không phải PDF: mục tiêu/phạm vi → dữ liệu đầu vào (nguồn log + khoảng thời gian) → các bước tra → trích log quan trọng → kết luận → việc cần làm → phụ lục. Gửi thành **file thật** vào đúng space/thread (`gchat_send_file.py --space ... --thread ...`); trên Chat chỉ **1 tin ngắn**: kết luận nghiệp vụ + file đính kèm — **KHÔNG dán log dài / nhiều dòng log vào tin nhắn**. PDF chỉ dùng khi giải thích **luồng nghiệp vụ** (markdown + diagram). Ngôn ngữ nghiệp vụ, **không** tên class/file/hằng số.

## Nút "Tra soát" trên app ≠ job đối soát (và mã 500004 khi giao dịch không đủ điều kiện)

"Tra soát giao dịch" là **tra cứu trạng thái theo yêu cầu khách** (một giao dịch, do người dùng bấm, có chống bấm liên tục) — khác job đối soát tự chạy theo lịch. Điều kiện để tra soát chạy: giao dịch **đã có kết quả cuối**, HOẶC đang **Chờ xử lý / Timeout** *và* có **mã tham chiếu (TRN) + ngày tham chiếu lưu trên giao dịch**. Ngoài 2 nhóm đó → hệ thống **từ chối bằng mã dùng chung `500004`**.

Vì là mã **dùng chung** (một mã phục vụ hàng trăm màn) nên câu chữ trong bảng mã lỗi ("… đã bị hủy trên trình duyệt Web") KHÔNG phải nguyên nhân — quy tắc chung: chốt đúng thao tác/màn tester báo → tra mã ra service/endpoint → tìm điều kiện chặn trong đúng luồng đó → giải thích theo điều kiện đó, và nói rõ câu chữ mặc định gây hiểu nhầm.

Biến thể đáng nghi nhất — **treo kép**: giao dịch vào nhánh "chờ tra soát" nhưng **không được ghi sang trạng thái Chờ xử lý và không lưu TRN/ngày tham chiếu** ⇒ vừa bấm Tra soát là 500004, vừa **không bao giờ được job đối soát nhặt** (job lọc theo trạng thái Chờ xử lý/Timeout *và* bắt buộc có TRN) ⇒ treo vô thời hạn. Khi gặp, kết luận là **bất thường phía hệ thống ở bước duyệt cuối — không phải lỗi thao tác, không phải lỗi riêng user**.

Nguyên nhân gốc hay gặp nhất của biến thể này: **bước cập nhật giao dịch thất bại âm thầm vì nội dung thông báo vượt ô lưu trữ theo BYTE** — ô trên phase rộng hơn nên vẫn ghi được, làm DB trông "bình thường". Mốc bắt đầu hỏng trùng lúc một dòng thông báo trong bảng mã lỗi được tạo/sửa ⇒ kiểm độ dài byte **ngay**, đừng dừng ở "lệch trạng thái hai tầng".

Bảng/trạng thái để kiểm chứng + cách chứng minh bằng dữ liệu (SIT không có log) + cấu trúc báo cáo: `references/tra-soat-giao-dich.md`.

Trong luồng tra soát chỉ có **đúng một điểm** ném `500004` ⇒ đừng gán các mã khác của cùng luồng (chống bấm nhanh ~30s, dịch vụ không hỗ trợ, lỗi quyền) cho cùng nguyên nhân, và luôn đọc trạng thái **cả tầng lệnh lẫn tầng giao dịch** — chính chỗ hai tầng lệch nhau là bằng chứng. Bảng mã theo trạng thái + cách đọc 2 tầng + quy trình chứng minh lỗi độ-dài-byte (mục 10–11): `references/tra-soat-giao-dich.md`.

## Tra soát trên UAT — đọc kết quả đối tác trực tiếp từ log

UAT không truy vấn được DB ⇒ chứng minh bằng log `napas-service`: mỗi lượt tra soát là một lời gọi `/ibft/transactionStatus` theo **TRN** (không theo traceNo), trả về `{code, desc, result:{responseCode, success, pending, failed}}`.

- `code 000` + `responseCode 00` / `success=true` → chốt **thành công**.
- `code 000` + `responseCode 68` / `pending=true` / `failed=false` → **vẫn chờ** ⇒ hệ thống giữ nguyên trạng thái (đúng cơ chế, không phải lỗi nút bấm).
- `code 400` *"No record found for TRN"* → không có căn cứ chốt.

Lưu ý dễ kết luận sai: kết quả lúc **xác nhận lệnh** là `{"code":"068","desc":"NAPAS ERROR: 68", ...}` — có mã core nhưng **trn rỗng**, nên giao dịch vào nhánh chờ tra soát; TRN dùng để tra soát về sau là TRN **hệ thống tự gắn** trên giao dịch (dạng `62xxVNTTA2FFxxxx`) ⇒ đừng kết luận "không có TRN nên không tra soát được".

Cách ghép traceNo↔TRN, cách chứng minh job đối soát **chưa từng quét** giao dịch (đọc lô job đẩy sang `transaction.napas_reconciliation.process_item` trong log `worker-service`), và đường bấm nút trên app (phân hệ phê duyệt, `.../completed-trans-reqs/check-pending`): `references/tra-soat-giao-dich.md` mục 13.

## Job đối soát và nút tra soát ghi lại KHÁC bộ trường (báo cáo sẽ tự mâu thuẫn)

Cả hai đường đều hỏi đối tác theo TRN và **nhận cùng một kết quả**, nhưng **phần ghi lại khác nhau**:

```
Thông tin lưu trên giao dịch         Job đối soát     Nút cập nhật/tra soát
-----------------------------------  ---------------  ----------------------
Trạng thái giao dịch                 Có ghi           Có ghi
Mã giao dịch core banking            Có ghi           Có ghi
Mã phản hồi SME                      KHÔNG ghi lại    Có ghi (000 / 01)
Nội dung phản hồi                    KHÔNG ghi lại    Có ghi (mã lõi, vd 00)
Lịch sử bước xử lý (mốc đối soát)    Có ghi           Có ghi
```

Hệ quả nghiệp vụ: sau khi **job** chốt thành công, báo cáo chi tiết giao dịch vẫn hiển thị mã `500069` kèm câu *"…đang được xử lý…"* (giá trị cũ lưu từ bước duyệt cuối) ⇒ dòng báo cáo **tự mâu thuẫn** (trạng thái Thành công mà mã phản hồi là mã của trạng thái chờ), dễ bị đọc thành "giao dịch còn treo", và không phân biệt được giao dịch do job chốt hay do đối tác trả kết quả trực tiếp. Nhánh job chốt **thất bại** cũng y hệt.

Cách trả lời chuẩn cho câu hỏi "sao chạy job thì 2 cột phản hồi không đổi, bấm nút thì đổi": (1) xác nhận tester quan sát **đúng**, đây là khác biệt thật của hệ thống chứ không phải lỗi thao tác/môi trường; (2) đưa bảng đối chiếu bộ trường được ghi; (3) nêu hệ quả (đọc báo cáo dễ kết luận sai); (4) nói rõ đây là điểm **chưa nhất quán cần dev/BA chốt** là thiếu sót cần bổ sung hay chủ đích — **không cam kết sửa, không hứa mốc**; (5) trong lúc chờ, muốn biết kết quả thật của giao dịch do job chốt thì đọc **mốc đối soát trong lịch sử bước xử lý** hoặc log lượt job chạy, **đừng** kết luận theo 2 cột phản hồi trên báo cáo; (6) khi sếp/dev hỏi thẳng *"đọc code xem có phải bug không"* → đưa **phán quyết** ngay trong group bằng ngôn ngữ nghiệp vụ kèm 2–3 căn cứ rút gọn (dữ liệu đã lấy về mà không ghi lại; đường còn lại ghi đủ từ đúng nguồn đó; hai đường lệch **cả hai chiều**), còn **vị trí code (file:line) gửi riêng Hoàng**, không đưa ra group. Ba phép thử để chốt bug hay chủ đích: `references/tra-soat-giao-dich.md` mục 12.1.

Hai điểm phụ cần thống nhất với dev khi trả lời: ô **nội dung phản hồi ở đường nút** đang lưu **mã lõi** (vd `00`) chứ không phải câu thông báo (tên cột ≠ giá trị), và mã phản hồi ở đường nút dùng quy ước NAPAS `000`/`01` khác kiểu mã SME `5xxxxx` lưu lúc duyệt cuối. Bảng chi tiết + cách kiểm bằng dữ liệu: `references/tra-soat-giao-dich.md` (mục 12).

## Tra cứu nhanh 1 giao dịch theo mã tester đưa + "mã TRN" là gì

Tester dán thẳng mã họ đọc trên app (`016254144594843`) và hỏi *"check giao dịch này"*, *"check mã TRN"*,
*"chi tiết mã X"*. Mã đó là **`traceNo`** trong log `napas-service` — KHÁC `napasRef` và KHÔNG phải
`transactionId`: grep `traceNo` → lấy `transactionId` (số) làm khoá truy mọi bước sau (tạo / duyệt /
từ chối / xác nhận / cập nhật trạng thái). **Chỉ grep `traceNo` là chưa đủ** để biết lệnh có đi tiếp
không — phải grep tiếp `transactionId`, vì các bước sau log theo id này.

**"Mã TRN" tester hỏi = `napasRef`** (`6254VNTTA2FFCPNC`) lưu trên thông tin lệnh, kèm **ngày cấp TRN**
(`napasRefDate`). TRN được cấp ở bước **tra tên người hưởng**, sớm hơn mốc tạo lệnh vài giây ⇒ mốc TRN
luôn đứng trước mốc tạo lệnh, đừng coi là bất thường.

- **Có TRN KHÔNG có nghĩa lệnh đã sang "Chờ xử lý"**: lệnh còn "Chờ duyệt" vẫn có TRN. Dấu hiệu lệnh
  đã thực thi là có **mã giao dịch lõi** (`coreRef`)/ngày tham chiếu — không phải TRN.
- TRN có thời gian sống (`...napas_v2.trn.ttl_hours`) nên TRN lúc tạo khác TRN lúc duyệt cuối là bình
  thường ⇒ khi trả TRN cho tester **luôn kèm ngày cấp**, và đừng khẳng định một con số TTL cụ thể.

Trả lời dạng này là **tra cứu nhanh**: 1–2 giao dịch thì trả thẳng trong group bằng bảng bọc code block
(trạng thái, TRN + ngày cấp, số tiền, người hưởng, mã risk nếu tester đang hỏi risk) — **KHÔNG cần dựng
PDF**; chỉ khi điều tra nhiều bước mới gửi file báo cáo **`.md` đủ các bước** (đừng bắt tester chờ file cho một tra cứu 30 giây).

## Thông tin risk core của một giao dịch (mã risk / bản ghi rủi ro)

Tester thường đưa **mã tra cứu NAPAS (traceNo)** dạng `0162551445950xx` — KHÁC `napasRef`
(`6255VNTTA2FF4HVR`). Grep traceNo trong log `napas-service` (pod mới nhất) để ra `transactionId`,
rồi lấy `transactionId` làm khoá cho mọi bước sau (đừng grep theo `napasRef`).

Giao dịch NAPAS 2.0 có **2 lớp thông tin risk**, trả lời phải tách rõ 2 lớp này:

- **"Có lưu mã risk core không"** = trong thông tin lệnh lúc tạo có mã rule core trả về (vd
  `VB_RULE_0001`) + nội dung cảnh báo vi/en (kiểu *"người nhận thuộc danh sách nghi ngờ rủi ro…"*).
  Lớp này **luôn CÓ**, kể cả lệnh tạo lúc cấu hình kiểm tra risk đang tắt.
- **"Có bản ghi rủi ro riêng không"** = đọc **cờ "đã kiểm tra risk" của chính giao dịch đó** tại bước
  tạo lệnh (`checkRiskScore`; `true` = có bản ghi). Kiểm chứng chéo bằng log: bước xác nhận **không** có
  warning `not found for transactionId: <id>`, và khi trạng thái GD được cập nhật thì có dòng
  `Update NapasRiskTransactionModel status to <trạng thái> for txId=<id>` → bản ghi tồn tại và
  **chạy theo vòng đời giao dịch** (GD sang thành công thì bản ghi theo luôn).

Cấu hình quyết định lớp 2: `check_risk_score.enable` (bật/tắt) + bảng cấu hình theo mã rule
(STOP → chặn ngay ở bước tạo lệnh; WARNING → cho tạo lệnh nhưng ghi nội dung cảnh báo + tạo bản ghi;
không có cấu hình cho mã đó → xử như nhánh tắt).

Câu hỏi kèm trạng thái GD (vd "cả 2 GD đều timeout 500069") → ghép luôn phần đối soát ở các mục trên:
lệnh đã cập nhật trạng thái thành công thì nói rõ, lệnh còn "chờ xử lý" thì đừng mô tả là thất bại.

## Pitfalls

- **Mã `VBG*` (VBG0408400, VBG040768) không có trong source vbsme và không có trong bảng mã lỗi AD_MESSAGE** — sinh ở tầng lõi/gateway. Đừng grep repo tìm định nghĩa (mất thời gian, không ra) — diễn giải nghiệp vụ: *"lõi báo không có bản ghi"* / *"lõi chưa có kết quả xử lý"*.
- **Không lấy comment/hằng số trong source làm sự thật về mã lỗi** — message khách thấy tra ở bảng mã lỗi theo `error_code_source` của scope-map.
- **"Chờ xử lý" không phải bug job**: đừng viết "job lỗi", "job kẹt", "cần restart job". Viết theo cơ chế: lõi chưa trả kết quả → hệ thống không có căn cứ chốt.
- Đừng nhầm **tra cứu trạng thái phía app** (khách bấm kiểm tra lại trên app) với **job đối soát** — cùng hỏi lõi theo TRN nhưng app không phải cơ chế chốt trạng thái; đừng lấy mốc thời gian app để giải thích lý do treo.
- Cửa sổ quét của job là điểm mấu chốt khi giải thích "sao mãi không tự đổi" — luôn nêu, đừng chỉ nói "job chạy mỗi 30 phút".
- **`500004` của tra soát ≠ mã chống bấm nhanh.** 500004 ném ra *trước* khi lock chống bấm nhanh được ghi, nên bấm lại nhiều lần vẫn ra 500004; mã chống bấm nhanh (`501015`) chỉ hiện khi lần trước đã qua được bước kiểm điều kiện. Tester hỏi "sao bấm mãi vẫn cùng một lỗi" → đó là dấu hiệu lỗi ở điều kiện trạng thái, không phải chống spam.
- **Hỏi trạng thái một mã GD mà chỉ đọc bảng giao dịch là thiếu.** Luôn đọc kèm bảng lệnh đã hoàn tất (lệnh có thể đã "chờ đối soát" + có TRN trong khi giao dịch vẫn "chờ duyệt" + trống TRN/ngày tham chiếu); lệch tầng là *bằng chứng*, không phải chi tiết phụ.
- **Giao dịch "đứng im" (`MODIFIED_DATE` đóng băng) trong khi bước trước báo thành công ⇒ nghi ghi DB thất bại âm thầm, đừng dừng ở "lệch trạng thái".** Kiểm độ dài BYTE của nội dung thông báo so với giới hạn cột (tiếng Việt 2–3 byte/ký tự; đường ghi chạy nền nên người dùng vẫn thấy thành công) — ô thông báo trên bảng lệnh/phase thường rộng hơn trên bảng giao dịch nên phase vẫn ghi được và che mất lỗi.
- **Báo cáo (hoặc 2 tầng dữ liệu) hiển thị 2 cột mâu thuẫn — vd trạng thái *Thành công* mà mã phản hồi vẫn là mã *chờ xử lý* ⇒ so BỘ TRƯỜNG mà TỪNG đường ghi, đừng chỉ so kết quả nghiệp vụ.** Hai đường xử lý có thể lấy về **cùng** dữ liệu nhưng chỉ một đường persist đủ trường (bước ghi của đường kia bỏ qua trường đó) ⇒ cột giữ nguyên giá trị cũ. Đọc thẳng bước cập nhật của cả hai đường và đối chiếu danh sách trường được set, rồi kiểm chứng bằng dữ liệu (`RESPONSE_CODE` / `RESPONSE_MESSAGE` trên bảng giao dịch) — kết luận "hệ thống không có dữ liệu đó" là sai, dữ liệu **đã được lấy về nhưng không được ghi lại**.
- **Kết luận "có/không bản ghi rủi ro" phải dựa vào cờ kiểm tra risk của CHÍNH giao dịch, KHÔNG dựa vào mốc giờ bật/tắt cấu hình.** Cấu hình bị đội test bật/tắt liên tục (nạp lại hàng chục lần/ngày) ⇒ hai giao dịch cùng ngày có thể khác nhau: lệnh tạo trước lúc bật thì không có bản ghi rủi ro, dù được xác nhận sau đó. Gặp chênh lệch → giải thích đúng cơ chế này cho tester ("khác nhau vậy là bình thường"), đừng để bị hiểu là bug.
- **Nhãn cột hiển thị trên màn hình/báo cáo (tiếng Việt, kiểu "mã phản hồi SME", "Báo cáo chi tiết giao dịch chuyển khoản") KHÔNG nằm trong repo backend** — grep theo nhãn trả 0 kết quả và rất tốn thời gian. Muốn map nhãn → trường thật: xác định bảng/cột DB (đối chiếu entity hoặc `sql_get_columns`) rồi mới đọc luồng nghiệp vụ theo tên trường.
- **Mốc giờ trong ngữ cảnh tin nhắn group lệch 7 giờ so với log**: mốc tin nhắn hiện theo UTC, còn autoindex + header log theo giờ VN (+07) ⇒ giao dịch tester hỏi lúc `07:5x` nằm ở `14:3x` trong log. Đừng kết luận "log ghi giờ tương lai" hay chọn nhầm pod — cộng 7 tiếng rồi mới khoanh vùng thời gian.
- **Đừng đếm/gán trạng thái bằng grep trên dòng log.** Mỗi dòng log là **một container của một request** nhưng bên trong chứa **nhiều giao dịch** ⇒ đếm `"status":"X"` theo dòng sẽ gán trạng thái của giao dịch này sang giao dịch khác. Phải `json.loads` dòng đó rồi duyệt cấu trúc, chỉ nhận object mang đúng `traceNo`/`transactionId` đang hỏi, và lấy mốc thời gian từ entry `REQUEST` của container.
- **Trước khi kết luận "sau đó lệnh không có hoạt động nào"**: xác nhận file log đang đọc phủ từ **lúc lệnh tạo tới hiện tại** (đọc mốc dòng đầu/dòng cuối file). Pod đang chạy gộp nhiều ngày vào **một** file, pod cũ là file riêng; cửa sổ không phủ thì phải lấy thêm pod / `worker-service` rồi mới kết luận.

## Verification

- Câu trả lời nêu được: (1) mốc thời gian nào lõi không phản hồi, (2) kết quả lượt đối soát gần nhất cho giao dịch đó, (3) phạm vi ảnh hưởng cả đợt, (4) vì sao không tự đổi trạng thái, (5) việc cần xác minh tiếp — và **không** có tên class/file/hằng số.
- File báo cáo **`.md`** đã gửi lên đúng space/thread dưới dạng file thật (đọc lại message vừa gửi để chắc), và tin nhắn Chat chỉ có kết luận ngắn — không dán log dài.
