# Đọc log UAT của VBSME (portal log) — công thức chạy được

Log source (scope-map): `https://10.22.17.219:10443/omni-sme/` (UAT), LIVE ở `/omni-sme/live/`.
Chứng chỉ tự ký ⇒ LUÔN `curl -k`. UAT/LIVE **không có DB** — chỉ có log, đừng hứa query DB UAT.

## 1. Liệt kê file log của một service

Mỗi service là một thư mục Apache autoindex:

```bash
curl -k -s -m 40 "https://10.22.17.219:10443/omni-sme/napas-service/" -o dir.html -w "%{http_code} %{size_download}\n"
```

Parse bằng `href`, **không** lấy text trong `<td>` (ô tên file bị rút gọn dạng `sme-napas-656…..log..>`):

```python
import re, html
h = open("dir.html", encoding="utf-8", errors="replace").read()
for m in re.finditer(r"<tr>.*?</tr>", h, re.S):
    n = re.search(r'href="([^"?][^"]*)"', m.group(0))
    d = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2})", m.group(0))
    if n:
        print(html.unescape(n.group(1)), d.group(1) if d else "")
```

Chọn file có mốc thời gian phủ khoảng cần tra (bản mới nhất = pod đang chạy). Có cả thư mục ngày/tháng (`2026-09/`).

## 2. Tải log về

```bash
curl -k -s -m 300 -o /tmp/uatlogs/<ten>.log "https://10.22.17.219:10443/omni-sme/<service>/<pod>.log"
```

Log 5–20 MB tải bình thường, không cần `.gz`. Tải nhiều pod cùng lúc rồi grep chung thư mục.

## 3. Service nào có log

`napas-service`, `worker-service`, `dmz-channel-gateway`, `transfer-service`, `bank-service`,
`approval-service`, `nonfinancial-service`, `bo`… (mỗi service nhiều pod ⇒ nhiều file `.log`).

- `worker-service`: chứa **job nền / đối soát** (`transaction.napas_reconciliation.*`) — cần khi hỏi
  "giao dịch treo rồi xử lý thế nào", cập nhật trạng thái lệnh, core ref.
- `napas-service`: luồng tạo lệnh / xác nhận NAPAS, metadata giao dịch, mã risk.
- `dmz-channel-gateway`: request từ app/web vào.

## 4. Đọc log

- Header mỗi dòng: `[version-build][yyyy-MM-dd HH:mm:ss.SSS]` — **giờ +07**, dùng để cắt mốc thời gian.
- Dòng request log là **JSON một dòng rất dài** (hàng chục KB) ⇒ grep theo `trace`/`requestId`/`transactionId`
  rồi extract field bằng regex, đừng in cả dòng (tràn ngữ cảnh).
- Ví dụ tìm một giao dịch: `grep -n "625418459492" *.log | cut -c1-400`, rồi python `re.findall` lấy
  `requestId`, `path`, `code`, `riskScore`, `checkRiskScore`, `napasRef`…
- Log bị xoay vòng theo pod: nếu không thấy giao dịch cũ, tải thêm pod khác hoặc thư mục tháng.
