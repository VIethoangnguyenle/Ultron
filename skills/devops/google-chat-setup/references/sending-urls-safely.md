# Gửi URL/chuỗi ký tự đặc biệt qua Google Chat — coi chừng markdown ăn ký tự

## Luật

Chuỗi dài có `_` hoặc `*` (URL OAuth, token, mã base64url, chuỗi băm) **PHẢI bọc trong code block**
(``` ... ```). Google Chat hiểu `_chữ_` = *nghiêng* và `*chữ*` = **đậm** ⇒ **nuốt mất dấu** ⇒ chuỗi
bị sai mà mắt thường khó thấy.

- SAI: dán URL trần → `...Lu6_wB8aC...` gửi đi thành `...Lu6wB8aC...` (mất `_`).
- ĐÚNG: đặt URL trong ``` ``` — Chat không parse markdown trong code block ⇒ copy ra là nguyên bản.
- Code block thì **không bấm được link** ⇒ nói rõ với người nhận: "copy nguyên dòng này".

## Cách kiểm trước khi gửi

Đếm ký tự đặc biệt trong chuỗi gốc rồi đối chiếu với thứ mình sắp ghi ra:

```
python3 -c "s='<chuoi>'; print(len(s), s.count('_'), s.count('*'))"
```

Nếu chuỗi ra từ file/log: `grep -m1 '^https' file.txt` rồi copy đúng kết quả, **đừng gõ lại tay**.

## Triệu chứng đã gặp thật

- OAuth consent URL bị mất `_` trong `code_challenge` ⇒ Google trả
  **400: invalid_request — "Code Challenge must be base64 encoded"**.
- Triệu chứng chung: link "mở ra lỗi lạ", API trả 400/401 dù token/mã đúng — kiểm ký tự trước khi
  nghi ngờ logic.

## Ghi chú

PKCE `code_challenge` là base64url nên **hay** chứa `_` và `-`; state random cũng có thể có `_`.
Giữ tiến trình flow sống trong lúc chờ người dùng bấm ⇒ gửi lại đúng URL là chạy được, không cần làm lại từ đầu.
