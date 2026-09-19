"""알림 채널."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

import httpx

from .envfile import ENV_PATH, upsert_env

#: 카카오 텍스트 템플릿의 본문 길이 제한.
KAKAO_TEXT_LIMIT = 200


class Notifier(Protocol):
    def send(self, title: str, body: str) -> None: ...


class ConsoleNotifier:
    """표준출력. 항상 켜둔다."""

    def __init__(self, stream=None) -> None:
        self._stream = stream or sys.stdout

    def send(self, title: str, body: str) -> None:
        stamp = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{stamp}] {title}\n{body}\n", file=self._stream, flush=True)


class TelegramNotifier:
    """텔레그램 봇 메시지."""

    def __init__(self, token: str, chat_id: str, *, client: httpx.Client | None = None) -> None:
        if not token or not chat_id:
            raise ValueError("텔레그램 토큰과 chat_id가 모두 필요합니다.")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._client = client or httpx.Client(timeout=10.0)

    def send(self, title: str, body: str) -> None:
        try:
            self._client.post(
                self._url,
                json={"chat_id": self._chat_id, "text": f"{title}\n{body}"},
            )
        except httpx.HTTPError as exc:
            # 알림 실패로 감시를 중단시키지는 않는다.
            print(f"[알림 실패] 텔레그램 전송 오류: {exc}", file=sys.stderr, flush=True)


class KakaoNotifier:
    """카카오톡 "나에게 보내기".

    액세스 토큰은 하루 못 가서 만료되므로, 401 을 만나면 리프레시 토큰으로
    갱신하고 한 번 다시 보낸다. 갱신된 토큰은 콜백으로 저장한다 - 6시간짜리
    감시 도중에 만료되면 알림이 조용히 끊기기 때문이다.
    """

    SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
    TOKEN_URL = "https://kauth.kakao.com/oauth/token"
    #: 알림을 누르면 바로 결제하러 갈 수 있게.
    LINK = "https://www.korail.com"

    def __init__(
        self,
        access_token: str,
        refresh_token: str = "",
        rest_api_key: str = "",
        *,
        client: httpx.Client | None = None,
        on_token_refresh: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        if not access_token:
            raise ValueError("카카오 액세스 토큰이 필요합니다.")
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.rest_api_key = rest_api_key
        self._client = client or httpx.Client(timeout=10.0)
        self._on_token_refresh = on_token_refresh

    def send(self, title: str, body: str) -> None:
        try:
            response = self._post(title, body)
            if response.status_code == 401 and self._refresh():
                response = self._post(title, body)
            if response.status_code >= 400:
                print(
                    f"[알림 실패] 카카오 {response.status_code}: {response.text[:200]}",
                    file=sys.stderr,
                    flush=True,
                )
        except httpx.HTTPError as exc:
            # 알림 실패로 감시를 중단시키지는 않는다.
            print(f"[알림 실패] 카카오 전송 오류: {exc}", file=sys.stderr, flush=True)

    def _post(self, title: str, body: str) -> httpx.Response:
        text = f"{title}\n{body}"
        if len(text) > KAKAO_TEXT_LIMIT:
            text = text[: KAKAO_TEXT_LIMIT - 1] + "…"
        template = {
            "object_type": "text",
            "text": text,
            "link": {"web_url": self.LINK, "mobile_web_url": self.LINK},
        }
        return self._client.post(
            self.SEND_URL,
            headers={"Authorization": f"Bearer {self.access_token}"},
            data={"template_object": json.dumps(template, ensure_ascii=False)},
        )

    def _refresh(self) -> bool:
        if not (self.refresh_token and self.rest_api_key):
            print(
                "[알림 실패] 카카오 토큰이 만료됐는데 갱신 정보가 없습니다. "
                "python3 scripts/kakao_setup.py 를 다시 실행하세요.",
                file=sys.stderr,
                flush=True,
            )
            return False

        response = self._client.post(
            self.TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": self.rest_api_key,
                "refresh_token": self.refresh_token,
            },
        )
        if response.status_code >= 400:
            print(
                "[알림 실패] 카카오 토큰 갱신 실패. "
                "python3 scripts/kakao_setup.py 로 다시 인증하세요.",
                file=sys.stderr,
                flush=True,
            )
            return False

        payload = response.json()
        self.access_token = payload.get("access_token", self.access_token)
        saved = {"KAKAO_ACCESS_TOKEN": self.access_token}
        # 리프레시 토큰은 만료 한 달 전부터만 새로 내려온다.
        if payload.get("refresh_token"):
            self.refresh_token = payload["refresh_token"]
            saved["KAKAO_REFRESH_TOKEN"] = self.refresh_token
        if self._on_token_refresh:
            self._on_token_refresh(saved)
        return True


def save_kakao_tokens(values: dict[str, str], path: Path | str = ENV_PATH) -> None:
    """갱신된 토큰을 .env 에 돌려놓는다."""
    upsert_env(path, values)


def build_notifiers(env: dict[str, str], extra: list | None = None) -> list:
    """환경변수를 보고 쓸 수 있는 알림 채널을 모은다.

    CLI 와 GUI 가 같은 규칙을 쓰도록 한 곳에 둔다.
    """
    notifiers = list(extra or [])
    access = env.get("KAKAO_ACCESS_TOKEN")
    if access:
        notifiers.append(
            KakaoNotifier(
                access,
                env.get("KAKAO_REFRESH_TOKEN", ""),
                env.get("KAKAO_REST_API_KEY", ""),
                on_token_refresh=save_kakao_tokens,
            )
        )
    token, chat_id = env.get("TELEGRAM_BOT_TOKEN"), env.get("TELEGRAM_CHAT_ID")
    if token and chat_id:
        notifiers.append(TelegramNotifier(token, chat_id))
    return notifiers


class MultiNotifier:
    def __init__(self, *notifiers: Notifier) -> None:
        self._notifiers = [n for n in notifiers if n is not None]

    def send(self, title: str, body: str) -> None:
        for n in self._notifiers:
            n.send(title, body)


class RecordingNotifier:
    """테스트용."""

    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []

    def send(self, title: str, body: str) -> None:
        self.messages.append((title, body))
