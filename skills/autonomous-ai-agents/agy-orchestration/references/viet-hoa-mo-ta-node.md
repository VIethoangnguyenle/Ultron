# Pipeline việt hoá mô tả node đã có (agy + JSON schema)

Dùng khi graph đã có node/cạnh nhưng `summary` còn câu máy sinh tiếng Anh ("Performs X operation in Y",
"Retrieves moduleError data", "File: <path>") hoặc câu khuôn sáo. Đã chạy thật cho **vietbank-digital**
(2026-09-15, 366 node → 15 lô, model `claude-opus-4-6-thinking`).

## Nguyên tắc
1. **Nhóm node theo FILE nguồn**, không theo thứ tự id — 1 lượt agy thấy trọn file sẽ viết mô tả đúng
   quan hệ giữa các hàm (pipeline pre/around/post, cache, sự kiện…) thay vì mô tả rời rạc.
2. Mỗi lô ≤ ~30 node và ≤ ~50KB source; file >50KB thì cắt bớt (giữ phần liên quan).
3. Node không có file thật (`class:.../external:<JDK class>`, doc bị thiếu) → gom 1 lô riêng, dặn model mô tả
   theo tên + loại, **không bịa** hành vi.
4. Prompt phải nói rõ: 1–2 câu tiếng Việt, nói việc THẬT (nhận gì/trả gì/gọi đâu/điều kiện gì), CẤM câu
   khuôn sáo, enum/hằng số thì nêu mã lỗi/trạng thái cho nghiệp vụ nào, file cấu hình thì nêu cấu hình gì.
5. Ghi ra file riêng của lô rồi mới apply — KHÔNG để model ghi trực tiếp vào graph.

## Lệnh
```
agy --model claude-opus-4-6-thinking --print-timeout 15m --output-format json \
  --json-schema schema.json -p "$(cat prompts/batch_NN.txt)" > out_opus/batch_NN.raw
```
(schema: `{"type":"object","properties":{"items":{"type":"array","items":{"type":"object",
"properties":{"id":{"type":"string"},"summary":{"type":"string"}},"required":["id","summary"]}}},
"required":["items"]}` — nhưng vẫn phải parse phòng thủ, xem mục "Đừng tin `--json-schema`" trong SKILL.md.)

## Apply (luôn theo thứ tự này)
1. `shutil.copy2(knowledge-graph.json, ...bakN-<ts>)` **trước** khi sửa.
2. Chỉ đổi field `summary` theo `id`; KHÔNG đụng `nodes`/`edges`/`layers`/`tour`.
3. Ghi ra `.tmp` rồi `os.replace` (atomic) — tránh file graph 24MB hỏng giữa chừng.
4. Kiểm lại bằng chính file vừa ghi: số node/cạnh không đổi, `len(set(ids))==len(ids)`,
   cạnh mồ côi = 0 (**cạnh dùng `source`/`target`, KHÔNG phải `from`/`to`**), summary rỗng = 0,
   và đếm lại node còn dấu hiệu tiếng Anh (regex dấu tiếng Việt) → phải giảm đúng bằng số node đã sửa.
5. Domain-graph: node `step:<kg_id>` dùng lại mô tả của node KG tương ứng (bỏ tiền tố `step:`) — đừng
   gọi agy thêm lần nào cho phần này.

## Kiểm chất lượng mô tả mới
- Có dấu tiếng Việt (regex `[àáạảãâầấậẩẫă...]`), độ dài ≥ 40 ký tự.
- Không khớp khuôn câu cũ: `^(Thực thi phương thức|Đóng vai trò là|Xử lý ... trong lớp)`.
- Số id khớp 100% với danh sách node cần sửa, không id lạ.

## Khi lô bị trả RỖNG (exit 0, size 0) — thứ tự xử lý đã kiểm chứng
1. **Kiểm size từng lô** (`find out -size 0c`) — đừng tin exit code.
2. **Chia nhỏ theo mốc `===== FILE:`**: mỗi prompt ≤2 file nguồn, ≤16-18KB. Lô 33-49KB hay fail, lô 3-17KB
   chạy ~50s/lô. Giữ nguyên header, lọc lại danh sách node theo đúng file có trong prompt.
3. **Timeout phải rộng hơn cả thang model**: cạn quota thì wrapper đi hết 9 attempt ≈ 8 phút ⇒ dùng
   `timeout 600`+; đặt 300s là tự cắt ngang (exit 124, công cốc).
4. **Quota cạn cả 2 account ⇒ đừng đốt thêm**: giao subagent TỰ đọc source và tự viết mô tả (không qua agy).
   Đã dùng cho 44 node/12 file: 3 subagent song song ~10 phút, chất lượng tương đương. Prompt cho subagent:
   đưa `list.json` (filePath → [node id]), yêu cầu ghi `out_<k>.json` = mảng `{id, summary}`, CẤM gọi CLI agy/claude.
5. Với file bảo mật/khóa: dặn subagent chỉ nêu vai trò nghiệp vụ, không mô tả chi tiết thuật toán khóa.
6. Kiểm chứng cuối bằng MCP `understand_anything` (`get_node_detail`) — graph đã nạp lại mô tả mới chưa.
