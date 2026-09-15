---
name: ultron-ba-mcp
description: Use when operating the Ultron BA MCP port.
---

# Ultron BA MCP — cổng hiểu hệ thống cho agent của BA/Tester

Cổng HTTP MCP **chỉ đọc**, để agent của BA/Tester (Claude Desktop/Cursor/Antigravity/Codex) tự tra
hệ thống mà viết URD/user case và phủ test case. Hoàng chốt 15/09/2026: phát cho *cả BA và Tester*,
*tối ưu cho agent* (không tối ưu cho người đọc), **không cần cắt mã nguồn** — nhưng vẫn cấm secret/
credential trong dữ liệu trả về.

## Vị trí & vận hành
- Code: `/home/zane/Desktop/tools/mcp/Ultron-BA-MCP/` (Python, FastMCP 1.27.x, `streamable-http`,
  `json_response` + `stateless_http`; dùng lại `kg_loader` của repo `Understand-Anything-MCP` — chỉ import, không sửa).
- Service: unit user `ultron-ba-mcp` (unit mẫu ở `deploy/`). Cổng `9450`, đường dẫn MCP `/mcp`, health `GET /healthz`.
- Bind: `127.0.0.1` **luôn** + IP tailnet khi node mở (mẫu `siri_speak.py`). Người ngoài vào qua
  `http://ultron:9450/mcp` (tên MagicDNS, đừng dùng IP).
- 16 tool, 3 nhóm: định hướng (`server_info`, `list_projects`, `search`) · nghiệp vụ
  (`get_domain_overview`, `get_domain`, `get_flow`, `get_business_rules`, `get_api_contract`,
  `get_knowledge_card`, `get_db_dictionary`, `explain_error_code`, `search_error_codes`,
  `suggest_test_scenarios`) · mức code (`get_implementation`, `trace_impact`, `find_path`).
  Mọi câu trả lời có `{ok, data, meta, hints}`; `meta` mang dự án + mốc + độ mới, `hints` gợi ý bước sau.
- Khoá API: `scripts/keys.py {add,rotate,disable,enable,list,remove}` — `keys.json` chỉ giữ sha256;
  key thô in **đúng một lần** (hoặc ghi ra file bằng `--out`, quyền 600). Key của Hoàng:
  `~/.hermes/state/ba_mcp/hoang.key`.
- Audit mọi lượt gọi: `~/.hermes/state/ba_mcp/audit.jsonl` (tool, nhãn key, hash tham số, ms, bytes).
- Dữ liệu đệm: `data/error_codes.json` (danh mục mã lỗi từ `AD_MESSAGE` qua db-access) và
  `data/db_schema.json` (schema SIT) — làm mới bằng `scripts/refresh_error_codes.py`, không truy DB lúc phục vụ.

## Kiểm chứng sau mỗi lần sửa (đừng tin agent code tự báo)
Chạy sẵn: `python3 scripts/verify_port.py` trong skill này (dùng venv của project) — 15 ca dưới đây,
in PASS/FAIL và exit != 0 nếu có ca hỏng. Script tự cấp key tạm rồi xoá, không in key thô.
1. Không key / sai key / key đã thu hồi → `401`; key đúng → `200`.
2. `tools/list` đúng số tool, tên không đổi; gọi **thật** từng tool bằng tham số đúng schema.
3. Tất định: gọi 2 lần cùng tham số → kết quả giống hệt.
4. `max_chars=500` → `truncated=true` và độ dài thật ≤ ngưỡng.
5. Hạn mức: tạo key `rpm=3` → lượt 4-5 phải `429` + `retry_after_s`; xong thì thu hồi/xoá key test.
6. Audit: số dòng tăng **đúng** số lượt gọi.
7. `ss -ltnp | grep 9450` → có cả `127.0.0.1` và IP tailnet.
8. Quét câu trả lời xem có lộ key thô không.

