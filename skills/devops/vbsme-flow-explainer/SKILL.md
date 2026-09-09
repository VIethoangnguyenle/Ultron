---
name: vbsme-flow-explainer
description: "Use when devs ask to explain a vbsme business flow."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, flow, sequence, diagram, dev-support]
    related_skills: [vbsme-db-lookup, vbsme-error-diagnosis, architecture-diagram]
---

# vbsme flow explainer (VietBank SME)

When a **developer OR tester** teammate asks to explain a business flow/sequence (e.g. "Giải thích luồng chuyển tiền Napas 24/7"), the deliverable is a **markdown file with diagrams**, not a short chat reply.

Audience = mixed (dev + tester). Keep it flow-first and easy to understand — a tester should be able to follow it without deep technical knowledge; a dev should get enough to trace it. When in doubt, err simple.

## Output = one markdown report, easy to read (flow-first, not technical)

Purpose is to explain the **flow clearly and simply** — not a deep technical spec. Keep it readable for a teammate who wants to understand the process. Save to `vietbank-sme/docs/flows/<slug>-flow.md`:

1. **Tóm tắt nghiệp vụ** — 3-4 câu: flow làm gì, ai khởi tạo, kết quả cuối. Ngôn ngữ nghiệp vụ, dễ hiểu.
2. **Sequence diagram** — Mermaid `sequenceDiagram`: các bên tham gia (khách hàng → app → hệ thống → ngân hàng) và chuỗi thao tác theo thứ tự. Đây là trái tim của file.
3. **Các bước chính** — gạch đầu dòng ngắn gọn, mỗi bước 1 câu: làm gì + kết quả. Kèm mã lỗi hay gặp ở bước đó (chỉ khi cần thiết).
4. **Bảng DB liên quan** — phần phụ trợ NHẸ: liệt kê các bảng flow đụng tới (tên bảng + 1 dòng mục đích). Không đào sâu cột/kiểu dữ liệu trừ khi người hỏi yêu cầu.
5. **Điểm lưu ý** (tùy chọn, ngắn) — 2-3 ý: cấu hình hay gặp, chỗ dễ kẹt, ràng buộc quan trọng.

Tone: business-first, dễ hiểu. Technical details (đọc/ghi chi tiết, cột, index) chỉ thêm khi người hỏi hỏi sâu.

Post the mermaid code + a short summary into the chat; the full file goes to disk (files may fall back to a host-path notice if `/setup-files` is not active).

## Sources of truth (in order)

1. **Domain graph** — query `mcp__understand_anything__get_domain_flow_detail(flow_name=...)` / `get_domain_detail` for the already-extracted flow + steps (fast, already business-labelled). The graph also carries `table` nodes (132 indexed) — use them to enumerate DB tables.
2. **Source code** — CodeGraph / Serena / `search_files` to confirm entry points, handlers, and the exact call chain. For DB tables: find each entity class's `@Table(name=...)` / `@Collection` (Mongo) and its repository, then read the columns via `mcp__db_access__sql_get_columns`.
3. **DB** — `AD_MESSAGE` for error code meanings, `AD_CONFIG` for config-driven branches; `sql_get_columns` to confirm each table's real columns.

## Diagrams — use the diagram-design skill

- Mermaid blocks are the default for a `.md` deliverable (render on GitLab/GitHub/VS Code).
- When a **polished standalone diagram** is wanted (HTML/SVG/PNG, branded, print-quality), load the `diagram-design` skill at `/home/zane/Desktop/tools/diagram-design/skills/diagram-design/SKILL.md` and follow it — it supports sequence, flowchart, architecture, swimlane, data-flow, etc. Produce the `.html` beside the `.md` and link it.
- Sequence-diagram complexity budget: ≤5 lifelines, ≤1 combined fragment. Split into overview + detail if the flow exceeds it.

## Rules

- **Never paste internal source code** — explain in business language; diagrams carry service/actor names and arrows, not code.
- **Confirm scope first** if the flow name is ambiguous (multiple flows share a prefix).
- Trace exactly what the code does — don't invent steps. Verify each hop against the domain graph / source.
- Report in Vietnamese.
