"""도메인 모델: 감시 조건과 조회 결과."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, time


@dataclass(frozen=True)
class Train:
    """조회 결과 열차 한 건."""

    train_no: str
    train_name: str
    dep_station: str
    arr_station: str
    dep_time: time
    arr_time: time
    seats: dict[str, int] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.train_no}@{self.dep_time:%H%M}"

    def available(self, seat_types: tuple[str, ...]) -> dict[str, int]:
        return {t: n for t in seat_types if (n := self.seats.get(t, 0)) > 0}

    def __str__(self) -> str:
        seats = ", ".join(f"{t} {n}석" for t, n in self.seats.items() if n > 0) or "매진"
        return (
            f"{self.train_name} {self.train_no} "
            f"{self.dep_station}({self.dep_time:%H:%M}) → "
            f"{self.arr_station}({self.arr_time:%H:%M}) [{seats}]"
        )


@dataclass(frozen=True)
class WatchCriteria:
    """어떤 열차를 감시할지."""

    dep_station: str
    arr_station: str
    travel_date: date
    time_from: time = time(0, 0)
    time_to: time = time(23, 59)
    seat_types: tuple[str, ...] = ("일반실",)
    passengers: int = 1
    train_names: tuple[str, ...] = ()

    def matches(self, train: Train) -> dict[str, int]:
        """조건에 맞으면 {좌석종류: 잔여석}, 아니면 빈 dict."""
        if not self.time_from <= train.dep_time <= self.time_to:
            return {}
        if self.train_names and train.train_name not in self.train_names:
            return {}
        return {
            seat: n
            for seat, n in train.available(self.seat_types).items()
            if n >= self.passengers
        }

    @classmethod
    def parse_time_range(cls, spec: str) -> tuple[time, time]:
        """'0900-1330' 또는 '09:00-13:30' 형태를 파싱."""
        m = re.fullmatch(r"(\d{1,2}):?(\d{2})\s*-\s*(\d{1,2}):?(\d{2})", spec.strip())
        if not m:
            raise ValueError(f"시간대 형식이 잘못되었습니다: {spec!r} (예: 0900-1330)")
        h1, m1, h2, m2 = (int(g) for g in m.groups())
        start, end = time(h1, m1), time(h2, m2)
        if start > end:
            raise ValueError(f"시작 시각이 종료 시각보다 늦습니다: {spec!r}")
        return start, end


@dataclass(frozen=True)
class Reservation:
    """좌석 선점 결과. 결제는 포함하지 않는다."""

    reservation_no: str
    train: Train
    seat_type: str
    pay_deadline: str
    raw: dict = field(default_factory=dict)