## Danh tính dự án — câu hỏi "đang trả lời cho dự án nào" (Hoàng chốt 15/09: *dùng key đi nhé*)
Dự án là chuyện của **cổng**, không để agent tự suy luận:
- Key mang **dự án mặc định**; key scope đúng 1 dự án ⇒ bỏ trống `project` là tự dùng dự án đó;
  truyền `project` ra ngoài scope ⇒ chặn (`PROJECT_OUT_OF_SCOPE`), không tự đổi sang default.
- Key `*` + bỏ trống `project` + có >1 dự án ⇒ `BAD_ARG` kèm danh sách id (không đoán).
- Câu hỏi liên dự án: chỉ khi key `*` và gọi `project:"*"` ⇒ mỗi kết quả gắn nhãn dự án.
- Mọi response ghi `meta.project` + `meta.project_source` (`arg` | `key_default` | `scope_only`).
- Phát cho BA/Tester: cấp **một key mỗi nhóm mỗi dự án** (`ba-vbsme`, `test-vbsme`, `ba-digital`…).
- Bí danh (`vbsme`/`SME`/`digital`…) quy về id chuẩn; id hợp lệ ghi thẳng vào `instructions` của cổng.

## Hợp đồng tham số & phân trang (chốt sau v7/v8 — đo lại bằng tay 15/09)
- Mọi tool danh sách: `limit` **có tác dụng thật**, `shown == len(danh sách)` **luôn luôn**, `total` = tổng khớp
  (không phải số sau khi cắt), đi tiếp bằng `offset` = `meta.next_offset`; `cursor` cũng nhận **cùng ngữ nghĩa**.
- Tham số sai tên / giá trị rác (`offset=-1`, `offset="x"`, `offset` vượt biên, `limit=0`, `zzz_nonsense`, `limt`)
  ⇒ `BAD_ARG` kèm danh sách tham số hợp lệ. **Cấm nuốt im lặng** — xem mục bẫy bên dưới.
- Chạy lại bộ kiểm tay: `scripts/verify_port.py` (15 ca lõi) + `scripts/verify_port_pagination.py` (12 ca phân trang/tham số).
  Cả hai cần key thật của Hoàng (`~/.hermes/state/ba_mcp/hoang.key`), chạy bằng venv của project.
- Tài liệu bàn giao cho BA/Tester: `README.md` trong project (cắm client, bảng 16 tool, câu hỏi mẫu, giới hạn đã biết).

## Bẫy đã trả giá
- **Độ mới phải so theo REF/dòng lịch sử, không theo bản checkout.** Workspace vbsme là nhiều repo con;
  checkout có thể đang ở nhánh feature trong khi graph dựng từ `dev-sit` ⇒ diff `graph_ref..HEAD` đếm
  cả nghìn file "đổi" giả và kết luận `VERY_STALE` sai bản chất. Đúng phải là: `graph_ref` là tổ tiên
  của HEAD ⇒ mới kết luận FRESH/STALE; khác dòng ⇒ `DIVERGED` + nói rõ, và nếu cần độ cũ thật thì so
  `graph_ref` với `origin/<nhánh gốc>`.
- **Gọi tool sai tên tham số** ⇒ MCP trả `isError` (không phải kết quả `ok=false`), client dễ hiểu nhầm
  là "tool hỏng". Trước khi kết luận, đọc `inputSchema` từ `tools/list` rồi gọi lại.
- **Chờ job trước rồi mới giao job sau: dùng `kill -0 <PID>`, KHÔNG dùng `pgrep -f "<chuỗi spec>"`.**
  `pgrep -f` khớp cả chính tiến trình wrapper đang chạy vòng chờ (đường lệnh của nó chứa chuỗi đó)
  ⇒ vòng lặp không bao giờ hết và job sau không bao giờ chạy. Trị số PID thì không tự khớp.
