import random
from datetime import date, time

import pytest

from korail_watch.errors import AuthError, BlockedError, TransientError
from korail_watch.models import Train, WatchCriteria
from korail_watch.notify import RecordingNotifier
from korail_watch.poller import Poller, PollerConfig, StopReason
from korail_watch.sources import FakeTrainSource

CRITERIA = WatchCriteria(
    dep_station="서울",
    arr_station="부산",
    travel_date=date(2026, 9, 20),
    time_from=time(9, 0),
    time_to=time(13, 0),
    seat_types=("일반실",),
    passengers=1,
)

TRAIN = Train(
    train_no="101",
    train_name="KTX",
    dep_station="서울",
    arr_station="부산",
    dep_time=time(10, 0),
    arr_time=time(12, 40),
    seats={"일반실": 2},
)


class FakeClock:
    """sleep한 만큼만 시간이 흐르는 시계."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def build(responses, *, config=None, reserve=False):
    clock = FakeClock()
    notifier = RecordingNotifier()
    source = FakeTrainSource(responses)
    poller = Poller(
        source,
        CRITERIA,
        notifier,
        config or PollerConfig(),
        reserve=reserve,
        sleep=clock.sleep,
        clock=clock,
        rng=random.Random(0),
    )
    return poller, source, notifier, clock


def test_notifies_when_seat_appears():
    poller, _, notifier, _ = build([[], [TRAIN]])
    result = poller.run()

    assert [t for t, _ in result.matches] == [TRAIN]
    assert notifier.messages[0][0] == "빈자리 발견"


def test_stops_immediately_on_block_and_does_not_retry():
    poller, source, notifier, _ = build([BlockedError("매크로 탐지"), [TRAIN]])
    result = poller.run()

    assert result.reason is StopReason.BLOCKED
    assert source.search_calls == 1, "차단 후 재시도하면 안 된다"
    assert notifier.messages[0][0] == "감시 중단: 차단 신호"


def test_auth_error_is_fatal():
    poller, source, _, _ = build([AuthError("자격증명 없음"), [TRAIN]])
    result = poller.run()

    assert result.reason is StopReason.FATAL
    assert source.search_calls == 1


def test_transient_errors_back_off_exponentially_then_recover():
    poller, _, _, clock = build([TransientError("500"), TransientError("500"), [TRAIN]])
    result = poller.run()

    assert result.matches, "일시 오류 후에는 회복해서 계속 조회해야 한다"
    assert clock.slept[:2] == [30.0, 60.0]


def test_gives_up_after_too_many_consecutive_errors():
    config = PollerConfig(max_transient_failures=2)
    poller, source, _, _ = build([TransientError("x")] * 5, config=config)
    result = poller.run()

    assert result.reason is StopReason.TOO_MANY_ERRORS
    assert source.search_calls == 3


def test_stops_at_max_duration():
    config = PollerConfig(interval=60, jitter=0.0, max_duration=200)
    poller, source, _, _ = build([[]] * 100, config=config)
    result = poller.run()

    assert result.reason is StopReason.TIME_LIMIT
    assert source.search_calls == 4


def test_repeat_notifications_are_suppressed_within_cooldown():
    config = PollerConfig(interval=60, jitter=0.0, max_duration=200, notify_cooldown=600)
    poller, _, notifier, _ = build([[TRAIN]] * 10, config=config)
    poller.run()

    assert len(notifier.messages) == 1


def test_same_train_notified_again_after_cooldown():
    config = PollerConfig(interval=60, jitter=0.0, max_duration=600, notify_cooldown=120)
    poller, _, notifier, _ = build([[TRAIN]] * 20, config=config)
    poller.run()

    assert len(notifier.messages) > 1


def test_reserve_mode_stops_after_securing_a_seat():
    poller, source, notifier, _ = build([[TRAIN]], reserve=True)
    result = poller.run()

    assert result.reason is StopReason.RESERVED
    assert result.reservation is not None
    assert len(source.reservations) == 1
    titles = [t for t, _ in notifier.messages]
    assert "좌석 선점 완료 - 결제 필요" in titles
    body = next(b for t, b in notifier.messages if t == "좌석 선점 완료 - 결제 필요")
    assert "직접 결제" in body


def test_reserve_failure_keeps_watching():
    class FlakyReserve(FakeTrainSource):
        def reserve(self, train, seat_type, criteria):
            raise RuntimeError("이미 매진되었습니다")

    clock = FakeClock()
    notifier = RecordingNotifier()
    source = FlakyReserve([[TRAIN], []])
    poller = Poller(
        source, CRITERIA, notifier,
        PollerConfig(interval=60, jitter=0.0, max_duration=150),
        reserve=True, sleep=clock.sleep, clock=clock, rng=random.Random(0),
    )
    result = poller.run()

    assert result.reason is StopReason.TIME_LIMIT
    assert source.search_calls > 1
    assert "선점 실패" in [t for t, _ in notifier.messages]


def test_interval_below_floor_is_rejected():
    with pytest.raises(ValueError):
        PollerConfig(interval=5)


def test_jitter_keeps_delay_around_interval():
    config = PollerConfig(interval=45, jitter=0.4)
    rng = random.Random(1)
    delays = [config.next_delay(rng) for _ in range(200)]

    assert all(27 <= d <= 63 for d in delays)
    assert len(set(delays)) > 100, "고정 간격이면 안 된다"


def test_backoff_is_capped():
    config = PollerConfig(backoff_base=30, backoff_max=600)
    assert config.backoff_delay(1) == 30
    assert config.backoff_delay(10) == 600
