"""알림 채널."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Protocol

import httpx


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