- **Nuốt im lặng là lỗi tệ nhất ở cổng cho agent** (đo được 4 ca trong 1 buổi): `limit` khai mà bỏ qua;
  `meta.next_cursor` quảng cáo nhưng chỉ nhận `offset`, truyền `cursor=3` ⇒ **trả lại trang 1 với `ok=true`**;
  giá trị rác cũng vậy. Agent không có cách nào biết mình đang đọc sai. Luật: (1) tên quảng cáo phải nhận
  đúng tên đó hoặc báo lỗi rõ; (2) tham số sai/rác ⇒ `BAD_ARG`; (3) rà cả 16 tool, tham số nào khai mà
  không có tác dụng thì sửa hoặc gỡ.
- **Smoke test của người viết code KHÔNG thay được kiểm chứng tay.** Bộ ca tự nghĩ thường chỉ chạy 1 trang,
  chỉ truyền đúng tên tham số mà người viết biết ⇒ 2 lỗi trên vẫn báo PASS. Luật số 1 khi nghiệm thu: dùng
  công cụ như *người dùng thật* (tên trường cổng tự quảng cáo, giá trị rác, đi nhiều trang) rồi mới tin.
- **Giao việc cho claude: đừng nhồi prompt dài vào dòng lệnh** — dấu nháy/apostrophe trong câu tiếng Việt
  làm bash chết `unexpected EOF while looking for matching quote` (job thoát ngay, file không đổi).
  Cách đúng: viết spec ra file rồi giao `claude -p 'Doc spec <path> va lam theo'` (nháy **đơn**,
  prompt ngắn, không ký tự đặc biệt).
- **Khớp mờ mà không khai là khớp mờ = nguy hiểm nhất.** Đo trên bản 15/09: `get_flow("zzz khong ton tai xyz")`
  vẫn trả `ok=true` một luồng bất kỳ (*"Chi tiết tài khoản thanh toán"*), không dấu hiệu nào cho biết là đoán ⇒
  BA viết URD từ luồng sai mà không biết. Luật: mọi tool tra theo tên phải trả `match{kind,score}`;
  điểm thấp ⇒ `NOT_FOUND` + `nearest[]`, **cấm** trả thực thể không liên quan với `ok=true`.
- **Đo độ mới thật của graph (15/09):** vbsme — `graph_ref` 7225eac1f **chính là** HEAD của `origin/dev-sit`
  (0 commit lệch) ⇒ graph FRESH, `VERY_STALE` trước đó chỉ là artefact so sai nhánh. digital — meta ghi
  `gitCommitHash: not-a-git-repo` ⇒ không có dòng lịch sử git, `UNKNOWN` là trả lời đúng, đừng "sửa" thành FRESH.
- `find_path`/`trace_impact` gốc chỉ hiểu ref mức code (`class:`/`file:`/`function:`) — muốn hỏi bằng ref
  nghiệp vụ (`domain:`/`flow:`/`step:`) thì phải resolve qua domain graph trước.

## Giới hạn dữ liệu đã biết (nói thẳng khi bàn giao)
- 6/36 domain của vbsme không có đường xuống code (graph dựng thiếu), vd `quan-ly-mat-khau`; tool trả
  NOT_FOUND có giải thích — muốn hết phải **dựng lại graph**, không phải lỗi cổng.
- `vietbank-digital`: meta.json ghi `gitCommitHash: not-a-git-repo` ⇒ không có mốc git, độ mới là `UNKNOWN_REF`.
- `trace_impact` ra `total=0` cho handler đăng ký qua registry (cạnh import nằm ở mức file) — giới hạn của graph.
- `get_db_dictionary` trả trọn cột mỗi bảng ⇒ trang vài bảng có thể vượt `max_chars`; dùng `offset` để lấy nốt.

## Hệ quả với luật Tailscale
Cổng nằm trên tailnet ⇒ **tắt theo node lúc 17h30** (luật Hoàng chốt 2026-09-12). Muốn BA/Tester dùng
thì node phải đang mở; đừng hẹn ai dùng sau 17h30. Cổng local `127.0.0.1:9450` vẫn sống 24/7.
