"""명령줄 진입점."""

from __future__ import annotations

import argparse
import os
import sys
import time as _time
from dataclasses import replace
from datetime import date, datetime, time
from pathlib import Path

from .api import EndpointSpec, KorailPlusClient
from .cadence import DEFAULT_WINDOWS, MIN_INTERVAL, parse_windows
from .envfile import load_dotenv
from .errors import KorailWatchError
from .models import Train, WatchCriteria
from .notify import ConsoleNotifier, MultiNotifier, build_notifiers
from .poller import Poller, PollerConfig, StopReason
from .sources import FakeTrainSource


def parse_date(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%m-%d", "%m%d"):
        try:
            parsed = datetime.strptime(value, fmt).date()
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=date.today().year)
        return parsed
    raise argparse.ArgumentTypeError(f"날짜 형식이 잘못되었습니다: {value} (예: 2026-09-20)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="korail-watch",
        description="코레일+ 빈자리 감시. 조회와 좌석 선점까지만 하고 결제는 하지 않습니다.",
    )
    p.add_argument("--dep", required=True, help="출발역 (예: 서울)")
    p.add_argument("--arr", required=True, help="도착역 (예: 부산)")
    p.add_argument("--date", required=True, type=parse_date, help="출발일 (2026-09-20)")
    p.add_argument("--time", default="0000-2359", help="시간대 (예: 0900-1330)")
    p.add_argument("--seats", default="일반실", help="좌석 종류, 쉼표 구분 (예: 일반실,특실)")
    p.add_argument("--passengers", type=int, default=1, help="인원 수")
    p.add_argument("--trains", default="", help="열차명 제한, 쉼표 구분 (예: KTX,SRT)")
    p.add_argument("--spec", default="endpoints.json", help="엔드포인트 스펙 경로")
    p.add_argument(
        "--interval",
        type=float,
        default=45.0,
        help=f"집중 구간 밖의 기본 조회 간격(초), 최소 {MIN_INTERVAL:g}",
    )
    p.add_argument(
        "--windows",
        default="",
        help="취소표가 몰리는 시간대만 간격을 좁힌다. 예: 2340-0025@6,1800-2000@15",
    )
    p.add_argument(
        "--cancel-hunt",
        action="store_true",
        help=f"취소표 사냥 프리셋. --windows '{DEFAULT_WINDOWS}' 와 같다",
    )
    p.add_argument("--max-hours", type=float, default=6.0, help="최대 실행 시간")
    p.add_argument(
        "--max-requests", type=int, default=1200, help="총 조회 요청 상한"
    )
    p.add_argument(
        "--reserve",
        action="store_true",
        help="빈자리를 찾으면 좌석 선점까지 시도 (결제는 앱에서 직접)",
    )
    p.add_argument("--demo", action="store_true", help="가짜 데이터로 알림 경로만 점검")
    return p


def build_notifier() -> MultiNotifier:
    notifiers = build_notifiers(dict(os.environ), extra=[ConsoleNotifier()])
    if len(notifiers) == 1:
        print(
            "[안내] 카카오톡·텔레그램 설정이 없어 콘솔로만 알립니다. "
            "scripts/kakao_setup.py 를 참고하세요.",
            file=sys.stderr,
        )
    return MultiNotifier(*notifiers)


class VirtualClock:
    """데모 전용. 실제로 자지 않고 시간만 흐르게 해 루프가 즉시 끝나게 한다."""

    def __init__(self) -> None:
        self.now = 0.0

    def sleep(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def demo_source(criteria: WatchCriteria) -> FakeTrainSource:
    hit = Train(
        train_no="101",
        train_name="KTX",
        dep_station=criteria.dep_station,
        arr_station=criteria.arr_station,
        dep_time=max(criteria.time_from, time(9, 0)),
        arr_time=time(11, 40),
        seats={criteria.seat_types[0]: max(criteria.passengers, 1)},
    )
    return FakeTrainSource([[], [], [hit]])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_dotenv(Path(".env"))

    try:
        time_from, time_to = WatchCriteria.parse_time_range(args.time)
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    criteria = WatchCriteria(
        dep_station=args.dep,
        arr_station=args.arr,
        travel_date=args.date,
        time_from=time_from,
        time_to=time_to,
        seat_types=tuple(s.strip() for s in args.seats.split(",") if s.strip()),
        passengers=args.passengers,
        train_names=tuple(t.strip() for t in args.trains.split(",") if t.strip()),
    )

    window_spec = args.windows or (DEFAULT_WINDOWS if args.cancel_hunt else "")
    try:
        windows = parse_windows(window_spec) if window_spec else ()
        config = PollerConfig(
            interval=args.interval,
            windows=windows,
            max_duration=args.max_hours * 3600,
            max_requests=args.max_requests,
        )
    except ValueError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    if args.demo:
        # 데모는 가상 시계로 도니 몇 번만 돌고 끝나게 한다.
        config = replace(config, max_duration=config.interval * 4)
    notifier = build_notifier()

    print(
        f"감시 시작: {criteria.dep_station} → {criteria.arr_station} "
        f"{criteria.travel_date:%Y-%m-%d} {time_from:%H:%M}~{time_to:%H:%M} "
        f"/ {', '.join(criteria.seat_types)} {criteria.passengers}명"
    )
    print(
        f"조회: {config.cadence.describe()} "
        f"/ 최대 {args.max_hours:g}시간 / 요청 상한 {config.max_requests}회"
    )
    if args.reserve:
        print("선점 모드: 빈자리를 찾으면 예약까지 시도합니다. 결제는 코레일+ 앱에서 직접 하세요.")
    else:
        print(
            "알림 전용 모드입니다. 취소표는 알림을 보고 손으로 잡기엔 너무 빨리 사라지니,"
            " 실제로 구하려면 --reserve 를 쓰세요."
        )

    client = None
    clock = VirtualClock() if args.demo else None
    try:
        if args.demo:
            source = demo_source(criteria)
        else:
            spec = EndpointSpec.load(args.spec)
            client = KorailPlusClient(
                spec,
                login_id=os.getenv("KORAIL_ID", ""),
                password=os.getenv("KORAIL_PW", ""),
            )
            source = client

        poller = Poller(
            source,
            criteria,
            notifier,
            config,
            reserve=args.reserve,
            sleep=clock.sleep if clock else _time.sleep,
            clock=clock if clock else _time.monotonic,
        )
        result = poller.run()
    except KorailWatchError as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n중단했습니다.")
        return 130
    finally:
        if client is not None:
            client.close()

    print(f"\n종료: {result.reason.value} (조회 {result.polls}회, 매치 {len(result.matches)}건)")
    if result.detail:
        print(f"상세: {result.detail}")
    if result.reservation:
        print(f"예약번호 {result.reservation.reservation_no} - 앱에서 결제하세요.")
    return 0 if result.reason in (StopReason.RESERVED, StopReason.TIME_LIMIT) else 1


if __name__ == "__main__":
    raise SystemExit(main())
