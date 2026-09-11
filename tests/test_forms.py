from datetime import date, time

import pytest

from korail_watch.cadence import MIN_INTERVAL
from korail_watch.forms import (
    DEFAULTS,
    FormError,
    build_run_spec,
    parse_seats,
    parse_travel_date,
)

TODAY = date(2026, 9, 11)


def form(**overrides):
    values = dict(DEFAULTS)
    values.update({"date": "2026-09-20", "use_windows": False})
    values.update(overrides)
    return values


def test_builds_criteria_and_config():
    spec = build_run_spec(form(time="0900-1330", passengers="2"), today=TODAY)

    assert spec.criteria.dep_station == "서울"
    assert spec.criteria.time_from == time(9, 0)
    assert spec.criteria.passengers == 2
    assert spec.config.interval == 45
    assert spec.config.windows == ()


def test_windows_applied_when_enabled():
    spec = build_run_spec(form(use_windows=True), today=TODAY)

    assert spec.config.windows
    assert any(w.interval == 6 for w in spec.config.windows)


def test_windows_ignored_when_disabled():
    spec = build_run_spec(form(use_windows=False, windows="1200-1300@8"), today=TODAY)

    assert spec.config.windows == ()


def test_seat_combo_choice_expands():
    spec = build_run_spec(form(seats="일반실+특실"), today=TODAY)

    assert spec.criteria.seat_types == ("일반실", "특실")


@pytest.mark.parametrize(
    "raw,expected",
    [("2026-09-20", date(2026, 9, 20)), ("20260920", date(2026, 9, 20)),
     ("0920", date(2026, 9, 20))],
)
def test_parse_travel_date(raw, expected):
    assert parse_travel_date(raw, today=TODAY) == expected


def test_bare_date_already_passed_rolls_to_next_year():
    assert parse_travel_date("0105", today=TODAY) == date(2027, 1, 5)


def test_empty_date_is_a_form_error():
    with pytest.raises(FormError) as exc:
        parse_travel_date("", today=TODAY)
    assert exc.value.field == "date"


def test_past_date_rejected():
    with pytest.raises(FormError, match="지난 날짜"):
        build_run_spec(form(date="2026-09-01"), today=TODAY)


def test_same_stations_rejected():
    with pytest.raises(FormError) as exc:
        build_run_spec(form(arr="서울"), today=TODAY)
    assert exc.value.field == "arr"


def test_blank_station_rejected():
    with pytest.raises(FormError) as exc:
        build_run_spec(form(dep="   "), today=TODAY)
    assert exc.value.field == "dep"


def test_bad_time_range_names_the_field():
    with pytest.raises(FormError) as exc:
        build_run_spec(form(time="9-13"), today=TODAY)
    assert exc.value.field == "time"


@pytest.mark.parametrize("bad", ["0", "-1", "두명", ""])
def test_bad_passenger_count_rejected(bad):
    with pytest.raises(FormError) as exc:
        build_run_spec(form(passengers=bad), today=TODAY)
    assert exc.value.field == "passengers"


def test_fractional_passengers_rejected():
    with pytest.raises(FormError, match="정수"):
        build_run_spec(form(passengers="1.5"), today=TODAY)


def test_interval_below_floor_names_the_field():
    with pytest.raises(FormError) as exc:
        build_run_spec(form(interval=str(MIN_INTERVAL - 1)), today=TODAY)
    assert exc.value.field == "interval"


def test_bad_window_spec_names_the_field():
    with pytest.raises(FormError) as exc:
        build_run_spec(form(use_windows=True, windows="1200-1300@1"), today=TODAY)
    assert exc.value.field == "windows"


def test_empty_seats_rejected():
    with pytest.raises(FormError):
        parse_seats("  ,  ")


def test_flags_accept_checkbox_booleans_and_strings():
    assert build_run_spec(form(reserve=True), today=TODAY).reserve
    assert build_run_spec(form(reserve="on"), today=TODAY).reserve
    assert not build_run_spec(form(reserve=False), today=TODAY).reserve


def test_spec_path_falls_back_to_default():
    assert build_run_spec(form(spec_path=" "), today=TODAY).spec_path == "endpoints.json"


def test_train_names_parsed():
    spec = build_run_spec(form(trains="KTX, SRT"), today=TODAY)

    assert spec.criteria.train_names == ("KTX", "SRT")
