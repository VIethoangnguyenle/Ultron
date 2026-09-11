#!/usr/bin/env python3
"""Ra soat bai hoc dai han (agentmemory lessons): bai rac, bai trung nhau, bai de loi thoi.

0 token. CHI SOI VA BAO — khong tu xoa bai hoc (xoa la quyet dinh cua Ultron/Hoang).

Chay tay:      python3 ~/.hermes/scripts/lesson_review.py
Chay dinh ky:  action `lesson-review` trong ~/.hermes/schedules.yaml (Chu nhat 09:00)
Phat hien    -> ghi 1 file escalation (~/.hermes/escalations/) de cron forward ve DM Hoang
Report       -> ~/.hermes/reports/lesson_review_<YYYY-MM-DD>.md
exit 1 neu co phat hien can nguoi xu ly, 0 neu sach.
"""
import datetime as dt
import json
import os
import pathlib
import re
import sys

HOME = pathlib.Path(os.path.expanduser("~"))
LESSONS = HOME / ".local/share/agentmemory/state_store.db/mem%3Alessons.bin"
REPORTS = HOME / ".hermes/reports"
ESCAL = HOME / ".hermes/escalations"
CONFIG = HOME / ".hermes/config.yaml"
WORK = HOME / "Desktop/work"

JUNK = re.compile(r"(?i)\bprobe\b|move-test|test lesson|dummy|placeholder lesson")
# Bai co moc THAY DOI DUOC (version/nhanh/duong dan/cong/nguong) -> de loi thoi theo thoi gian.
DECAY = re.compile(
    r"\d+\.\d+\.\d+|origin/[\w./-]+|/home/[\w./-]+|~/[\w./-]+|https?://|localhost:\d+|:\d{4}\b|"
    r"build\.gradle|\.java\b|\.json\b|prometheus_version"
)
PROBE_APPROVAL = re.compile(r"(?i)command_allowlist|auto-approve|approvals\.mode|c[ơo] ch[ếe] approval|approval ch[ặa]n")
PROBE_MCPTOKEN = re.compile(r"\.mcp\.json")
HAS_TOKEN = re.compile(r"ATATT[A-Za-z0-9]")
PATHY = re.compile(r"(?:/home/[\w./-]+|~/[\w./-]+)")


def load_lessons():
    raw = LESSONS.read_text(encoding="utf-8", errors="replace")
    dec = json.JSONDecoder()
    objs, i = [], 0
    while i < len(raw):
        while i < len(raw) and raw[i] in " \n\r\t":
            i += 1
        if i >= len(raw):
            break
        try:
            o, j = dec.raw_decode(raw, i)
        except Exception:
            break
        objs.append(o)
        i = j
    out = []
    for o in objs:
        if isinstance(o, list):
            out += [x for x in o if isinstance(x, dict) and "content" in x]
        elif isinstance(o, dict) and "content" in o:
            out.append(o)
        elif isinstance(o, dict):
            for v in o.values():
                if isinstance(v, list):
                    out += [x for x in v if isinstance(x, dict) and "content" in x]
                elif isinstance(v, dict) and "content" in v:
                    out.append(v)
    return [l for l in out if not l.get("deleted")]


def age_days(iso):
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")).replace(tzinfo=None)
        return (dt.datetime.utcnow() - d).days
    except Exception:
        return -1


def local_hm(iso):
    try:
        d = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00")) + dt.timedelta(hours=7)
        return d.strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "?"


def words(text):
    return {w.lower() for w in re.findall(r"[\wÀ-ỹ]+", text or "") if len(w) > 4}


def approvals_off():
    try:
        for ln in CONFIG.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*mode:\s*'?off'?\s*$", ln):
                return True
    except Exception:
        return None
    return False


def mcptoken_removed():
    files = list(WORK.glob("*/*/.mcp.json")) + list(WORK.glob("*/.mcp.json"))
    if not files:
        return None
    live = any(HAS_TOKEN.search(f.read_text(encoding="utf-8", errors="replace")) for f in files)
    return not live


def missing_paths(text):
    gone = []
    for p in set(PATHY.findall(text or "")):
        real = pathlib.Path(p.replace("~", str(HOME)))
        if not real.exists():
            gone.append(p)
    return gone


