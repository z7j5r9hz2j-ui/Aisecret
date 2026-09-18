#!/usr/bin/env python3
"""텔레그램 알림 설정을 확인하고 .env 에 저장한다.

    python3 scripts/telegram_setup.py

봇 토큰이 맞는지 확인하고, chat_id 를 자동으로 찾아서, 테스트 메시지를 보낸다.
폰이 울리면 설정 끝이다.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import httpx

API = "https://api.telegram.org"
ENV_PATH = Path(".env")


class SetupError(Exception):
    """사용자가 고칠 수 있는 문제. 무엇을 해야 하는지 함께 알려준다."""


def load_dotenv(path: Path = ENV_PATH) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def call(client: httpx.Client, token: str, method: str, **params):
    try:
        resp = client.get(f"{API}/bot{token}/{method}", params=params or None)
    except httpx.HTTPError as exc:
        raise SetupError(
            f"텔레그램에 연결하지 못했습니다: {exc}\n"
            "인터넷 연결이나 방화벽을 확인하세요."
        ) from exc

    if resp.status_code == 401:
        raise SetupError(
            "봇 토큰이 잘못되었습니다.\n"
            "@BotFather 에게 /mybots → 봇 선택 → API Token 으로 다시 확인하세요."
        )
    try:
        payload = resp.json()
    except ValueError:
        raise SetupError(f"텔레그램 응답을 읽지 못했습니다: {resp.text[:200]}") from None
    if not payload.get("ok"):
        raise SetupError(f"텔레그램 오류: {payload.get('description', payload)}")
    return payload["result"]


def verify_token(client: httpx.Client, token: str) -> str:
    me = call(client, token, "getMe")
    return f"@{me.get('username', '?')} ({me.get('first_name', '')})"


def find_chats(client: httpx.Client, token: str) -> list[tuple[str, str]]:
    """봇에게 말을 건 대화 목록. (chat_id, 표시이름)"""
    updates = call(client, token, "getUpdates")
    seen: dict[str, str] = {}
    for update in updates:
        message = (
            update.get("message")
            or update.get("edited_message")
            or update.get("channel_post")
            or {}
        )
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            continue
        label = chat.get("title") or " ".join(
            part for part in (chat.get("first_name"), chat.get("last_name")) if part
        ) or chat.get("username") or "이름 없음"
        # 같은 대화가 여러 번 나오면 먼저 본 이름을 쓴다(보통 더 온전하다).
        seen.setdefault(str(chat_id), label)
    return sorted(seen.items())


def send_test(client: httpx.Client, token: str, chat_id: str) -> None:
    call(
        client,
        token,
        "sendMessage",
        chat_id=chat_id,
        text=(
            "korail-watch 알림 테스트입니다.\n"
            "이 메시지가 보이면 설정이 끝났습니다.\n\n"
            "빈자리를 찾거나 좌석을 선점하면 여기로 알려드립니다."
        ),
    )


def upsert_env(path: Path, values: dict[str, str]) -> None:
    """.env 의 키를 갱신하거나 없으면 추가한다. 다른 줄은 건드리지 않는다."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def resolve_chat_id(client: httpx.Client, token: str, given: str, stream=None) -> str:
    # 기본값으로 sys.stdout 을 박으면 정의 시점의 stdout 에 묶인다. 호출할 때 찾는다.
    stream = stream or sys.stdout
    if given:
        return given

    chats = find_chats(client, token)
    if not chats:
        raise SetupError(
            "봇과 나눈 대화가 없습니다.\n"
            "폰에서 텔레그램을 열고 방금 만든 봇을 검색해 대화를 시작한 뒤\n"
            "아무 메시지나(예: 안녕) 보내고 이 명령을 다시 실행하세요.\n"
            "봇은 먼저 말을 걸 수 없어서, 사용자가 먼저 보내야 합니다."
        )
    if len(chats) > 1:
        print("여러 대화가 있습니다. --chat-id 로 골라주세요:", file=stream)
        for chat_id, label in chats:
            print(f"  {chat_id}  {label}", file=stream)
        raise SetupError("chat_id 를 지정해 다시 실행하세요.")

    chat_id, label = chats[0]
    print(f"chat_id 를 찾았습니다: {chat_id} ({label})", file=stream)
    return chat_id


def main(argv: list[str] | None = None, *, client: httpx.Client | None = None) -> int:
    parser = argparse.ArgumentParser(description="텔레그램 알림 설정 확인")
    parser.add_argument("--token", default="", help="봇 토큰 (기본: .env 의 TELEGRAM_BOT_TOKEN)")
    parser.add_argument("--chat-id", default="", help="보낼 대화 id (기본: 자동 탐색)")
    parser.add_argument("--no-save", action="store_true", help=".env 에 저장하지 않는다")
    args = parser.parse_args(argv)

    load_dotenv()
    token = args.token or os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print(
            "봇 토큰이 없습니다.\n"
            "  1) 텔레그램에서 @BotFather 검색\n"
            "  2) /newbot 보내고 이름과 사용자명(끝이 bot) 입력\n"
            "  3) 받은 토큰으로 다시 실행:\n"
            "     python3 scripts/telegram_setup.py --token 여기에토큰",
            file=sys.stderr,
        )
        return 2

    owns_client = client is None
    client = client or httpx.Client(timeout=15.0)
    try:
        print(f"봇 확인: {verify_token(client, token)}")
        chat_id = resolve_chat_id(client, token, args.chat_id or os.getenv("TELEGRAM_CHAT_ID", ""))
        send_test(client, token, chat_id)
        print("테스트 메시지를 보냈습니다. 폰을 확인하세요.")

        if not args.no_save:
            upsert_env(ENV_PATH, {"TELEGRAM_BOT_TOKEN": token, "TELEGRAM_CHAT_ID": chat_id})
            print(f"{ENV_PATH} 에 저장했습니다. 이제 GUI 를 켜면 알림이 함께 갑니다.")
    except SetupError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    finally:
        if owns_client:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
