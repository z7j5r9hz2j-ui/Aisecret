"""스펙 파일로 구동되는 코레일+ HTTP 클라이언트.

이 파일에는 실제 엔드포인트 URL이 들어 있지 않다. `코레일+`는 신규 통합 앱이라
공개된 API 래퍼가 없고, 검증하지 못한 URL을 코드에 박아두면 조용히 404를 맞으며
디버깅만 어려워진다. 대신 직접 캡처한 요청/응답 형태를 endpoints.json에 적으면
그대로 동작하도록 했다. 캡처 방법은 README의 "1단계: API 파악" 참고.
"""

from __future__ import annotations

import json
from datetime import time
from pathlib import Path
from typing import Any

import httpx

from .errors import AuthError, BlockedError, SpecError, TransientError
from .models import Reservation, Train, WatchCriteria

#: 스펙에 명시하지 않았을 때 차단으로 간주할 응답 본문 키워드.
DEFAULT_BLOCK_INDICATORS = ("매크로", "비정상", "차단", "자동화", "abnormal")


def dig(obj: Any, path: str) -> Any:
    """'data.trains.0.seat' 같은 점 경로로 중첩 값을 꺼낸다."""
    if not path:
        return obj
    cur = obj
    for part in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def render(node: Any, ctx: dict[str, Any]) -> Any:
    """스펙 안의 {placeholder}를 컨텍스트 값으로 치환한다.

    문자열 전체가 하나의 placeholder면 값의 타입을 보존한다
    ("{passengers}" -> 2, "인원 {passengers}명" -> "인원 2명").
    """
    if isinstance(node, dict):
        return {k: render(v, ctx) for k, v in node.items()}
    if isinstance(node, list):
        return [render(v, ctx) for v in node]
    if isinstance(node, str):
        stripped = node.strip()
        if stripped.startswith("{") and stripped.endswith("}") and stripped.count("{") == 1:
            key = stripped[1:-1]
            if key in ctx:
                return ctx[key]
            raise SpecError(f"스펙에 알 수 없는 placeholder: {stripped}")
        try:
            return node.format(**ctx)
        except KeyError as exc:
            raise SpecError(f"스펙에 알 수 없는 placeholder: {exc} (in {node!r})") from exc
    return node


def parse_hhmm(value: Any) -> time:
    """'0930', '09:30', '093000', '09:30:00' 을 time으로."""
    if isinstance(value, time):
        return value
    s = str(value or "").strip().replace(":", "")
    if len(s) < 4 or not s[:4].isdigit():
        raise SpecError(f"시각 형식을 해석할 수 없습니다: {value!r}")
    return time(int(s[:2]), int(s[2:4]))


def parse_seat_count(value: Any, available_values: tuple[str, ...], passengers: int) -> int:
    """잔여석 필드를 좌석 수로 정규화한다.

    응답이 숫자면 그대로, '예약가능'/'Y' 같은 상태 문자열이면 요청 인원만큼
    있다고 본다(정확한 수를 모르므로 최소 보장값). 그 외에는 0.
    """
    if isinstance(value, bool):
        return passengers if value else 0
    if isinstance(value, int):
        return max(value, 0)
    s = str(value or "").strip()
    if s.isdigit():
        return int(s)
    return passengers if s in available_values else 0


class EndpointSpec:
    """endpoints.json 을 감싼 얇은 래퍼."""

    def __init__(self, data: dict[str, Any], path: Path | None = None) -> None:
        self.data = data
        self.path = path
        if not data.get("base_url"):
            raise SpecError(
                f"{path or 'spec'}: base_url 이 비어 있습니다. "
                "README의 '1단계: API 파악'을 따라 캡처한 값을 채워주세요."
            )

    @classmethod
    def load(cls, path: str | Path) -> EndpointSpec:
        p = Path(path)
        if not p.exists():
            raise SpecError(
                f"엔드포인트 스펙이 없습니다: {p}\n"
                "endpoints.example.json 을 복사해 캡처한 값을 채워주세요."
            )
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SpecError(f"{p}: JSON 파싱 실패 - {exc}") from exc
        return cls(data, p)

    def section(self, name: str) -> dict[str, Any]:
        sec = self.data.get(name)
        if not isinstance(sec, dict) or not sec.get("path"):
            raise SpecError(f"스펙에 '{name}' 섹션의 path가 없습니다.")
        return sec

    def has(self, name: str) -> bool:
        return isinstance(self.data.get(name), dict) and bool(self.data[name].get("path"))

    @property
    def block_indicators(self) -> tuple[str, ...]:
        return tuple(self.data.get("block_indicators") or DEFAULT_BLOCK_INDICATORS)


