import json
from datetime import date, time

import httpx
import pytest

from korail_watch.api import EndpointSpec, KorailPlusClient, dig, parse_hhmm, render
from korail_watch.errors import AuthError, BlockedError, SpecError, TransientError
from korail_watch.models import Train, WatchCriteria

SPEC = {
    "base_url": "https://example.test",
    "block_indicators": ["매크로"],
    "login": {
        "method": "POST",
        "path": "/login",
        "json": {"userId": "{login_id}", "password": "{password}"},
        "success_path": "ok",
        "token_path": "data.token",
    },
    "search": {
        "method": "POST",
        "path": "/search",
        "json": {"dep": "{dep_station}", "date": "{date}", "adult": "{passengers}"},
        "list_path": "data.trainList",
        "fields": {"train_no": "trainNo", "train_name": "trainName",
                   "dep_time": "depTime", "arr_time": "arrTime"},
        "seat_fields": {"일반실": "general", "특실": "special"},
        "seat_available_values": ["예약가능"],
    },
    "reserve": {
        "method": "POST",
        "path": "/reserve",
        "json": {"trainNo": "{train_no}", "seat": "{seat_type}"},
        "reservation_no_path": "data.reservationNo",
        "deadline_path": "data.payLimit",
    },
}

CRITERIA = WatchCriteria(
    dep_station="서울", arr_station="부산", travel_date=date(2026, 9, 20),
    time_from=time(9, 0), time_to=time(13, 0), passengers=2,
)

TRAIN_ROW = {
    "trainNo": "101", "trainName": "KTX",
    "depTime": "093000", "arrTime": "121500",
    "general": "예약가능", "special": "매진",
}


def client_with(handler, spec=None):
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, base_url=SPEC["base_url"])
    return KorailPlusClient(EndpointSpec(spec or SPEC), "id", "pw", client=http)


def default_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/login":
        return httpx.Response(200, json={"ok": True, "data": {"token": "T0KEN"}})
    if request.url.path == "/search":
        return httpx.Response(200, json={"data": {"trainList": [TRAIN_ROW]}})
    if request.url.path == "/reserve":
        return httpx.Response(
            200, json={"data": {"reservationNo": "R123", "payLimit": "20분 이내"}}
        )
    return httpx.Response(404)


def test_spec_requires_base_url():
    with pytest.raises(SpecError):
        EndpointSpec({"base_url": ""})


def test_missing_spec_file_gives_actionable_error(tmp_path):
    with pytest.raises(SpecError, match="endpoints.example.json"):
        EndpointSpec.load(tmp_path / "nope.json")


def test_invalid_json_reports_file(tmp_path):
    bad = tmp_path / "endpoints.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(SpecError, match="JSON 파싱 실패"):
        EndpointSpec.load(bad)


def test_render_rejects_unknown_placeholder():
    with pytest.raises(SpecError):
        render({"a": "{nope}"}, {"passengers": 1})


def test_dig_handles_lists_and_missing_keys():
    assert dig({"a": [{"b": 7}]}, "a.0.b") == 7
    assert dig({"a": 1}, "a.b.c") is None
    assert dig({}, "missing") is None


@pytest.mark.parametrize("value", ["0930", "09:30", "093000", "09:30:00"])
def test_parse_hhmm_accepts_common_formats(value):
    assert parse_hhmm(value) == time(9, 30)


def test_parse_hhmm_rejects_garbage():
    with pytest.raises(SpecError):
        parse_hhmm("아침")


def test_login_sets_auth_header_and_search_parses_rows():
    seen = {}

    def handler(request):
        seen[request.url.path] = (
            dict(request.headers),
            json.loads(request.content) if request.content else None,
        )
        return default_handler(request)

    with client_with(handler) as c:
        trains = c.search(CRITERIA)

    assert seen["/search"][0]["authorization"] == "Bearer T0KEN"
    assert seen["/search"][1] == {"dep": "서울", "date": "20260920", "adult": 2}, \
        "placeholder 치환 시 정수 타입이 보존되어야 한다"

    (train,) = trains
    assert (train.train_no, train.dep_time, train.arr_time) == ("101", time(9, 30), time(12, 15))
    assert train.seats == {"일반실": 2, "특실": 0}
    assert CRITERIA.matches(train) == {"일반실": 2}


def test_login_failure_raises_auth_error():
    def handler(request):
        return httpx.Response(200, json={"ok": False})

    with client_with(handler) as c, pytest.raises(AuthError):
        c.search(CRITERIA)


def test_missing_credentials_raise_auth_error():
    http = httpx.Client(transport=httpx.MockTransport(default_handler))
    with KorailPlusClient(EndpointSpec(SPEC), "", "", client=http) as c:
        with pytest.raises(AuthError, match="KORAIL_ID"):
            c.login()


@pytest.mark.parametrize("status", [401, 403, 429])
def test_blocking_status_codes_raise_blocked(status):
    def handler(request):
        if request.url.path == "/login":
            return httpx.Response(200, json={"ok": True, "data": {"token": "T"}})
        return httpx.Response(status)

    with client_with(handler) as c, pytest.raises(BlockedError):
        c.search(CRITERIA)


def test_block_keyword_in_body_raises_blocked():
    def handler(request):
        if request.url.path == "/login":
            return httpx.Response(200, json={"ok": True, "data": {"token": "T"}})
        return httpx.Response(200, json={"message": "매크로 의심 접속입니다"})

    with client_with(handler) as c, pytest.raises(BlockedError, match="매크로"):
        c.search(CRITERIA)


def test_server_error_is_transient():
    def handler(request):
        if request.url.path == "/login":
            return httpx.Response(200, json={"ok": True, "data": {"token": "T"}})
        return httpx.Response(503)

    with client_with(handler) as c, pytest.raises(TransientError):
        c.search(CRITERIA)


def test_network_failure_is_transient():
    def handler(request):
        raise httpx.ConnectError("boom")

    with client_with(handler) as c, pytest.raises(TransientError):
        c.search(CRITERIA)


def test_bad_list_path_is_reported_as_spec_error():
    spec = json.loads(json.dumps(SPEC))
    spec["search"]["list_path"] = "data"

    with client_with(default_handler, spec) as c, pytest.raises(SpecError, match="list_path"):
        c.search(CRITERIA)


def test_reserve_returns_reservation_without_payment():
    train = Train(
        train_no="101", train_name="KTX", dep_station="서울", arr_station="부산",
        dep_time=time(9, 30), arr_time=time(12, 15), seats={"일반실": 2},
    )
    with client_with(default_handler) as c:
        c.login()
        reservation = c.reserve(train, "일반실", CRITERIA)

    assert reservation.reservation_no == "R123"
    assert reservation.pay_deadline == "20분 이내"


def test_reserve_without_spec_section_is_spec_error():
    spec = {k: v for k, v in SPEC.items() if k != "reserve"}
    train = Train(
        train_no="101", train_name="KTX", dep_station="서울", arr_station="부산",
        dep_time=time(9, 30), arr_time=time(12, 15), seats={"일반실": 2},
    )
    with client_with(default_handler, spec) as c, pytest.raises(SpecError, match="--reserve"):
        c.reserve(train, "일반실", CRITERIA)


def test_client_has_no_payment_method():
    assert not [m for m in dir(KorailPlusClient) if "pay" in m.lower()]
