from datetime import date, time

import pytest

from korail_watch.models import Train, WatchCriteria


def make_train(**kw):
    base = dict(
        train_no="101",
        train_name="KTX",
        dep_station="서울",
        arr_station="부산",
        dep_time=time(10, 0),
        arr_time=time(12, 40),
        seats={"일반실": 2, "특실": 0},
    )
    return Train(**{**base, **kw})


def criteria(**kw):
    base = dict(
        dep_station="서울",
        arr_station="부산",
        travel_date=date(2026, 9, 20),
        time_from=time(9, 0),
        time_to=time(13, 0),
        seat_types=("일반실",),
        passengers=1,
    )
    return WatchCriteria(**{**base, **kw})


@pytest.mark.parametrize(
    "spec,expected",
    [("0900-1330", (time(9, 0), time(13, 30))), ("09:00-13:30", (time(9, 0), time(13, 30)))],
)
def test_parse_time_range(spec, expected):
    assert WatchCriteria.parse_time_range(spec) == expected


@pytest.mark.parametrize("bad", ["9-13", "0900~1330", "1400-0900", ""])
def test_parse_time_range_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        WatchCriteria.parse_time_range(bad)


def test_matches_returns_available_seats():
    assert criteria().matches(make_train()) == {"일반실": 2}


def test_no_match_outside_time_window():
    assert criteria().matches(make_train(dep_time=time(14, 30))) == {}


def test_no_match_when_seats_fewer_than_passengers():
    assert criteria(passengers=3).matches(make_train()) == {}


def test_no_match_when_seat_type_not_watched():
    assert criteria(seat_types=("특실",)).matches(make_train()) == {}


def test_train_name_filter():
    assert criteria(train_names=("SRT",)).matches(make_train()) == {}
    assert criteria(train_names=("KTX",)).matches(make_train()) == {"일반실": 2}


def test_train_key_distinguishes_departures():
    assert make_train().key != make_train(dep_time=time(11, 0)).key
