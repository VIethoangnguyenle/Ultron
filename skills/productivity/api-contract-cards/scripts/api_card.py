#!/usr/bin/env python3
"""api_card.py — sinh & kiem tra JSON request/response cho 1 API tu "the API".

Muc dich: tra loi client cau hoi "JSON request/response cua API nay la gi" bang JSON THAT,
sinh tu the API tu chua (khong bia field), va kiem tra payload client gui len.

Dung:
  python3 api_card.py --cards <dir> --out <dir>     # sinh schema + mau + validate (exit 1 neu FAIL)
  python3 api_card.py --show <card_id>              # in mau JSON de dan vao cau tra loi client
  python3 api_card.py --check-payload <card_id> <file.json>   # soi payload client, chi dich danh field sai

The API la 1 file JSON tu chua moi thu: xem assets/cards/*.json
"""
import argparse
import glob
import json
import os
import sys

PY_FOR_JSON = {"string": str, "integer": int, "number": float, "boolean": bool, "array": list, "object": dict}


# ------------------------------------------------------------------ card loading
def load_cards(cards_dir):
    cards = {}
    for f in sorted(glob.glob(os.path.join(cards_dir, "*.json"))):
        with open(f, encoding="utf-8") as fh:
            c = json.load(fh)
        cards[c["card_id"]] = c
    return cards


def field_schema(f):
    t = f["type"]
    if t == "enum":
        s = {"type": "string", "enum": f["enum"]}
    elif t == "integer":
        s = {"type": "integer"}
    elif t == "number":
        s = {"type": "number"}
    elif t == "boolean":
        s = {"type": "boolean"}
    elif t == "array":
        s = {"type": "array", "items": {"type": "string"}}
    elif t == "object":
        s = {"type": "object"}
    else:
        s = {"type": "string"}
    if f.get("note"):
        s["description"] = f["note"]
    if f.get("example") is not None:
        s["examples"] = [f["example"]]
    if f.get("nullable"):
        s["type"] = [s["type"], "null"]
    return s


def request_schema(card):
    props = {f["name"]: field_schema(f) for f in card["request_fields"]}
    required = [f["name"] for f in card["request_fields"] if f.get("required")]
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "%s request (%s)" % (card["card_id"], card["version"]),
        "type": "object",
        "properties": props,
        "required": required,
        "additionalProperties": True,
    }


def response_schema(card):
    data_fields = card.get("response_data_fields", [])
    data_props = {f["name"]: field_schema(f) for f in data_fields}
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "%s response (%s)" % (card["card_id"], card["version"]),
        "type": "object",
        "properties": {
            "success": {"type": "boolean"},
            "code": {"type": "string"},
            "des": {"type": "string"},
            "messageCode": {"type": "string"},
            "data": {"type": ["object", "null"], "properties": data_props, "additionalProperties": True},
            "warnings": {"type": "array"},
        },
        "required": ["success"],
        "additionalProperties": True,
    }


# ------------------------------------------------------------------ sample gen
def _fallback(f):
    t = f["type"]
    if t == "enum":
        return f["enum"][0]
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return True
    if t == "array":
        return []
    if t == "object":
        return {}
    return "<chuoi>"


def minimal_request(card):
    return {f["name"]: f.get("example") for f in card["request_fields"]
            if f.get("required") and f.get("example") is not None}


def full_request(card):
    out = {}
    for f in card["request_fields"]:
        ex = f.get("example")
        out[f["name"]] = _fallback(f) if ex is None else ex
    return out


def success_response(card):
    data = {f["name"]: f.get("example") for f in card.get("response_data_fields", [])}
    return {"success": True, "code": card.get("success_code", "00"), "des": "",
            "messageCode": "", "data": data, "warnings": []}


def error_response(card, err):
    """Tra ve (http_status, body). Kienh App tra 200 ca khi loi; kienh Web tra 400 cho loi dau vao."""
    field_errors = err.get("field_errors")
    body = {
        "success": False,
        "code": err["code"],
        "des": err["message"] + (" (<requestId>)" if card.get("channel") == "APP" else ""),
        "data": field_errors,
        "warnings": [],
    }
    if card.get("channel") == "APP":
        status = 200
    else:
        status = 400 if err.get("input_error") else 200
    return status, body


