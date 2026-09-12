---
name: db-code-discrepancy-triage
description: "Use when DB master data and code declarations disagree."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, dev-support, triage, db, source-code, evidence]
    related_skills: [tester-support, vbsme-db-lookup, vbsme-flow-explainer]
---

# DB master data vs code declarations — triage

## Khi dùng

Câu hỏi kiểu *"tại sao mã X có trong bảng danh mục (`AD_SERVICE`, `AD_CONFIG`, `AD_MESSAGE`...) mà
không có trong hằng số/enum/config của code?"* — hoặc chiều ngược lại. Đây là câu hỏi **chứng minh**,
gần như **không bao giờ là bug**: danh mục master data và khai báo trong code là hai tập khác nhau,
mỗi cái phục vụ một mục đích. Nhiệm vụ là dựng bằng chứng rồi kết luận, không đoán.

Đừng dùng khi: câu hỏi thuộc quy trình flow (dùng `vbsme-flow-explainer`) hay tra mã lỗi cho tester
(dùng `tester-support`).

## Quy trình (làm đủ bước rồi mới kết luận)

1. **Đọc bản ghi trong DB trước** — danh mục là nguồn sự thật về dữ liệu. Oracle bắt buộc prefix schema:
   `SELECT CODE, TYPE, VI_NAME, IS_ACTIVE, STATUS FROM VBSMEONL.AD_SERVICE WHERE CODE = '<mã>'`, rồi tra
   nhóm ở `VBSMEONL.AD_SERVICE_TYPE WHERE CODE = '<TYPE>'`. Lấy cả `CREATED_DATE`/`MODIFIED_DATE` —
   bản ghi vừa bị sửa thường là dữ liệu test chứ không phải nghiệp vụ.
2. **Grep literal trong source** (đừng bắt đầu bằng graph — xem Pitfalls):
   `cd /home/zane/Desktop/work/vietbank/vietbank-sme && grep -rn --include=*.java -w "<mã>" vietbank-sme-omni dvnh-common viet-bank-ekyc-sme`
   **0 hit là bằng chứng mạnh**: code chưa từng tham chiếu giá trị đó ⇒ nó chỉ sống trong danh mục.
   Chạy cho **cả workspace** (mỗi repo con có thể định nghĩa bản sao hằng số của riêng nó).
3. **So sánh mã anh em theo cả hai chiều** — bằng chứng thuyết phục nhất khi trả lời: chọn vài mã mà code
   CÓ dùng và vài mã code KHÔNG dùng trong cùng nhóm/tầng, grep từng mã, rồi chỉ ra sự lệch hai chiều ⇒
   chứng minh khai báo trong code là **tập con chọn lọc** (chỉ mã cần rẽ nhánh), không phải bản sao danh mục.
4. **Đọc khai báo khi cần đối chiếu**: `mcp__understand_anything__get_node_source` trên node class tương
   ứng — nhớ truyền `project=<tên project>` (thiếu sẽ báo "Multiple projects loaded"). Tên node lấy từ
   `query_nodes` theo **tên khái niệm**, không theo literal.
5. **Kết luận + trả lời** theo hình dạng bên dưới.

## Trả lời (Hình dạng)

- **Ngôn ngữ nghiệp vụ, không code**: nói "danh mục dịch vụ / danh mục cấu hình" vs "khai báo trong code".
  KHÔNG nêu tên class, tên hằng số, tên file, đường dẫn `.java` — kể cả khi người hỏi là dev và tự nêu
  tên class trong câu hỏi (đó là luật bảo mật của Hoàng, không phải sự né tránh).
- **Nêu cơ chế ở mức người đọc hiểu được**: danh mục là dữ liệu chuẩn, hệ thống nạp lúc chạy và tra theo
  mã; khai báo trong code chỉ dùng cho chỗ **cần rẽ nhánh** (điển hình: chặn phiên bản app tối thiểu theo
  từng chức năng). Nhánh nào không cần rẽ nhánh thì không cần hằng số.
- **Đưa ví dụ 2 chiều** để người hỏi tự kiểm chứng (mã có trong code / mã không có trong code).
- **Trả lời thẳng trong chat**, KHÔNG dựng file `.md`/`.pdf` — đây là câu hỏi tra cứu hẹp, không phải
  yêu cầu explain-flow. Chỉ xuất file khi người hỏi yêu cầu rõ.
- Không lộ tiến trình tra cứu (grep/query/đọc source) ra group — chỉ đưa kết quả cuối.

## Pitfalls

- **`query_nodes` KHÔNG tìm được literal.** Nó tìm mờ theo *khái niệm*: literal `01101` trả về 0 node,
  còn tên chung kiểu `AdService` trả về hàng trăm node nhiễu. Literal (mã, tên cột, URL) → grep repo;
  đường dẫn → `search_by_file_path`; chỉ dùng `query_nodes` cho tên khái niệm.
- **Nhiều bản sao của cùng một class hằng số** trong các service khác nhau (auth / transfer / bank / napas
  / onboard...). Câu hỏi "code có mã X không" phải hiểu là *toàn repo* → grep cả workspace rồi mới kết luận.
- **Dữ liệu SIT lẫn rác test**: các bản ghi kiểu `Pentest123456`, `a`, `12` nằm chung bảng danh mục với mã
  nghiệp vụ thật (có bản `IS_ACTIVE = 0`). Thấy mã lạ phải soi nguồn/người tạo trước khi coi là nghiệp vụ.
- **Đừng kết luận "thiếu hằng số = bug"** rồi hứa sửa/thêm hằng số — đó là thay đổi source, thuộc quyền
  Hoàng quyết; chỉ giải thích hiện trạng.
- **Đừng biến việc tra cứu hẹp thành task nặng**: một lệnh grep + một query DB là ra đáp án; giữ ngữ cảnh
  gọn (kết quả dài ghi ra file, không nhồi vào ngữ cảnh).

## Kiến thức nền theo dự án

- vbsme (danh mục dịch vụ `AD_SERVICE` / `AD_SERVICE_TYPE`, vai trò thật của khai báo mã dịch vụ trong
  code, cache lúc chạy): `references/vbsme-service-catalog.md`.

## Verification

- Query DB trả đúng bản ghi mã cần tra + tên nhóm của nó.
- Grep literal đã chạy trên **cả 3 repo** và kết quả 0 hit (hoặc liệt kê được hit cụ thể).
- Có ít nhất 1 ví dụ mã CÓ trong code và 1 ví dụ mã KHÔNG có, cùng grep chứng minh.
- Câu trả lời gửi đi không chứa tên class/hằng số/file/đường dẫn source.