class KorailPlusClient:
    """조회와 좌석 선점까지만 수행한다. 결제 API는 구현하지 않는다."""

    def __init__(
        self,
        spec: EndpointSpec,
        login_id: str = "",
        password: str = "",
        *,
        client: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self.spec = spec
        self.login_id = login_id
        self.password = password
        self._own_client = client is None
        self._client = client or httpx.Client(
            base_url=spec.data["base_url"],
            headers=spec.data.get("headers") or {},
            timeout=timeout,
            follow_redirects=True,
        )
        self._logged_in = False

    def close(self) -> None:
        if self._own_client:
            self._client.close()

    def __enter__(self) -> KorailPlusClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- 내부 ---------------------------------------------------------------

    def _call(self, name: str, ctx: dict[str, Any]) -> Any:
        sec = self.spec.section(name)
        method = str(sec.get("method", "POST")).upper()
        url = render(sec["path"], ctx)
        kwargs: dict[str, Any] = {}
        for key, field in (("json", "json"), ("data", "data"), ("params", "params")):
            if sec.get(field) is not None:
                kwargs[key] = render(sec[field], ctx)
        if sec.get("headers"):
            kwargs["headers"] = render(sec["headers"], ctx)

        try:
            resp = self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise TransientError(f"{name} 요청 실패: {exc}") from exc

        if resp.status_code in (401, 403, 429):
            raise BlockedError(
                f"{name} 응답 {resp.status_code} - 차단 또는 인증 만료로 판단해 중단합니다."
            )
        if resp.status_code >= 500:
            raise TransientError(f"{name} 응답 {resp.status_code}")
        if resp.status_code >= 400:
            raise KorailWatchHTTPError(f"{name} 응답 {resp.status_code}: {resp.text[:200]}")

        body = resp.text
        for word in self.spec.block_indicators:
            if word in body:
                raise BlockedError(f"{name} 응답에 차단 신호 '{word}' 가 포함되어 중단합니다.")

        try:
            return resp.json()
        except ValueError:
            return {"_text": body}

    # -- 공개 API -----------------------------------------------------------

    def login(self) -> None:
        if not self.spec.has("login"):
            self._logged_in = True
            return
        if not self.login_id or not self.password:
            raise AuthError("KORAIL_ID / KORAIL_PW 환경변수가 비어 있습니다.")

        payload = self._call(
            "login", {"login_id": self.login_id, "password": self.password}
        )
        sec = self.spec.section("login")

        ok_path = sec.get("success_path")
        if ok_path and not dig(payload, ok_path):
            raise AuthError(f"로그인 실패: {str(payload)[:200]}")

        token_path = sec.get("token_path")
        if token_path:
            token = dig(payload, token_path)
            if not token:
                raise AuthError(f"응답에서 토큰({token_path})을 찾지 못했습니다.")
            header = sec.get("auth_header", "Authorization")
            fmt = sec.get("auth_format", "Bearer {token}")
            self._client.headers[header] = fmt.format(token=token)
        self._logged_in = True

    def search(self, criteria: WatchCriteria) -> list[Train]:
        if not self._logged_in:
            self.login()

        sec = self.spec.section("search")
        payload = self._call("search", self._criteria_ctx(criteria))
        rows = dig(payload, sec.get("list_path", "")) or []
        if not isinstance(rows, list):
            raise SpecError(
                f"list_path '{sec.get('list_path')}' 가 리스트가 아닙니다: {type(rows).__name__}"
            )

        fields = sec.get("fields") or {}
        seat_fields = sec.get("seat_fields") or {}
        available_values = tuple(sec.get("seat_available_values") or ("예약가능", "Y"))

        trains: list[Train] = []
        for row in rows:
            trains.append(
                Train(
                    train_no=str(dig(row, fields.get("train_no", "trainNo")) or ""),
                    train_name=str(dig(row, fields.get("train_name", "trainName")) or ""),
                    dep_station=str(dig(row, fields.get("dep_station", "")) or criteria.dep_station),
                    arr_station=str(dig(row, fields.get("arr_station", "")) or criteria.arr_station),
                    dep_time=parse_hhmm(dig(row, fields.get("dep_time", "depTime"))),
                    arr_time=parse_hhmm(dig(row, fields.get("arr_time", "arrTime"))),
                    seats={
                        label: parse_seat_count(
                            dig(row, field), available_values, criteria.passengers
                        )
                        for label, field in seat_fields.items()
                    },
                )
            )
        return trains

    def reserve(
        self, train: Train, seat_type: str, criteria: WatchCriteria
    ) -> Reservation:
        """좌석 선점까지만. 결제는 코레일+ 앱에서 직접 진행해야 한다."""
        if not self.spec.has("reserve"):
            raise SpecError(
                "스펙에 reserve 섹션이 없습니다. 알림만 받으려면 --reserve 를 빼고 실행하세요."
            )
        ctx = self._criteria_ctx(criteria) | {
            "train_no": train.train_no,
            "train_name": train.train_name,
            "seat_type": seat_type,
            "dep_time": f"{train.dep_time:%H%M}",
            "arr_time": f"{train.arr_time:%H%M}",
        }
        payload = self._call("reserve", ctx)
        sec = self.spec.section("reserve")
        no = dig(payload, sec.get("reservation_no_path", "")) or ""
        if not no:
            raise KorailWatchHTTPError(f"선점 응답에서 예약번호를 찾지 못했습니다: {str(payload)[:200]}")
        return Reservation(
            reservation_no=str(no),
            train=train,
            seat_type=seat_type,
            pay_deadline=str(dig(payload, sec.get("deadline_path", "")) or "선점 후 약 20분"),
            raw=payload if isinstance(payload, dict) else {},
        )

    def _criteria_ctx(self, criteria: WatchCriteria) -> dict[str, Any]:
        return {
            "dep_station": criteria.dep_station,
            "arr_station": criteria.arr_station,
            "date": f"{criteria.travel_date:%Y%m%d}",
            "date_dashed": f"{criteria.travel_date:%Y-%m-%d}",
            "time": f"{criteria.time_from:%H%M}00",
            "passengers": criteria.passengers,
            "login_id": self.login_id,
            "password": self.password,
        }


class KorailWatchHTTPError(TransientError):
    """4xx 등 재시도 여지가 애매한 응답."""
