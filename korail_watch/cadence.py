"""조회 간격 스케줄.

취소표는 하루에 균등하게 나오지 않는다. 미결제 자동취소와 환불 수수료
구간 변경 같은 이벤트 직후에 몰린다. 그래서 종일 같은 간격으로 때리는 대신,
수확이 몰리는 시간대(window)에만 간격을 좁힌다. 총 요청 수는 줄고
적중률은 오른다 - 그리고 균일한 연타보다 탐지에 걸릴 여지도 적다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

#: 어떤 경우에도 이보다 자주 조회하지 않는다.
#: 사람이 앱에서 엄지로 새로고침하는 속도의 하한 정도.
MIN_INTERVAL = 5.0


@dataclass(frozen=True)
class Window:
    """특정 시간대에 적용할 조회 간격."""

    start: time
    end: time
    interval: float
    label: str = ""

    def __post_init__(self) -> None:
        if self.interval < MIN_INTERVAL:
            raise ValueError(
                f"조회 간격은 {MIN_INTERVAL:g}초 이상이어야 합니다: {self.interval:g}초"
            )

    def contains(self, moment: datetime | time) -> bool:
        t = moment.time() if isinstance(moment, datetime) else moment
        if self.start <= self.end:
            return self.start <= t <= self.end
        return t >= self.start or t <= self.end  # 자정을 넘는 구간

    def __str__(self) -> str:
        name = f" {self.label}" if self.label else ""
        return f"{self.start:%H:%M}~{self.end:%H:%M} {self.interval:g}초{name}"


@dataclass(frozen=True)
class Cadence:
    """기본 간격 + 시간대별 예외."""

    base_interval: float
    windows: tuple[Window, ...] = ()

    def __post_init__(self) -> None:
        if self.base_interval < MIN_INTERVAL:
            raise ValueError(
                f"기본 조회 간격은 {MIN_INTERVAL:g}초 이상이어야 합니다: {self.base_interval:g}초"
            )

    def interval_at(self, moment: datetime) -> float:
        """해당 시각에 적용할 간격. 먼저 매치되는 window가 이긴다."""
        for window in self.windows:
            if window.contains(moment):
                return window.interval
        return self.base_interval

    def active_window(self, moment: datetime) -> Window | None:
        return next((w for w in self.windows if w.contains(moment)), None)

    def describe(self) -> str:
        if not self.windows:
            return f"{self.base_interval:g}초 간격"
        return (
            f"기본 {self.base_interval:g}초 / 집중 구간: "
            + ", ".join(str(w) for w in self.windows)
        )


def parse_windows(spec: str) -> tuple[Window, ...]:
    """'0000-0020@5,1800-1900@10' 형태를 파싱."""
    from .models import WatchCriteria

    windows: list[Window] = []
    for chunk in (c.strip() for c in spec.split(",")):
        if not chunk:
            continue
        range_part, sep, interval_part = chunk.rpartition("@")
        if not sep:
            raise ValueError(
                f"집중 구간 형식이 잘못되었습니다: {chunk!r} (예: 0000-0020@5)"
            )
        try:
            interval = float(interval_part)
        except ValueError as exc:
            raise ValueError(f"간격이 숫자가 아닙니다: {interval_part!r}") from exc
        start, end = WatchCriteria.parse_time_range(range_part, allow_wrap=True)
        windows.append(Window(start=start, end=end, interval=interval))
    if not windows:
        raise ValueError("집중 구간이 비어 있습니다.")
    return tuple(windows)


#: 취소표가 몰리는 시간대의 기본값.
#:
#: - 00:00~00:25: 예약대기 배정분의 결제 기한이 당일 24시이므로, 미결제 건이
#:   자정 직후 한꺼번에 풀린다. (코레일 공지 기준)
#: - 23:40~23:59: 위 기한을 앞두고 포기·취소가 몰리는 구간.
#: - 07:00~09:00 / 18:00~20:00: 출퇴근 시간대 열차의 당일 일정 변경 취소.
#:   이건 경험적 추정이므로 본인 노선 기록을 보고 조정할 것.
DEFAULT_WINDOWS = "2340-0025@6,0700-0900@15,1800-2000@15"
