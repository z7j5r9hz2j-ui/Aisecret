"""저빈도 폴링 루프.

설계 원칙 두 가지.
1) 고정 간격으로 때리지 않는다. 지터를 섞어 사람 손에 가까운 간격을 유지한다.
2) 차단 신호를 만나면 우회하지 않고 멈춘다. 재시도로 뚫는 코드는 넣지 않았다.
"""

from __future__ import annotations

import random
import time as _time
from dataclasses import dataclass, field
from enum import Enum

from .errors import AuthError, BlockedError, SpecError, TransientError
from .models import Reservation, Train, WatchCriteria
from .notify import Notifier
from .sources import TrainSource


class StopReason(str, Enum):
    RESERVED = "좌석 선점 완료"
    TIME_LIMIT = "최대 실행 시간 도달"
    BLOCKED = "차단 신호 감지 - 중단"
    TOO_MANY_ERRORS = "연속 오류 한도 초과"
    FATAL = "복구 불가 오류"
    INTERRUPTED = "사용자 중단"


@dataclass(frozen=True)
class PollerConfig:
    interval: float = 45.0
    """기본 조회 간격(초). 30초 밑으로는 내리지 말 것."""

    jitter: float = 0.4
    """간격에 곱해질 흔들림 비율. 0.4면 45초 ± 18초."""

    max_duration: float = 6 * 60 * 60
    """총 실행 상한(초). 무한 실행 금지."""

    backoff_base: float = 30.0
    backoff_max: float = 600.0
    max_transient_failures: int = 5
    notify_cooldown: float = 600.0
    """같은 열차를 다시 알리기까지의 최소 간격(초)."""

    def __post_init__(self) -> None:
        if self.interval < 30:
            raise ValueError("조회 간격은 30초 이상이어야 합니다.")
        if not 0 <= self.jitter < 1:
            raise ValueError("jitter는 0 이상 1 미만이어야 합니다.")

    def next_delay(self, rng: random.Random) -> float:
        spread = self.interval * self.jitter
        return max(1.0, self.interval + rng.uniform(-spread, spread))

    def backoff_delay(self, failures: int) -> float:
        return min(self.backoff_base * (2 ** max(failures - 1, 0)), self.backoff_max)


@dataclass
class PollResult:
    reason: StopReason
    polls: int = 0
    matches: list[tuple[Train, str]] = field(default_factory=list)
    reservation: Reservation | None = None
    detail: str = ""


class Poller:
    def __init__(
        self,
        source: TrainSource,
        criteria: WatchCriteria,
        notifier: Notifier,
        config: PollerConfig | None = None,
        *,
        reserve: bool = False,
        sleep=_time.sleep,
        clock=_time.monotonic,
        rng: random.Random | None = None,
    ) -> None:
        self.source = source
        self.criteria = criteria
        self.notifier = notifier
        self.config = config or PollerConfig()
        self.reserve_enabled = reserve
        self._sleep = sleep
        self._clock = clock
        self._rng = rng or random.Random()
        self._last_notified: dict[str, float] = {}

    def run(self) -> PollResult:
        started = self._clock()
        result = PollResult(reason=StopReason.TIME_LIMIT)
        failures = 0

        while self._clock() - started < self.config.max_duration:
            try:
                trains = self.source.search(self.criteria)
            except BlockedError as exc:
                result.reason, result.detail = StopReason.BLOCKED, str(exc)
                self.notifier.send("감시 중단: 차단 신호", str(exc))
                return result
            except (AuthError, SpecError) as exc:
                result.reason, result.detail = StopReason.FATAL, str(exc)
                self.notifier.send("감시 중단: 설정 오류", str(exc))
                return result
            except TransientError as exc:
                failures += 1
                if failures > self.config.max_transient_failures:
                    result.reason, result.detail = StopReason.TOO_MANY_ERRORS, str(exc)
                    self.notifier.send("감시 중단: 연속 오류", str(exc))
                    return result
                self._sleep(self.config.backoff_delay(failures))
                continue
            except KeyboardInterrupt:
                result.reason = StopReason.INTERRUPTED
                return result

            failures = 0
            result.polls += 1

            for train in trains:
                available = self.criteria.matches(train)
                if not available:
                    continue
                seat_type = next(iter(available))
                result.matches.append((train, seat_type))
                if self._should_notify(train):
                    self.notifier.send("빈자리 발견", str(train))
                if self.reserve_enabled:
                    reservation = self._try_reserve(train, seat_type)
                    if reservation is not None:
                        result.reservation = reservation
                        result.reason = StopReason.RESERVED
                        return result

            self._sleep(self.config.next_delay(self._rng))

        return result

    def _should_notify(self, train: Train) -> bool:
        now = self._clock()
        last = self._last_notified.get(train.key)
        if last is not None and now - last < self.config.notify_cooldown:
            return False
        self._last_notified[train.key] = now
        return True

    def _try_reserve(self, train: Train, seat_type: str) -> Reservation | None:
        try:
            reservation = self.source.reserve(train, seat_type, self.criteria)
        except BlockedError:
            raise
        except Exception as exc:  # 선점 실패는 흔하다(그 사이 팔림). 감시를 계속한다.
            self.notifier.send("선점 실패", f"{train}\n사유: {exc}")
            return None
        self.notifier.send(
            "좌석 선점 완료 - 결제 필요",
            f"{train}\n좌석: {seat_type}\n예약번호: {reservation.reservation_no}\n"
            f"결제 기한: {reservation.pay_deadline}\n"
            "코레일+ 앱에서 직접 결제하세요. 기한이 지나면 자동 취소됩니다.",
        )
        return reservation
