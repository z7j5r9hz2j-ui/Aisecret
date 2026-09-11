"""열차 조회 소스 인터페이스와 테스트용 가짜 구현."""

from __future__ import annotations

from typing import Protocol

from .models import Reservation, Train, WatchCriteria


class TrainSource(Protocol):
    """폴러가 의존하는 최소 인터페이스."""

    def search(self, criteria: WatchCriteria) -> list[Train]:
        """조건에 해당하는 열차 목록을 반환한다."""
        ...

    def reserve(
        self, train: Train, seat_type: str, criteria: WatchCriteria
    ) -> Reservation:
        """좌석을 선점한다. 결제는 하지 않는다."""
        ...


class FakeTrainSource:
    """미리 준비한 응답을 순서대로 돌려주는 소스.

    테스트와, 실제 스펙을 채우기 전 알림 경로를 확인하는 용도.
    """

    def __init__(self, responses: list[list[Train] | Exception]) -> None:
        self._responses = list(responses)
        self.search_calls = 0
        self.reservations: list[Reservation] = []

    def search(self, criteria: WatchCriteria) -> list[Train]:
        self.search_calls += 1
        if not self._responses:
            return []
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def reserve(
        self, train: Train, seat_type: str, criteria: WatchCriteria
    ) -> Reservation:
        res = Reservation(
            reservation_no=f"FAKE-{len(self.reservations) + 1:04d}",
            train=train,
            seat_type=seat_type,
            pay_deadline="선점 후 20분 이내",
        )
        self.reservations.append(res)
        return res