def gen_all(card, out_root):
    cid = card["card_id"]
    for d in ("cards", "schemas", "samples"):
        os.makedirs(os.path.join(out_root, d), exist_ok=True)
    rs = request_schema(card)
    rsp = response_schema(card)
    with open(os.path.join(out_root, "cards", cid + ".json"), "w", encoding="utf-8") as fh:
        json.dump(card, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(out_root, "schemas", cid + ".request.schema.json"), "w", encoding="utf-8") as fh:
        json.dump(rs, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(out_root, "schemas", cid + ".response.schema.json"), "w", encoding="utf-8") as fh:
        json.dump(rsp, fh, ensure_ascii=False, indent=2)

    art = {
        "request.minimal.json": minimal_request(card),
        "request.full.json": full_request(card),
        "response.success.json": success_response(card),
    }
    for err in card.get("errors", [])[:3]:
        _, body = error_response(card, err)
        art["response.error.%s.json" % err["code"]] = body
    for name, payload in art.items():
        with open(os.path.join(out_root, "samples", cid + "." + name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
    return rs, rsp, art


# ------------------------------------------------------------------ validate
def validate_payload(card, payload):
    """Soi payload client gui len -> danh sach loi theo tung field (de tra loi 'sai o dau')."""
    problems = []
    spec = {f["name"]: f for f in card["request_fields"]}
    for f in card["request_fields"]:
        if f.get("required") and (f["name"] not in payload or payload[f["name"]] in (None, "")):
            problems.append("THIEU truong bat buoc: %s (%s)" % (f["name"], f.get("note", "")))
    for k, v in payload.items():
        if k not in spec:
            problems.append("KHONG CO trong hop dong: %s (goi y xoa hoac lien he doi ky thuat)" % k)
            continue
        f = spec[k]
        t = f["type"]
        if t == "enum":
            if v not in f["enum"]:
                problems.append("SAI gia tri: %s = %r, chi nhan %s" % (k, v, "|".join(f["enum"])))
        else:
            want = PY_FOR_JSON.get(t, str)
            if not isinstance(v, want) or isinstance(v, bool) and want is int:
                problems.append("SAI kieu: %s dang %s, hop dong yeu cau %s" % (k, type(v).__name__, t))
    return problems


# ------------------------------------------------------------------ commands
def cmd_gen(args):
    import jsonschema
    cards = load_cards(args.cards)
    if not cards:
        print("Khong doc duoc the nao trong %s" % args.cards)
        return 1
    report, failures = [], 0
    for cid, card in cards.items():
        rs, rsp, art = gen_all(card, args.out)
        for name in ("request.minimal.json", "request.full.json"):
            try:
                jsonschema.validate(art[name], rs)
                report.append((cid, name, "PASS", ""))
            except jsonschema.ValidationError as e:
                failures += 1
                report.append((cid, name, "FAIL", e.message[:90]))
        for name in [k for k in art if k.startswith("response.")]:
            try:
                jsonschema.validate(art[name], rsp)
                report.append((cid, name, "PASS", ""))
            except jsonschema.ValidationError as e:
                failures += 1
                report.append((cid, name, "FAIL", e.message[:90]))
        missing = [f["name"] for f in card["request_fields"]
                   if f.get("required") and f["name"] not in rs["required"]]
        if missing:
            failures += 1
        report.append((cid, "required-consistency", "FAIL" if missing else "PASS", ",".join(missing)))
    for cid, name, kq, msg in report:
        print("%-32s %-30s %-5s %s" % (cid, name, kq, msg))
    print("TONG: %d kiem tra, FAIL = %d" % (len(report), failures))
    return 1 if failures else 0


def cmd_show(args):
    cards = load_cards(args.cards)
    card = cards[args.show]
    if args.endpoint_only:
        print("%s %s" % (card["method"], card["path"]))
        return 0
    print("# %s" % card["title"])
    print("%s %s   (version %s)" % (card["method"], card["path"], card["version"]))
    print("\n## Request toi thieu\n" + json.dumps(minimal_request(card), ensure_ascii=False, indent=2))
    print("\n## Request day du\n" + json.dumps(full_request(card), ensure_ascii=False, indent=2))
    print("\n## Response thanh cong\n" + json.dumps(success_response(card), ensure_ascii=False, indent=2))
    for err in card.get("errors", [])[:args.errors]:
        st, body = error_response(card, err)
        print("\n## Response loi %s (HTTP %d)\n" % (err["code"], st) + json.dumps(body, ensure_ascii=False, indent=2))
    return 0


def cmd_check_payload(args):
    cards = load_cards(args.cards)
    card = cards[args.check_payload]
    with open(args.payload_file, encoding="utf-8") as fh:
        payload = json.load(fh)
    problems = validate_payload(card, payload)
    if not problems:
        print("OK: payload dung hop dong (khong thay van de ve field)")
        return 0
    print("Payload co %d van de:" % len(problems))
    for p in problems:
        print("  - " + p)
    return 1


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_cards = os.path.join(os.path.dirname(here), "assets", "cards")
    ap = argparse.ArgumentParser(description="Sinh & kiem tra JSON request/response tu the API")
    ap.add_argument("--cards", default=default_cards)
    ap.add_argument("--out", default=os.path.join(os.getcwd(), "api-card-out"))
    ap.add_argument("--show", metavar="CARD_ID")
    ap.add_argument("--errors", type=int, default=3)
    ap.add_argument("--endpoint-only", action="store_true")
    ap.add_argument("--check-payload", metavar="CARD_ID")
    ap.add_argument("payload_file", nargs="?")
    args = ap.parse_args()
    if args.show:
        return cmd_show(args)
    if args.check_payload:
        if not args.payload_file:
            print("Can duong dan file JSON payload")
            return 2
        return cmd_check_payload(args)
    return cmd_gen(args)


if __name__ == "__main__":
    sys.exit(main())
