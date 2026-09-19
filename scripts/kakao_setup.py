#!/usr/bin/env python3
"""카카오톡 "나에게 보내기" 알림을 설정한다.

    python3 scripts/kakao_setup.py --key <REST API 키>

브라우저로 동의 화면을 열고, 돌아온 인증 코드를 토큰으로 바꿔 .env 에 저장한 뒤
테스트 메시지를 보낸다. 사용자는 "동의하기" 한 번만 누르면 된다.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from korail_watch.envfile import ENV_PATH, load_dotenv, upsert_env  # noqa: E402
from korail_watch.notify import KakaoNotifier  # noqa: E402

AUTH_URL = "https://kauth.kakao.com/oauth/authorize"
TOKEN_URL = "https://kauth.kakao.com/oauth/token"
DEFAULT_PORT = 8910
REDIRECT_PATH = "/callback"

DONE_PAGE = """<!doctype html><meta charset="utf-8">
<title>korail-watch</title>
<body style="font-family:system-ui;text-align:center;padding:3rem">
<h2>{heading}</h2><p>{message}</p><p>이 창은 닫으셔도 됩니다.</p></body>"""


class SetupError(Exception):
    """사용자가 고칠 수 있는 문제."""


def redirect_uri(port: int) -> str:
    return f"http://localhost:{port}{REDIRECT_PATH}"


def authorize_url(rest_api_key: str, port: int) -> str:
    query = urlencode({
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri(port),
        "response_type": "code",
        "scope": "talk_message",
    })
    return f"{AUTH_URL}?{query}"


class _CallbackHandler(BaseHTTPRequestHandler):
    """동의 후 돌아오는 ?code= 를 받아낸다."""

    def do_GET(self) -> None:  # noqa: N802 - http.server 규약
        parsed = urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            return

        params = parse_qs(parsed.query)
        self.server.code = (params.get("code") or [""])[0]
        self.server.error = (params.get("error_description") or params.get("error") or [""])[0]

        body = DONE_PAGE.format(
            heading="인증 완료" if self.server.code else "인증 실패",
            message="터미널로 돌아가세요." if self.server.code else self.server.error,
        )
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, *args) -> None:
        pass  # 접속 로그로 화면을 더럽히지 않는다


def wait_for_code(port: int, timeout: float = 300.0) -> str:
    """로컬 서버를 띄워 인증 코드를 기다린다."""
    try:
        server = HTTPServer(("127.0.0.1", port), _CallbackHandler)
    except OSError as exc:
        raise SetupError(
            f"{port} 포트를 열지 못했습니다: {exc}\n"
            f"다른 프로그램이 쓰고 있다면 --port 로 바꾸고, 카카오 개발자센터의 "
            f"Redirect URI 도 같은 포트로 바꿔주세요."
        ) from exc

    server.code = server.error = ""
    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()
    thread.join(timeout)
    server.server_close()

    if server.error:
        raise SetupError(f"카카오가 인증을 거부했습니다: {server.error}")
    if not server.code:
        raise SetupError(
            "시간 안에 인증이 끝나지 않았습니다. 브라우저에서 '동의하기' 를 눌렀는지 확인하세요."
        )
    return server.code


def exchange_code(client: httpx.Client, rest_api_key: str, code: str, port: int) -> dict:
    response = client.post(TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": rest_api_key,
        "redirect_uri": redirect_uri(port),
        "code": code,
    })
    payload = response.json() if response.content else {}
    if response.status_code >= 400 or "access_token" not in payload:
        raise SetupError(
            f"토큰 발급 실패: {payload.get('error_description') or payload or response.text[:200]}\n"
            f"카카오 개발자센터에 Redirect URI 가 정확히 '{redirect_uri(port)}' 로 "
            "등록돼 있는지 확인하세요."
        )
    return payload


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None,
         opener=webbrowser.open, wait=wait_for_code) -> int:
    parser = argparse.ArgumentParser(description="카카오톡 나에게 보내기 알림 설정")
    parser.add_argument("--key", default="", help="REST API 키 (기본: .env 의 KAKAO_REST_API_KEY)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="인증 콜백 포트")
    parser.add_argument("--no-save", action="store_true", help=".env 에 저장하지 않는다")
    args = parser.parse_args(argv)

    load_dotenv()
    rest_api_key = args.key or os.getenv("KAKAO_REST_API_KEY", "")
    if not rest_api_key:
        print(
            "REST API 키가 없습니다.\n"
            "  1) developers.kakao.com 로그인 → 내 애플리케이션 → 애플리케이션 추가\n"
            "  2) 앱 설정 → 앱 키 → 'REST API 키' 복사\n"
            "  3) 카카오 로그인 → 활성화 ON\n"
            f"  4) 카카오 로그인 → Redirect URI 에 {redirect_uri(args.port)} 등록\n"
            "  5) 카카오 로그인 → 동의항목 → '카카오톡 메시지 전송'(talk_message) 설정\n"
            "  6) python3 scripts/kakao_setup.py --key 여기에키",
            file=sys.stderr,
        )
        return 2

    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        url = authorize_url(rest_api_key, args.port)
        print("브라우저에서 카카오 동의 화면을 엽니다. '동의하기' 를 눌러주세요.")
        print(f"창이 안 열리면 이 주소를 직접 여세요:\n  {url}\n")
        opener(url)

        code = wait(args.port)
        tokens = exchange_code(client, rest_api_key, code, args.port)
        print("토큰을 받았습니다.")

        notifier = KakaoNotifier(
            tokens["access_token"],
            tokens.get("refresh_token", ""),
            rest_api_key,
            client=client,
        )
        notifier.send(
            "korail-watch 알림 테스트",
            "이 메시지가 보이면 설정이 끝났습니다.\n"
            "빈자리를 찾거나 좌석을 선점하면 여기로 알려드립니다.",
        )
        print("테스트 메시지를 보냈습니다. 카카오톡 '나와의 채팅' 을 확인하세요.")

        if not args.no_save:
            upsert_env(ENV_PATH, {
                "KAKAO_REST_API_KEY": rest_api_key,
                "KAKAO_ACCESS_TOKEN": tokens["access_token"],
                "KAKAO_REFRESH_TOKEN": tokens.get("refresh_token", ""),
            })
            print(f"{ENV_PATH} 에 저장했습니다. 이제 GUI 를 켜면 알림이 함께 갑니다.")
            print("리프레시 토큰은 두 달마다 만료됩니다. 알림이 끊기면 이 명령을 다시 실행하세요.")
    except SetupError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    finally:
        if owns_client:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
