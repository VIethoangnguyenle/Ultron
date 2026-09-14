#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bizcard.py — tra cứu "thẻ nghiệp vụ" (business knowledge cards) kèm cổng kiểm hạn.

Đọc lớp thẻ ở <root>/registry.json + <root>/cards/*.json, trả lời câu hỏi nghiệp vụ
bằng thẻ đã xác minh, và LUÔN kèm cổng kiểm hạn 2 tầng để thẻ cũ không trả lời sai.

Chỉ dùng thư viện chuẩn của Python 3. Không gọi mạng, trừ khi dùng `--fetch`
(chạy `git fetch`).
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
import unicodedata
from datetime import datetime
from pathlib import Path

# Vị trí mặc định cuối cùng, chỉ dùng khi không có --root, không có $BIZCARD_ROOT
# và không dò ngược lên từ thư mục hiện tại được.
DEFAULT_ROOT = "/home/zane/Desktop/work/vietbank/vietbank-sme/docs/knowledge"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_CONFIG = 2
EXIT_MISS = 3

FIX_RE = re.compile(r"(fix|bugfix|hotfix)", re.IGNORECASE)
GIT_TIMEOUT = 30
FETCH_TIMEOUT = 60

ST_OK = "OK"
ST_DRIFT = "LECH"
ST_MISSING = "THIEU"
ST_NOFP = "KHONG_CO_VAN_TAY"

LABEL = {
    ST_OK: "khớp",
    ST_DRIFT: "LỆCH",
    ST_MISSING: "KHÔNG THẤY",
    ST_NOFP: "chưa có dấu vân tay",
}

WIDTH = 96
SOFT_LIMIT = 10          # số commit tầng mềm in ra tối đa cho mỗi thẻ


class ConfigError(Exception):
    """Lỗi cấu hình / đọc file — dẫn tới exit code 2."""


# --------------------------------------------------------------------------- #
# Nạp registry và thẻ
# --------------------------------------------------------------------------- #

def find_root(cli_root):
    if cli_root:
        return Path(cli_root).expanduser().resolve()
    env_root = os.environ.get("BIZCARD_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    here = Path.cwd().resolve()
    for base in [here] + list(here.parents):
        for rel in ("docs/knowledge/registry.json", "knowledge/registry.json", "registry.json"):
            if (base / rel).is_file():
                return (base / rel).parent
    return Path(DEFAULT_ROOT)


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except FileNotFoundError:
        raise ConfigError("Không tìm thấy file: %s" % path)
    except json.JSONDecodeError as exc:
        raise ConfigError("File JSON hỏng (%s): %s" % (path, exc))
    except OSError as exc:
        raise ConfigError("Không đọc được %s: %s" % (path, exc))


def load_registry(root):
    registry = read_json(root / "registry.json")
    if not isinstance(registry.get("cards"), list):
        raise ConfigError("registry.json thiếu danh sách `cards`.")
    if not isinstance(registry.get("repos"), dict) or not registry["repos"]:
        raise ConfigError("registry.json thiếu `repos`.")
    if not registry.get("workspace_root"):
        raise ConfigError("registry.json thiếu `workspace_root`.")
    return registry


def load_cards(root, registry, only_id=None):
    cards = []
    for entry in registry["cards"]:
        cid = entry.get("id")
        if only_id and cid != only_id:
            continue
        rel = entry.get("file") or ("cards/%s.json" % cid)
        card = read_json(root / rel)
        card["_path"] = root / rel
        card["_registry_title"] = entry.get("title", "")
        card.setdefault("id", cid)
        cards.append(card)
    if only_id and not cards:
        raise ConfigError("Không có thẻ nào tên `%s` trong registry." % only_id)
    return cards


def repo_of(registry, card):
    name = card.get("fingerprint_repo")
    repos = registry["repos"]
    if not name:
        if len(repos) != 1:
            raise ConfigError(
                "Thẻ `%s` không khai `fingerprint_repo` mà registry có nhiều repo." % card.get("id"))
        name = next(iter(repos))
    if name not in repos:
        raise ConfigError(
            "Thẻ `%s` trỏ tới repo `%s` không có trong registry." % (card.get("id"), name))
    return name, repos[name]


# --------------------------------------------------------------------------- #
# Git
# --------------------------------------------------------------------------- #

def run_git(repo_path, args, timeout=GIT_TIMEOUT):
    """Trả về (returncode, stdout, stderr); không để lộ exception của subprocess."""
    cmd = ["git", "-C", str(repo_path)] + args
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except FileNotFoundError:
        raise ConfigError("Không tìm thấy lệnh `git` trong PATH.")
    except subprocess.TimeoutExpired:
        return 124, "", "quá hạn %ss: %s" % (timeout, " ".join(cmd))
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


_ref_cache = {}


def ref_exists(repo_path, ref):
    key = (str(repo_path), ref)
    if key not in _ref_cache:
        rc, _, _ = run_git(repo_path, ["rev-parse", "--verify", "--quiet", "%s^{commit}" % ref])
        _ref_cache[key] = rc == 0
    return _ref_cache[key]


def last_commit_of(repo_path, ref, rel_file):
    rc, stdout, err = run_git(repo_path, ["log", "-1", "--format=%H", ref, "--", rel_file])
    if rc != 0:
        return None, err or "git log thất bại"
    return (stdout or None), None


def fetch_repo(name, repo):
    branch = repo.get("branch")
    args = ["fetch", "origin"] + ([branch] if branch else [])
    rc, _, err = run_git(repo["path"], args, timeout=FETCH_TIMEOUT)
    if rc != 0:
        detail = (err.splitlines() or ["không rõ"])[-1]
        return "Cảnh báo: fetch repo `%s` thất bại (%s) — vẫn kiểm trên ref đang có." % (name, detail)
    return None


# --------------------------------------------------------------------------- #
# Cổng kiểm hạn
# --------------------------------------------------------------------------- #

def sha256_prefix_of(path, length):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()[:length]


def resolve_loose(workspace_root, file_ref):
    path = Path(file_ref).expanduser()
    if path.is_absolute():
        return path
    return Path(workspace_root) / file_ref


def check_evidence(registry, card, ev):
    """Tầng cứng: kiểm một mục bằng chứng."""
    repo_name, repo = repo_of(registry, card)
    ref = ev.get("ref") or card.get("gate_ref") or repo.get("gate_ref")
    res = {
        "file": ev.get("file") or "(thiếu trường file)",
        "repo": repo_name,
        "repo_path": repo["path"],
        "ref": ref,
        "proves": ev.get("proves", ""),
        "note": ev.get("note", ""),
        "kind": None,
        "status": ST_NOFP,
        "expected": None,
        "actual": None,
        "detail": "",
        "local_checkout_commit": ev.get("local_checkout_commit"),
    }
    if not ev.get("file"):
        res["detail"] = "Mục bằng chứng không có trường `file`."
        return res

    if ev.get("last_commit"):
        res["kind"] = "git"
        res["expected"] = ev["last_commit"]
        if not ref:
            res["detail"] = "Không xác định được ref để kiểm."
            return res
        if not ref_exists(repo["path"], ref):
            res["status"] = ST_MISSING
            res["detail"] = "Ref `%s` không tồn tại trong repo %s." % (ref, repo["path"])
            return res
        actual, err = last_commit_of(repo["path"], ref, ev["file"])
        if err:
            res["status"] = ST_MISSING
            res["detail"] = err
            return res
        res["actual"] = actual
        if actual is None:
            res["status"] = ST_MISSING
            res["detail"] = "File không có commit nào trên `%s` (bị xoá hoặc đổi tên?)." % ref
        elif actual != ev["last_commit"]:
            res["status"] = ST_DRIFT
            res["detail"] = "commit cuối chạm file đã đổi"
        else:
            res["status"] = ST_OK
        return res

    if ev.get("sha256_prefix"):
        res["kind"] = "sha256"
        expected = str(ev["sha256_prefix"]).lower()
        res["expected"] = expected
        path = resolve_loose(registry["workspace_root"], ev["file"])
        res["abs_path"] = str(path)
        if not path.is_file():
            res["status"] = ST_MISSING
            res["detail"] = "Không thấy file trên đĩa: %s" % path
            return res
        try:
            actual = sha256_prefix_of(path, len(expected))
        except OSError as exc:
            res["status"] = ST_MISSING
            res["detail"] = "Không đọc được file: %s" % exc
            return res
        res["actual"] = actual
        res["status"] = ST_OK if actual == expected else ST_DRIFT
        if res["status"] == ST_DRIFT:
            res["detail"] = "nội dung file đã đổi"
        return res

    res["detail"] = "Mục này không có `last_commit` lẫn `sha256_prefix` — không kiểm được."
    return res


def soft_watch(registry, card):
    """Tầng mềm: liệt kê commit chạm vùng theo dõi kể từ verified_at."""
    paths = card.get("watch_paths") or []
    out_data = {"paths": paths, "commits": [], "error": None, "repo_path": None, "ref": None}
    if not paths:
        return out_data
    _, repo = repo_of(registry, card)
    ref = card.get("gate_ref") or repo.get("gate_ref")
    out_data["repo_path"] = repo["path"]
    out_data["ref"] = ref
    since = card.get("verified_at")
    if not ref or not since:
        out_data["error"] = "Thiếu `gate_ref` hoặc `verified_at` — không chạy được tầng mềm."
        return out_data
    if not ref_exists(repo["path"], ref):
        out_data["error"] = "Ref `%s` không tồn tại." % ref
        return out_data
    args = ["log", "--format=%h|%ad|%an|%s", "--date=short",
            "--since=%s" % since, ref, "--"] + list(paths)
    rc, stdout, err = run_git(repo["path"], args)
    if rc != 0:
        out_data["error"] = err or "git log thất bại"
        return out_data
    for line in stdout.splitlines():
        parts = line.split("|", 3)
        if len(parts) < 4:
            continue
        sha, date, author, subject = parts
        out_data["commits"].append({
            "sha": sha, "date": date, "author": author, "subject": subject,
            "suspect": bool(FIX_RE.search(subject)),
        })
    return out_data


def check_card(registry, card):
    results = [check_evidence(registry, card, ev) for ev in (card.get("evidence") or [])]
    hard = [r for r in results if r["status"] in (ST_DRIFT, ST_MISSING)]
    soft = soft_watch(registry, card)
    return {
        "id": card.get("id"),
        "title": card.get("title") or card.get("_registry_title", ""),
        "confidence": card.get("confidence", "?"),
        "verified_at": card.get("verified_at", "?"),
        "gate_ref": card.get("gate_ref", ""),
        "evidence": results,
        "hard_drift": bool(hard),
        "soft": soft,
        "suspect_count": sum(1 for c in soft["commits"] if c["suspect"]),
    }


# --------------------------------------------------------------------------- #
# Khớp từ khoá — ranh giới từ, giữ nguyên dấu tiếng Việt
# --------------------------------------------------------------------------- #

def norm(text):
    return unicodedata.normalize("NFC", text or "").lower()


def alias_hits(question, aliases):
    question_n = norm(question)
    hits = []
    for alias in aliases or []:
        alias_n = norm(alias).strip()
        if not alias_n:
            continue
        pattern = r"(?<!\w)" + re.escape(alias_n) + r"(?!\w)"
        if re.search(pattern, question_n):
            hits.append(alias)
    return hits


def match_cards(question, cards):
    scored = []
    for card in cards:
        hits = alias_hits(question, card.get("aliases"))
        if hits:
            scored.append((len(hits), sum(len(h) for h in hits), card.get("id") or "", card, hits))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [(card, hits) for _, _, _, card, hits in scored]


# --------------------------------------------------------------------------- #
# In ra màn hình
# --------------------------------------------------------------------------- #

def emit(line=""):
    print(line)


def wrap(text, indent="    "):
    return textwrap.fill(str(text), width=WIDTH,
                         initial_indent=indent, subsequent_indent=indent + "  ")


def gate_badge(result):
    if result["hard_drift"]:
        bad = sum(1 for e in result["evidence"] if e["status"] in (ST_DRIFT, ST_MISSING))
        return "LỆCH %d/%d" % (bad, len(result["evidence"]))
    if result["suspect_count"]:
        return "theo dõi (%d commit nghi ngờ)" % result["suspect_count"]
    if result["soft"]["commits"]:
        return "theo dõi (%d commit mới)" % len(result["soft"]["commits"])
    return "còn hạn"


def print_gate(result, prefix="  "):
    emit("%sCỔNG KIỂM HẠN — tầng cứng (bằng chứng):" % prefix)
    for ev in result["evidence"]:
        mark = "[OK]" if ev["status"] == ST_OK else "[%s]" % LABEL[ev["status"]]
        emit("%s  %-6s %s" % (prefix, mark, ev["file"]))
        if ev["status"] == ST_OK:
            continue
        if ev.get("detail"):
            emit("%s         %s" % (prefix, ev["detail"]))
        if ev["kind"] == "git":
            emit("%s         thẻ ghi : %s" % (prefix, ev["expected"]))
            emit("%s         thực tế : %s" % (prefix, ev["actual"] or "(không có)"))
        elif ev["kind"] == "sha256":
            emit("%s         thẻ ghi : sha256 %s" % (prefix, ev["expected"]))
            emit("%s         thực tế : sha256 %s" % (prefix, ev["actual"] or "(không đọc được)"))

    soft = result["soft"]
    emit("%sCỔNG KIỂM HẠN — tầng mềm (vùng theo dõi, từ %s):" % (prefix, result["verified_at"]))
    if soft["error"]:
        emit("%s  Không chạy được: %s" % (prefix, soft["error"]))
        return
    if not soft["paths"]:
        emit("%s  Thẻ không khai `watch_paths`." % prefix)
        return
    if not soft["commits"]:
        emit("%s  Không có commit nào chạm vùng theo dõi." % prefix)
        return

    commits = soft["commits"]
    suspects = [c for c in commits if c["suspect"]]
    emit("%s  %d commit chạm vùng theo dõi, trong đó %d nghi ngờ cao (fix/bugfix/hotfix)."
         % (prefix, len(commits), len(suspects)))
    # Ưu tiên in commit nghi ngờ, giữ nguyên thứ tự mới->cũ, cắt bớt cho vừa màn chat.
    shown = suspects[:SOFT_LIMIT]
    if len(shown) < SOFT_LIMIT:
        shown += [c for c in commits if not c["suspect"]][: SOFT_LIMIT - len(shown)]
    order = {id(c): i for i, c in enumerate(commits)}
    for c in sorted(shown, key=lambda c: order[id(c)]):
        tag = "   <== NGHI NGỜ CAO" if c["suspect"] else ""
        emit("%s  %s %s %s — %s%s" % (prefix, c["sha"], c["date"], c["author"], c["subject"], tag))
    if len(commits) > len(shown):
        emit("%s  ... còn %d commit nữa. Xem đủ:" % (prefix, len(commits) - len(shown)))
        emit("%s    git -C %s log --oneline --since=%s %s -- %s"
             % (prefix, soft["repo_path"], result["verified_at"], soft["ref"],
                " ".join('"%s"' % p for p in soft["paths"])))


def print_drift_warning(result, prefix="  "):
    emit("")
    emit("%s!!! KHÔNG dùng thẻ này làm kết luận — bằng chứng đã lệch, phải verify lại." % prefix)
    for ev in result["evidence"]:
        if ev["status"] not in (ST_DRIFT, ST_MISSING):
            continue
        emit("%s    File đã đổi: %s" % (prefix, ev["file"]))
        if ev["kind"] == "git" and ev["expected"]:
            emit("%s    Rà phần lệch bằng:" % prefix)
            emit('%s      git -C %s diff %s..%s -- "%s"'
                 % (prefix, ev["repo_path"], ev["expected"], ev["ref"], ev["file"]))
        elif ev["kind"] == "sha256":
            emit("%s    File ngoài git — đọc lại trực tiếp: %s"
                 % (prefix, ev.get("abs_path", ev["file"])))
    emit("%s    Verify tay xong thì đóng dấu lại: bizcard.py stamp %s" % (prefix, result["id"]))


# --------------------------------------------------------------------------- #
# Lệnh
# --------------------------------------------------------------------------- #

def cmd_list(args, root, registry, cards):
    headers = ["id", "độ tin", "xác minh", "số file BC"]
    if args.check:
        headers.append("cổng kiểm hạn")
    rows = []
    worst = EXIT_OK
    for card in cards:
        row = [card.get("id", "?"), card.get("confidence", "?"),
               (card.get("verified_at") or "?")[:10],
               str(len(card.get("evidence") or []))]
        if args.check:
            result = check_card(registry, card)
            row.append(gate_badge(result))
            if result["hard_drift"]:
                worst = EXIT_DRIFT
        rows.append(row)

    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    emit(" | ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    emit("-+-".join("-" * w for w in widths))
    for row in rows:
        emit(" | ".join(row[i].ljust(widths[i]) for i in range(len(headers))))
    emit("")
    emit("Tổng: %d thẻ. Thư mục thẻ: %s" % (len(cards), root))
    if not args.check:
        emit("Thêm --check để kèm trạng thái cổng kiểm hạn.")
    return worst


def card_payload(card, result, hits):
    return {
        "id": card.get("id"),
        "title": card.get("title"),
        "confidence": card.get("confidence"),
        "verified_at": card.get("verified_at"),
        "matched_aliases": hits,
        "conclusion": card.get("conclusion") or {},
        "traps": card.get("traps") or [],
        "gaps": card.get("gaps") or [],
        "gate": {
            "hard_drift": result["hard_drift"],
            "evidence": result["evidence"],
            "watch": result["soft"],
        },
    }


def print_card(card, hits, result):
    emit("")
    emit("THẺ: %s — %s" % (card.get("id"), card.get("title", "")))
    emit("  độ tin: %s | xác minh: %s | khớp alias: %s"
         % (card.get("confidence", "?"), card.get("verified_at", "?"), ", ".join(hits)))

    concl = card.get("conclusion") or {}
    if concl.get("summary"):
        emit("")
        emit("  KẾT LUẬN")
        emit(wrap(concl["summary"]))
    if concl.get("steps"):
        emit("")
        emit("  CÁC BƯỚC")
        for step in concl["steps"]:
            emit(wrap(step))
    if concl.get("api_paths"):
        emit("")
        emit("  ĐƯỜNG DẪN API")
        for api in concl["api_paths"]:
            if not isinstance(api, dict):
                emit("    %s" % api)
                continue
            emit("    %s" % api.get("path", ""))
            tail = api.get("meaning", "")
            if api.get("verified"):
                tail += "  [xác minh: %s]" % api["verified"]
            if tail.strip():
                emit(wrap(tail, indent="        "))
    if concl.get("error_codes"):
        emit("")
        emit("  MÃ LỖI")
        emit(wrap(concl["error_codes"]))
    if concl.get("where_to_look_next"):
        emit("")
        emit("  ĐỌC TIẾP")
        for item in concl["where_to_look_next"]:
            emit(wrap("- %s" % item))
    if concl.get("full_doc"):
        emit("")
        emit("  TÀI LIỆU ĐẦY ĐỦ")
        emit(wrap(concl["full_doc"]))

    if card.get("traps"):
        emit("")
        emit("  BẪY")
        for trap in card["traps"]:
            emit(wrap("- %s" % trap))
    if card.get("gaps"):
        emit("")
        emit("  KHOẢNG TRỐNG (thẻ chưa trả lời được)")
        for gap in card["gaps"]:
            emit(wrap("- %s" % gap))

    emit("")
    print_gate(result, prefix="  ")
    if result["hard_drift"]:
        print_drift_warning(result, prefix="  ")
    elif card.get("confidence") == "medium":
        emit("")
        emit("  Lưu ý: độ tin `medium` — phải nói rõ với người hỏi là thẻ này chưa chắc chắn tuyệt đối.")


def cmd_find(args, root, registry, cards):
    matches = match_cards(args.question, cards)
    if not matches:
        if args.json:
            print(json.dumps({"query": args.question, "miss": True, "matched": []},
                             ensure_ascii=False, indent=2))
        else:
            emit("MISS — không thẻ nào khớp câu hỏi: %s" % args.question)
            emit("")
            emit("Phải trace theo đường thường: CodeGraph -> Serena -> chốt bằng source.")
            emit("Trace xong thì viết thẻ mới vào %s/cards/ và thêm một dòng vào registry.json." % root)
            emit("Nếu thẻ ĐÃ CÓ mà từ khoá chưa phủ, bổ sung alias lấy từ chính câu hỏi này.")
        return EXIT_MISS

    matches = matches[: max(1, args.limit)]
    results = [(card, hits, check_card(registry, card)) for card, hits in matches]

    if args.json:
        print(json.dumps({
            "query": args.question,
            "miss": False,
            "matched": [card_payload(c, r, h) for c, h, r in results],
        }, ensure_ascii=False, indent=2, default=str))
    else:
        for idx, (card, hits, result) in enumerate(results):
            if idx:
                emit("")
                emit("=" * WIDTH)
            print_card(card, hits, result)

    return EXIT_DRIFT if any(r["hard_drift"] for _, _, r in results) else EXIT_OK


def cmd_check(args, root, registry, cards):
    warnings = []
    if args.fetch:
        seen = set()
        for card in cards:
            name, repo = repo_of(registry, card)
            if name in seen:
                continue
            seen.add(name)
            warn = fetch_repo(name, repo)
            if warn:
                warnings.append(warn)

    results = [check_card(registry, card) for card in cards]
    drift = any(r["hard_drift"] for r in results)
    suspect = any(r["suspect_count"] for r in results)

    if args.json:
        print(json.dumps({
            "root": str(root),
            "checked_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "warnings": warnings,
            "hard_drift": drift,
            "cards": results,
        }, ensure_ascii=False, indent=2, default=str))
        return EXIT_DRIFT if drift else EXIT_OK

    if args.quiet and not drift and not suspect and not warnings:
        return EXIT_OK

    for warn in warnings:
        emit(warn)
    if warnings:
        emit("")

    printed = 0
    for result in results:
        if args.quiet and not result["hard_drift"] and not result["suspect_count"]:
            continue
        if printed:
            emit("")
        emit("THẺ: %s  [%s]" % (result["id"], gate_badge(result)))
        print_gate(result, prefix="  ")
        if result["hard_drift"]:
            print_drift_warning(result, prefix="  ")
        printed += 1

    emit("")
    if drift:
        emit("KẾT QUẢ: CÓ LỆCH CỨNG — những thẻ lệch ở trên KHÔNG dùng làm kết luận được.")
    elif suspect:
        emit("KẾT QUẢ: không lệch cứng, nhưng có commit nghi ngờ cao chạm vùng theo dõi — nên rà lại.")
    else:
        emit("KẾT QUẢ: mọi thẻ còn hạn (%d thẻ)." % len(results))
    return EXIT_DRIFT if drift else EXIT_OK


def cmd_verify(args, root, registry, cards):
    card = next((c for c in cards if c.get("id") == args.card_id), None)
    if card is None:
        emit("Không có thẻ `%s`. Xem danh sách bằng: bizcard.py list" % args.card_id)
        return EXIT_CONFIG

    repo_name, repo = repo_of(registry, card)
    emit("THẺ: %s — %s" % (card.get("id"), card.get("title", "")))
    emit("  repo vân tay : %s (%s)" % (repo_name, repo["path"]))
    emit("  gate_ref     : %s" % (card.get("gate_ref") or "(không khai)"))
    emit("  verified_at  : %s" % card.get("verified_at", "?"))
    emit("  độ tin       : %s" % card.get("confidence", "?"))
    emit("")
    emit("BẰNG CHỨNG (%d mục) — chạy các lệnh dưới để tự kiểm chứng:"
         % len(card.get("evidence") or []))

    for i, ev in enumerate(card.get("evidence") or [], 1):
        emit("")
        emit("[%d] %s" % (i, ev.get("file") or "(thiếu trường file)"))
        if ev.get("proves"):
            emit(wrap("chứng minh: %s" % ev["proves"]))
        if ev.get("note"):
            emit(wrap("ghi chú   : %s" % ev["note"]))
        ref = ev.get("ref") or card.get("gate_ref") or repo.get("gate_ref")
        if ev.get("last_commit"):
            emit("    ref         : %s" % ref)
            emit("    last_commit : %s" % ev["last_commit"])
            if ev.get("last_commit_date"):
                emit("    ngày commit : %s" % ev["last_commit_date"])
            if ev.get("local_checkout_commit"):
                emit("    bản checkout local (tham khảo, stamp không đụng tới): %s"
                     % ev["local_checkout_commit"])
            emit("    kiểm commit cuối chạm file trên ref:")
            emit('      git -C %s log -1 --format=%%H %s -- "%s"' % (repo["path"], ref, ev["file"]))
            emit("    xem chính commit thẻ đang neo:")
            emit('      git -C %s show --stat %s -- "%s"' % (repo["path"], ev["last_commit"], ev["file"]))
            emit("    xem nội dung file tại commit đó:")
            emit('      git -C %s show %s:"%s"' % (repo["path"], ev["last_commit"], ev["file"]))
        elif ev.get("sha256_prefix"):
            path = resolve_loose(registry["workspace_root"], ev["file"])
            emit("    ngoài git — vân tay sha256: %s" % ev["sha256_prefix"])
            emit("    kiểm lại:")
            emit('      sha256sum "%s" | cut -c1-%d' % (path, len(ev["sha256_prefix"])))
        else:
            emit("    KHÔNG có `last_commit` lẫn `sha256_prefix` — mục này không kiểm được.")

    emit("")
    emit("Kiểm tự động toàn thẻ : bizcard.py check --card %s" % card.get("id"))
    emit("Verify tay xong        : bizcard.py stamp %s" % card.get("id"))
    return EXIT_OK


def cmd_stamp(args, root, registry, cards):
    card = next((c for c in cards if c.get("id") == args.card_id), None)
    if card is None:
        emit("Không có thẻ `%s`. Xem danh sách bằng: bizcard.py list" % args.card_id)
        return EXIT_CONFIG

    repo_name, repo = repo_of(registry, card)
    if args.fetch:
        warn = fetch_repo(repo_name, repo)
        if warn:
            emit(warn)
            emit("")

    # Tính trước toàn bộ giá trị mới; còn bất kỳ mục nào không tính được thì KHÔNG ghi gì.
    planned, errors = [], []
    for ev in card.get("evidence") or []:
        fileref = ev.get("file")
        if not fileref:
            errors.append("Một mục bằng chứng không có trường `file`.")
            continue
        if ev.get("last_commit"):
            ref = ev.get("ref") or card.get("gate_ref") or repo.get("gate_ref")
            if not ref or not ref_exists(repo["path"], ref):
                errors.append("Ref `%s` không tồn tại (file %s)." % (ref, fileref))
                continue
            actual, err = last_commit_of(repo["path"], ref, fileref)
            if err:
                errors.append("git log lỗi với %s: %s" % (fileref, err))
            elif actual is None:
                errors.append("File `%s` không có commit nào trên `%s`." % (fileref, ref))
            else:
                planned.append((ev, "last_commit", ev["last_commit"], actual, fileref))
        elif ev.get("sha256_prefix"):
            path = resolve_loose(registry["workspace_root"], fileref)
            if not path.is_file():
                errors.append("Không thấy file trên đĩa: %s" % path)
                continue
            try:
                actual = sha256_prefix_of(path, len(ev["sha256_prefix"]))
            except OSError as exc:
                errors.append("Không đọc được %s: %s" % (path, exc))
                continue
            planned.append((ev, "sha256_prefix", str(ev["sha256_prefix"]).lower(), actual, fileref))
        else:
            errors.append("Mục `%s` không có dấu vân tay để cập nhật." % fileref)

    if errors:
        emit("KHÔNG đóng dấu — còn lỗi phải xử lý trước (thẻ giữ nguyên, không ghi gì):")
        for err in errors:
            emit("  - %s" % err)
        return EXIT_CONFIG

    old_verified = card.get("verified_at")
    new_verified = datetime.now().astimezone().isoformat(timespec="seconds")

    emit("ĐÓNG DẤU THẺ: %s" % card.get("id"))
    emit("  repo: %s (%s)" % (repo_name, repo["path"]))
    emit("")
    changed = 0
    for ev, field, old, new, fileref in planned:
        if old == new:
            emit("  [giữ nguyên] %s" % fileref)
        else:
            changed += 1
            emit("  [CẬP NHẬT]   %s" % fileref)
            emit("      %s: %s" % (field, old))
            emit("      %s  %s  <== mới" % (" " * len(field), new))
        ev[field] = new
    emit("")
    emit("  verified_at: %s" % (old_verified or "(chưa có)"))
    emit("               %s  <== mới" % new_verified)
    card["verified_at"] = new_verified

    payload = {k: v for k, v in card.items() if not k.startswith("_")}
    path = card["_path"]
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except OSError as exc:
        raise ConfigError("Không ghi được thẻ %s: %s" % (path, exc))

    emit("")
    emit("Đã ghi: %s" % path)
    emit("%d dấu vân tay đổi. Nội dung conclusion / traps / gaps giữ nguyên." % changed)
    return EXIT_OK


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

EPILOG = """\
Ví dụ:
  bizcard.py list --check
  bizcard.py find "luồng chi lương hàng loạt gồm bước nào"
  bizcard.py check --fetch --quiet          # dùng cho cron: im lặng khi mọi thẻ sạch
  bizcard.py verify payroll-batch
  bizcard.py stamp payroll-batch --fetch

Mã thoát:
  0  không có lệch cứng
  1  có lệch cứng — thẻ không dùng làm kết luận được
  2  lỗi cấu hình / đọc file
  3  find không khớp thẻ nào

Thư mục thẻ lấy theo thứ tự: --root > $BIZCARD_ROOT > dò ngược lên từ thư mục hiện
tại (tìm docs/knowledge/registry.json) > mặc định dựng sẵn trong script.
Đường dẫn workspace và repo luôn đọc từ registry.json, không hardcode.
"""

CHECK_DESC = """\
Cổng kiểm hạn 2 tầng cho mọi thẻ.
  Tầng cứng: mỗi file bằng chứng phải khớp commit cuối chạm nó trên gate_ref
             (git log -1 trên ref đó); file ngoài git thì so bằng sha256.
  Tầng mềm : liệt kê commit chạm watch_paths kể từ verified_at, đánh dấu commit có
             fix / bugfix / hotfix là nghi ngờ cao.
"""


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bizcard.py",
        description="Tra cứu thẻ nghiệp vụ (business knowledge cards) kèm cổng kiểm hạn 2 tầng.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    parser.add_argument("--root", help="Thư mục chứa registry.json (ghi đè $BIZCARD_ROOT).")
    sub = parser.add_subparsers(dest="command", metavar="<lệnh>")

    p_list = sub.add_parser(
        "list", help="Liệt kê mọi thẻ.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Liệt kê mọi thẻ: id, độ tin, ngày xác minh, số file bằng chứng.")
    p_list.add_argument("--check", action="store_true",
                        help="Kèm cột trạng thái cổng kiểm hạn cho từng thẻ.")
    p_list.set_defaults(func=cmd_list)

    p_find = sub.add_parser(
        "find", help="Tìm thẻ theo câu hỏi.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("Khớp aliases của thẻ với câu hỏi theo RANH GIỚI TỪ — giữ nguyên dấu\n"
                     "tiếng Việt, không dùng substring thô. Sắp theo số alias khớp.\n"
                     "In kết luận + bẫy + khoảng trống + cổng kiểm hạn của chính thẻ đó."))
    p_find.add_argument("question", help="Câu hỏi nghiệp vụ, đặt trong dấu nháy.")
    p_find.add_argument("--limit", type=int, default=2, help="Số thẻ in ra tối đa (mặc định 2).")
    p_find.add_argument("--json", action="store_true", help="Xuất JSON thay vì văn bản.")
    p_find.set_defaults(func=cmd_find)

    p_check = sub.add_parser(
        "check", help="Chạy cổng kiểm hạn cho mọi thẻ.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=CHECK_DESC)
    p_check.add_argument("--fetch", action="store_true",
                         help="Chạy git fetch origin <branch> (tối đa 60s) trước khi kiểm. "
                              "Fetch lỗi thì vẫn kiểm trên ref đang có và in cảnh báo.")
    p_check.add_argument("--json", action="store_true", help="Xuất JSON thay vì văn bản.")
    p_check.add_argument("--quiet", action="store_true",
                         help="Không in gì khi mọi thẻ sạch (không lệch cứng, không commit "
                              "nghi ngờ cao). Dùng cho cron.")
    p_check.add_argument("--card", dest="card", metavar="ID", help="Chỉ kiểm một thẻ theo id.")
    p_check.set_defaults(func=cmd_check)

    p_verify = sub.add_parser(
        "verify", help="In bằng chứng + lệnh git để tự kiểm chứng.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("In danh sách file bằng chứng, commit đang được neo, và lệnh git show /\n"
                     "git log -1 cụ thể để người đọc tự kiểm chứng. Dùng khi cần độ chính xác cao."))
    p_verify.add_argument("card_id", help="id của thẻ (xem `bizcard.py list`).")
    p_verify.set_defaults(func=cmd_verify)

    p_stamp = sub.add_parser(
        "stamp", help="Đóng dấu lại thẻ sau khi đã verify tay.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=("Cập nhật last_commit (theo gate_ref), sha256_prefix và verified_at trong\n"
                     "file thẻ. TUYỆT ĐỐI không đụng tới conclusion / traps / gaps.\n"
                     "Chỉ chạy sau khi đã verify tay."))
    p_stamp.add_argument("card_id", help="id của thẻ cần đóng dấu lại.")
    p_stamp.add_argument("--fetch", action="store_true", help="Fetch trước khi lấy commit mới.")
    p_stamp.set_defaults(func=cmd_stamp)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return EXIT_CONFIG
    try:
        root = find_root(args.root)
        registry = load_registry(root)
        only = args.card if args.command == "check" else None
        cards = load_cards(root, registry, only_id=only)
        return args.func(args, root, registry, cards)
    except ConfigError as exc:
        print("LỖI CẤU HÌNH: %s" % exc, file=sys.stderr)
        return EXIT_CONFIG
    except BrokenPipeError:
        return EXIT_OK
    except KeyboardInterrupt:
        return EXIT_CONFIG


if __name__ == "__main__":
    sys.exit(main())
