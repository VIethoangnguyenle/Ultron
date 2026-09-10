---
name: vietbank-sme
description: "Use when working on the VietBank SME (vbsme) project."
version: 1.0.0
author: Ultron
license: MIT
platforms: [linux]
metadata:
  hermes:
    tags: [vietbank, vbsme, vnpay, fintech, oracle, database]
---

# VietBank SME (vbsme) project

Backend monorepo for VietBank SME omnichannel banking (Java/Gradle, Spring Boot, inside VNPay/dvnh infra). Hoang is the backend engineer here.

## Source layout (this machine)

- Main repo wrapper: `/home/zane/Desktop/work/vietbank/vietbank-sme/` — its `.git` is a bare `hooks/` only, so git fails at this level. cd into the nested repo before running git.
- Backend SME: `/home/zane/Desktop/work/vietbank/vietbank-sme/vietbank-sme-omni/` — git `git.vnpay.vn/dvnh/vietbank/app-backend-sme/vietbank-sme-omni.git`. Services are Gradle subprojects in `settings.gradle`.
- Backend Omni (older): `/home/zane/Desktop/work/vietbank/vietbank-omni/` — git `git.vnpay.vn/dvnh/vietbank/app-backend-omni/vietbank-omni.git`.
- Shared lib: `/home/zane/Desktop/work/dvnh-common/` — git `git.vnpay.vn/dvnh/dvnh-common-lib/java/dvnh-common.git`.
- Also present: `viet-bank-ekyc-sme`, `vietbank-sme-clone`, `documents/`.

## Databases (db-access MCP)

Call `mcp__db_access__list_databases` first. All `VBSME*`, Oracle + Mongo:
- `VBSMEONL`, `VBSMEOFF` — read+write.
- `VBSMERLE`, `VBSMESOTP`, `VBSMEFACE`, `VBSMEEKYC`, `VBEKYCSTORAGE` — read (Oracle).
- `VBSMELOGS` — Mongo (read).

Oracle rules (these waste real time when forgotten):
- Every TABLE reference MUST carry a schema prefix (`VBSMEONL.AD_MESSAGE`, not `AD_MESSAGE`) — bare table names are rejected with "missing a schema prefix". But SYS dictionary views (`all_tables`/`user_tables`) are NOT owned by the business schema: prefixing them (`VBSMEONL.all_tables`, `VBSMEONL.user_tables`) throws ORA-00942, not a clean result. To discover tables/columns, use the `sql_list_tables` / `sql_get_columns` MCP tools instead of hand-writing dictionary-view queries.
- Each `db_name` is a SEPARATE connection with its OWN user, NOT a schema switch. To read a table in `VBSMEOFF` you pass `db_name=VBSMEOFF` — never `VBSMEONL` with a `VBSMEOFF.` prefix in the SQL. Tables are not shared across DBs: `AD_MESSAGE` (holds the VPG error catalog) exists in `VBSMEONL` only; `VBSMEOFF.AD_MESSAGE` throws ORA-00942. Run `sql_list_tables` before assuming a table exists in a given DB.

## Error codes

- Message catalog lives in `AD_MESSAGE` (columns `CODE, DESCRIPTION, VI_CONTENT, EN_CONTENT, IS_ACTIVE`) in `VBSMEONL`.
- VNPay gateway error codes are prefixed `VPG`. Query: `SELECT CODE, DESCRIPTION, VI_CONTENT, EN_CONTENT FROM VBSMEONL.AD_MESSAGE WHERE CODE LIKE 'VPG%' ORDER BY CODE`.
- Code shape in source: `PREFIX_GATEWAY_ERROR="VPG"` + action prefix + responseCode. Prefixes: billing `01`, topup `02` (`Constants.java` → `BILLING_PREFIX_ERROR`, `TOPUP_PREFIX_ERROR`). `VnpayPaymentCheckerUtil.formatErrorCode` builds `VPG + action.getPrefixErrorCode() + responseCode`.
- `VNPAY_NOT_REVERT_ERROR_CODES = ["08","90"]` — codes that must NOT trigger a revert (transaction → PENDING, not FAILED).
- AD_MESSAGE text has data-entry typos (e.g. "nhà cung cấ" missing the "p") — preserve verbatim, don't silently correct.

## Caching (ETag)

List endpoints (banks, branches, cities/districts/wards, billing templates, promotions, home screen, banners, payment groups, savings products/groups, services, favorite icons, backgrounds) use an app-level versioned cache, NOT HTTP `If-None-Match`. Each list type has an `ETagType` (enum 0-18), keyed by `(type, customerId, channel)`, persisted to `OMNI_ETAG` (cached 7 days). Client sends its stored etag; server returns `data=null` when unchanged (client reuses local cache), else new data + `newEtag`. Any create/update/delete must call `generateEtag` to rotate the tag so stale clients refetch — a handler that forgets this leaves clients stuck on old data. Core code: `common/base/.../etag/` + `common/data/.../ETagType` + `BaseGetDataByETagHandler`. Full flow doc: `docs/flows/etag-flow.md`.

## Source-understanding tooling

- `understand-anything` MCP knowledge graph is already indexed for `vietbank-sme` (8339 nodes, coverage 69%) and `dvnh-common` (2776 nodes). Prefer `list_projects`, `query_nodes`, `trace_call_chain`, `find_impact`, `get_domain_overview` over raw grep — the graph models call chains, layers, domains, and DB tables.
- Other indexes on disk (for Claude Code; readable via terminal if needed): `.codegraph/codegraph.db` (~360MB), `.serena/`, `.ua/knowledge-graph.json`.

## Pitfalls

- `.mcp.json` in the project holds a plaintext Confluence personal token (`CONFLUENCE_PERSONAL_TOKEN`). Never echo its value; recommend moving it to an env var before the file hits internal git.