def main():
    lessons = load_lessons()
    today = dt.date.today().isoformat()
    junk, dups, decay, contradicted = [], [], [], []

    for l in lessons:
        text = (l.get("content") or "")
        if JUNK.search(text) or "probe" in (l.get("tags") or []):
            junk.append(l)

    # Trung nhau: Jaccard tren tu >4 ky tu
    for i, a in enumerate(lessons):
        wa = words(a.get("content"))
        if not wa:
            continue
        for b in lessons[i + 1:]:
            wb = words(b.get("content"))
            if not wb:
                continue
            jac = len(wa & wb) / max(1, len(wa | wb))
            if jac >= 0.6:
                dups.append((jac, a, b))

    appr_off = approvals_off()
    tok_gone = mcptoken_removed()
    for l in lessons:
        text = l.get("content") or ""
        if l in junk:
            continue
        # Tien de da doi: kiem chung bang the gioi thuc, khong doan
        if PROBE_APPROVAL.search(text) and appr_off:
            contradicted.append((l, "bai noi ve co che approval/allowlist chan lenh, nhung config hien tai approvals.mode = 'off' (khong con cong approval)"))
            continue
        if PROBE_MCPTOKEN.search(text) and re.search(r"(?i)token", text) and tok_gone:
            contradicted.append((l, "bai canh bao token plaintext trong .mcp.json — da kiem lai: khong con gia tri token song trong file"))
            continue
        gone = missing_paths(text)
        if gone:
            contradicted.append((l, "duong dan trong bai khong con ton tai: " + ", ".join(gone[:3])))
            continue
        if DECAY.search(text) and age_days(l.get("createdAt")) >= 14:
            decay.append(l)

    lines = [f"# Ra soat bai hoc — {today}", "", f"Tong so bai: {len(lessons)}", ""]

    def dump(title, items, render):
        lines.append(f"## {title} ({len(items)})")
        if not items:
            lines.append("_khong co_")
        for it in items:
            lines.append(render(it))
        lines.append("")

    dump("Bai rac / thu nghiem", junk,
         lambda l: f"- `{l.get('id')}` [{local_hm(l.get('createdAt'))}] {(l.get('content') or '')[:120]}")
    dump("Nghi trung nhau (nen gop)", dups,
         lambda t: f"- {t[0]:.2f} `{t[1].get('id')}` vs `{t[2].get('id')}`: {(t[1].get('content') or '')[:70]} || {(t[2].get('content') or '')[:70]}")
    dump("Tien de DA DOI — bai khong con dung", contradicted,
         lambda t: f"- `{t[0].get('id')}` [{local_hm(t[0].get('createdAt'))}] {t[1]}\n  > {(t[0].get('content') or '')[:200]}")
    dump("De loi thoi (co version/nhanh/duong dan, >= 14 ngay)", decay,
         lambda l: f"- `{l.get('id')}` [{local_hm(l.get('createdAt'))}, {age_days(l.get('createdAt'))} ngay] {(l.get('content') or '')[:120]}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"lesson_review_{today}.md"
    out.write_text("\n".join(lines), encoding="utf-8")

    need = bool(junk or contradicted)
    summary = (f"lesson-review: {len(lessons)} bai | rac={len(junk)} trung={len(dups)} "
               f"tien-de-doi={len(contradicted)} de-loi-thoi={len(decay)} -> {out}")
    print(summary)
    if need:
        ESCAL.mkdir(parents=True, exist_ok=True)
        payload = {
            "from": "Ultron (ra soat bai hoc dinh ky)",
            "space": "noi bo — bo nho dai han",
            "question": "Ra soat bai hoc: co bai rac hoac bai khong con dung, anh xem co xoa khong",
            "reason": "; ".join(
                [f"RAC: {(l.get('content') or '')[:60]} ({l.get('id')})" for l in junk]
                + [f"KHONG CON DUNG: {(t[0].get('content') or '')[:60]} ({t[0].get('id')}) — {t[1][:80]}" for t in contradicted]
            )[:900] + f" | report: {out}",
        }
        (ESCAL / f"lesson-review-{int(dt.datetime.now().timestamp())}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if need else 0


if __name__ == "__main__":
    sys.exit(main())
