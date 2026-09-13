#!/usr/bin/env python3
"""Xin quyền ĐỌC Google Calendar cho Hoàng — chạy tay 1 lần, 0 token.

Token cất ở FILE RIÊNG `google_calendar_token.json`; KHÔNG đụng `google_token.json`
(token Gmail đang chạy) — hai việc khác nhau thì giữ hai token khác nhau, thu hồi
hay cấp lại cái này không làm chết cái kia.

    gcal_auth.py             # xin quyền, mở local server, LUÔN in URL để copy sang máy khác
    gcal_auth.py --manual    # không mở cổng: in URL, dán lại URL redirect vào terminal
    gcal_auth.py --check     # xem token còn dùng được không + in 3 sự kiện sắp tới

Máy này có thể không có trình duyệt, nên cách nào cũng in URL ra màn hình. Với chế độ
mặc định, mở URL trên máy khác vẫn được miễn là máy đó tới được cổng local đang lắng nghe;
không tới được thì dùng --manual.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERMES = Path.home() / ".hermes"
SECRET = HERMES / "google_client_secret.json"
TOKEN = HERMES / "google_calendar_token.json"
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
MANUAL_PORT = 8765


def _save(creds) -> None:
    TOKEN.write_text(creds.to_json(), encoding="utf-8")
    TOKEN.chmod(0o600)
    print(f"OK: đã lưu token vào {TOKEN}")


def load_creds():
    """Trả về Credentials còn hạn, hoặc None nếu chưa cấp quyền bao giờ."""
    if not TOKEN.exists():
        return None
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json(), encoding="utf-8")
        TOKEN.chmod(0o600)
    return creds


def _flow():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not SECRET.exists():
        print(f"LỖI: thiếu client secret {SECRET}", file=sys.stderr)
        raise SystemExit(2)
    return InstalledAppFlow.from_client_secrets_file(str(SECRET), SCOPES)


def auth_local() -> int:
    flow = _flow()
    msg = ("\n=== MỞ URL NÀY TRÊN MÁY CÓ TRÌNH DUYỆT ===\n{url}\n"
           "=== rồi bấm đồng ý; trang sẽ tự quay về ===\n")
    creds = flow.run_local_server(port=0, open_browser=False,
                                  authorization_prompt_message=msg)
    _save(creds)
    return 0


def auth_manual() -> int:
    """Không dựa vào cổng local: người dùng dán lại URL redirect (hoặc mã code)."""
    flow = _flow()
    flow.redirect_uri = f"http://localhost:{MANUAL_PORT}/"
    url, _ = flow.authorization_url(access_type="offline", prompt="consent")
    print("\n=== MỞ URL NÀY TRÊN MÁY CÓ TRÌNH DUYỆT ===")
    print(url)
    print("\nBấm đồng ý xong trình duyệt sẽ báo 'không kết nối được' — KHÔNG SAO.")
    print(f"Copy nguyên URL trên thanh địa chỉ (dạng http://localhost:{MANUAL_PORT}/?code=...) dán vào đây.")
    raw = input("\nURL redirect (hoặc chỉ mã code): ").strip()
    if not raw:
        print("LỖI: không nhận được gì", file=sys.stderr)
        return 2
    code = raw
    if raw.startswith("http"):
        qs = parse_qs(urlparse(raw).query)
        if not qs.get("code"):
            print("LỖI: URL không có tham số ?code=", file=sys.stderr)
            return 2
        code = qs["code"][0]
    flow.fetch_token(code=code)
    _save(flow.credentials)
    return 0


def check() -> int:
    if not TOKEN.exists():
        print(f"CHƯA CẤP QUYỀN Calendar — không thấy {TOKEN}.")
        print("Chạy:  python3 scripts/gcal_auth.py        (hoặc --manual nếu không mở được cổng local)")
        return 2
    try:
        creds = load_creds()
    except Exception as exc:
        print(f"TOKEN HỎNG: {type(exc).__name__}: {exc}")
        print("Chạy lại  python3 scripts/gcal_auth.py  để cấp quyền mới.")
        return 2
    if not creds or not creds.valid:
        print("TOKEN HẾT HẠN và không làm mới được — chạy lại python3 scripts/gcal_auth.py")
        return 2
    print(f"Token OK  ({TOKEN})")
    print(f"  scope   : {', '.join(creds.scopes or SCOPES)}")
    print(f"  hết hạn : {creds.expiry} (UTC)" if creds.expiry else "  hết hạn : không rõ")
    try:
        from googleapiclient.discovery import build

        svc = build("calendar", "v3", credentials=creds, cache_discovery=False)
        now = dt.datetime.now(dt.timezone.utc).isoformat()
        evs = svc.events().list(calendarId="primary", timeMin=now, maxResults=3,
                                singleEvents=True, orderBy="startTime").execute().get("items", [])
    except Exception as exc:
        print(f"ĐỌC LỊCH LỖI: {type(exc).__name__}: {exc}")
        return 2
    if not evs:
        print("  Đọc lịch được, nhưng không có sự kiện nào sắp tới.")
        return 0
    print(f"  {len(evs)} sự kiện sắp tới:")
    for e in evs:
        st = e.get("start", {})
        print(f"    - {st.get('dateTime') or st.get('date')}  {e.get('summary', '(không tên)')}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Cấp quyền đọc Google Calendar")
    p.add_argument("--check", action="store_true", help="kiểm token + in 3 sự kiện sắp tới")
    p.add_argument("--manual", action="store_true", help="không dùng cổng local, dán code bằng tay")
    a = p.parse_args()
    if a.check:
        return check()
    if a.manual:
        return auth_manual()
    try:
        return auth_local()
    except OSError as exc:
        print(f"\nKhông mở được cổng local ({exc}) — chuyển sang chế độ dán tay.\n", file=sys.stderr)
        return auth_manual()


if __name__ == "__main__":
    sys.exit(main())
