"""GUI 입력값 → 실행 설정 변환.

위젯과 분리해 둔 이유는 검증 규칙을 화면 없이 테스트하기 위해서다.
gui.py 는 여기서 만든 RunSpec 을 받아 스레드에 넘기는 일만 한다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping

from .cadence import DEFAULT_WINDOWS, parse_windows
from .models import WatchCriteria
from .poller import PollerConfig

#: GUI가 보여줄 기본값.
DEFAULTS: dict[str, str] = {
    "dep": "서울",
    "arr": "부산",
    "date": "",
    "time": "0000-2359",
    "seats": "일반실",
    "passengers": "1",
    "trains": "",
    "interval": "45",
    "windows": DEFAULT_WINDOWS,
    "max_hours": "6",
    "max_requests": "1200",
    "spec_path": "endpoints.json",
}

SEAT_CHOICES = ("일반실", "특실", "일반실+특실")


class FormError(ValueError):
    """어느 입력란이 잘못됐는지 함께 전달한다."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


@dataclass(frozen=True)
class RunSpec:
    criteria: WatchCriteria
    config: PollerConfig
    reserve: bool = False
    spec_path: str = "endpoints.json"
    demo: bool = False


def _text(values: Mapping[str, object], key: str) -> str:
    return str(values.get(key, DEFAULTS.get(key, ""))).strip()


def _flag(values: Mapping[str, object], key: str) -> bool:
    raw = values.get(key, False)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on", "y"}


def _positive_number(values: Mapping[str, object], key: str, label: str) -> float:
    raw = _text(values, key)
    try:
        number = float(raw)
    except ValueError:
        raise FormError(key, f"{label}은 숫자여야 합니다: {raw!r}") from None
    if number <= 0:
        raise FormError(key, f"{label}은 0보다 커야 합니다: {raw}")
    return number


def parse_travel_date(raw: str, *, today: date | None = None) -> date:
    """'2026-09-20', '20260920', '0920' 을 허용한다."""
    today = today or date.today()
    raw = raw.strip()
    if not raw:
        raise FormError("date", "출발일을 입력하세요. (예: 2026-09-20)")
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m-%d", "%m%d"):
        try:
            parsed = datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=today.year)
            if parsed < today:  # '0105' 를 내년으로 해석
                parsed = parsed.replace(year=today.year + 1)
        return parsed
    raise FormError("date", f"출발일 형식이 잘못되었습니다: {raw!r} (예: 2026-09-20)")


def parse_seats(raw: str) -> tuple[str, ...]:
    seats = tuple(s.strip() for s in raw.replace("+", ",").split(",") if s.strip())
    if not seats:
        raise FormError("seats", "좌석 종류를 하나 이상 고르세요.")
    return seats


def build_run_spec(
    values: Mapping[str, object], *, today: date | None = None
) -> RunSpec:
    """폼 값으로 RunSpec을 만든다. 잘못된 칸은 FormError로 알린다."""
    dep, arr = _text(values, "dep"), _text(values, "arr")
    if not dep:
        raise FormError("dep", "출발역을 입력하세요.")
    if not arr:
        raise FormError("arr", "도착역을 입력하세요.")
    if dep == arr:
        raise FormError("arr", "출발역과 도착역이 같습니다.")

    travel_date = parse_travel_date(_text(values, "date"), today=today)
    if travel_date < (today or date.today()):
        raise FormError("date", f"지난 날짜입니다: {travel_date:%Y-%m-%d}")

    try:
        time_from, time_to = WatchCriteria.parse_time_range(_text(values, "time"))
    except ValueError as exc:
        raise FormError("time", str(exc)) from None

    passengers = _positive_number(values, "passengers", "인원")
    if passengers != int(passengers):
        raise FormError("passengers", "인원은 정수여야 합니다.")

    criteria = WatchCriteria(
        dep_station=dep,
        arr_station=arr,
        travel_date=travel_date,
        time_from=time_from,
        time_to=time_to,
        seat_types=parse_seats(_text(values, "seats")),
        passengers=int(passengers),
        train_names=tuple(t.strip() for t in _text(values, "trains").split(",") if t.strip()),
    )

    windows = ()
    if _flag(values, "use_windows"):
        try:
            windows = parse_windows(_text(values, "windows") or DEFAULT_WINDOWS)
        except ValueError as exc:
            raise FormError("windows", str(exc)) from None

    max_requests = _positive_number(values, "max_requests", "요청 상한")
    try:
        config = PollerConfig(
            interval=_positive_number(values, "interval", "기본 간격"),
            windows=windows,
            max_duration=_positive_number(values, "max_hours", "최대 실행 시간") * 3600,
            max_requests=int(max_requests),
        )
    except ValueError as exc:
        raise FormError("interval", str(exc)) from None

    return RunSpec(
        criteria=criteria,
        config=config,
        reserve=_flag(values, "reserve"),
        spec_path=_text(values, "spec_path") or "endpoints.json",
        demo=_flag(values, "demo"),
    )
