---
name: vbsme-flow-explainer
description: "Use when explaining any vbsme flow, mechanism, or base source."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vbsme, vietbank, flow, sequence, diagram, dev-support]
    related_skills: [vbsme-db-lookup, vbsme-error-diagnosis, architecture-diagram]
---

## Output = one markdown report, easy to read (flow-first, not technical) — delivered as BOTH .md AND .pdf

Always produce **two files**: a `.md` (source of truth, editable + searchable) and a `.pdf` (read-only, easy for testers / non-technical readers). The PDF must have the mermaid diagrams already rendered to images (mermaid does not render in PDF on its own).

**Build the PDF from the markdown** after writing it:
1. Write the `.md` (with mermaid `sequenceDiagram`/`flowchart` blocks).
2. Render the mermaid blocks to images. Tooling on this machine: `mmdc` and `pandoc` are MISSING, but `node`/`npx`, `google-chrome` (headless), and `weasyprint` are present. Render mermaid via `npx -y @mermaid-js/mermaid-cli -i in.mmd -o out.svg` (npx will fetch it), OR assemble an HTML that loads mermaid.js and print to PDF via chrome headless. Proven working command (CDN mermaid v10 + `--virtual-time-budget` so mermaid has time to render before print):
   `google-chrome --headless --disable-gpu --no-sandbox --no-pdf-header-footer --print-to-pdf=out.pdf --virtual-time-budget=25000 file://$PWD/in.html`
   (weasyprint does NOT run JS, so it won't render mermaid — pre-render to SVG first if using weasyprint. Verify the PDF by `pdftotext -layout out.pdf` and grepping that `flowchart TD`/`sequenceDiagram`/`classDiagram` are ABSENT — absent = rendered to vector; `pdftoppm -png` if you need a visual check.)
3. Produce the `.pdf`: either chrome headless on the HTML (mermaid rendered inline), or `weasyprint in.html out.pdf`.
4. If the render chain fails or tools are unavailable, still deliver the `.md` and say plainly the PDF needs `mmdc`/chrome to render — never ship a PDF with raw mermaid text.

Save both to `vietbank-sme/docs/flows/<slug>-flow.md` and `<slug>-flow.pdf` (or a fitting subfolder of `docs/`).

Covers **BOTH** business flows AND base-source / framework questions (dvnh-common, CQRS, factory, security, cache, gRPC/Kafka pipeline, logging, interceptor, config mechanism, common patterns...). Any "how does X work" question — business or infra — gets the same treatment.

Purpose is to explain **clearly and simply** — not a deep technical spec. Keep it readable for a teammate who wants to understand the process. Structure of the `.md`:

1. **Tóm tắt nghiệp vụ** — 3-4 câu: flow làm gì, ai khởi tạo, kết quả cuối. Ngôn ngữ nghiệp vụ, dễ hiểu.
2. **Sequence diagram** — Mermaid `sequenceDiagram`: các bên tham gia (khách hàng → app → hệ thống → ngân hàng) và chuỗi thao tác theo thứ tự. Đây là trái tim của file.
3. **Các bước chính** — gạch đầu dòng ngắn gọn, mỗi bước 1 câu: làm gì + kết quả. Kèm mã lỗi hay gặp ở bước đó (chỉ khi cần thiết).
4. **Bảng DB liên quan** — phần phụ trợ NHẸ: liệt kê các bảng flow đụng tới (tên bảng + 1 dòng mục đích). Không đào sâu cột/kiểu dữ liệu trừ khi người hỏi yêu cầu.
5. **Điểm lưu ý** (tùy chọn, ngắn) — 2-3 ý: cấu hình hay gặp, chỗ dễ kẹt, ràng buộc quan trọng.

Tone: business-first, dễ hiểu. Technical details (đọc/ghi chi tiết, cột, index) chỉ thêm khi người hỏi hỏi sâu.

Post into the chat: a short **text summary only** (no mermaid code, no diagrams) — the flow in plain language, a few short lines + the file path. Mermaid/diagrams live ONLY in the markdown file (deliver via file, or a host-path notice if `/setup-files` is not active). Google Chat does NOT render mermaid — pasting it into chat turns into unreadable raw text.

## Sources of truth (in order)

1. **Domain graph** — query `mcp__understand_anything__get_domain_flow_detail(flow_name=...)` / `get_domain_detail` for business flows. For base/framework questions use the `dvnh-common` project graph (also registered in understand-anything) + CodeGraph/Serena on `dvnh-common/` source.
2. **Source code** — CodeGraph / Serena / `search_files` to confirm entry points, handlers, and the exact call chain. For DB tables: find each entity class's `@Table(name=...)` / `@Collection` (Mongo) and its repository, then read the columns via `mcp__db_access__sql_get_columns`. For base-source questions, read `dvnh-common/` (framework modules: cqrs, factory, security-*, cache, grpc-*, monitor, media, render-*, soft-otp) and its docs under `dvnh-common/docs/`.
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
