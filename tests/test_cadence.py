from datetime import datetime, time

import pytest

from korail_watch.cadence import (
    DEFAULT_WINDOWS,
    MIN_INTERVAL,
    Cadence,
    Window,
    parse_windows,
)


def test_window_contains_plain_range():
    w = Window(start=time(7, 0), end=time(9, 0), interval=15)
    assert w.contains(datetime(2026, 9, 20, 8, 0))
    assert not w.contains(datetime(2026, 9, 20, 9, 1))


def test_window_contains_range_crossing_midnight():
    w = Window(start=time(23, 40), end=time(0, 25), interval=6)
    assert w.contains(time(23, 55))
    assert w.contains(time(0, 10))
    assert not w.contains(time(12, 0))


def test_window_rejects_interval_below_floor():
    with pytest.raises(ValueError, match="이상이어야"):
        Window(start=time(0, 0), end=time(1, 0), interval=MIN_INTERVAL - 1)


def test_cadence_first_matching_window_wins():
    cadence = Cadence(
        base_interval=45,
        windows=(
            Window(start=time(0, 0), end=time(1, 0), interval=6),
            Window(start=time(0, 30), end=time(2, 0), interval=30),
        ),
    )
    assert cadence.interval_at(datetime(2026, 9, 20, 0, 45)) == 6
    assert cadence.interval_at(datetime(2026, 9, 20, 1, 30)) == 30
    assert cadence.interval_at(datetime(2026, 9, 20, 5, 0)) == 45


def test_cadence_rejects_base_below_floor():
    with pytest.raises(ValueError):
        Cadence(base_interval=1)


def test_active_window_reports_none_outside():
    cadence = Cadence(45, (Window(time(7, 0), time(8, 0), 15),))
    assert cadence.active_window(datetime(2026, 9, 20, 7, 30)) is not None
    assert cadence.active_window(datetime(2026, 9, 20, 9, 30)) is None


def test_parse_windows_roundtrip():
    windows = parse_windows("2340-0025@6, 0700-0900@15")

    assert len(windows) == 2
    assert (windows[0].start, windows[0].end, windows[0].interval) == (
        time(23, 40), time(0, 25), 6.0,
    )
    assert windows[1].interval == 15.0


def test_default_windows_parse_and_respect_floor():
    windows = parse_windows(DEFAULT_WINDOWS)

    assert windows
    assert all(w.interval >= MIN_INTERVAL for w in windows)


@pytest.mark.parametrize("bad", ["0700-0900", "0700-0900@fast", "", "@5"])
def test_parse_windows_rejects_bad_specs(bad):
    with pytest.raises(ValueError):
        parse_windows(bad)


def test_parse_windows_rejects_interval_below_floor():
    with pytest.raises(ValueError):
        parse_windows("0000-0030@1")


def test_describe_mentions_windows():
    text = Cadence(45, parse_windows("2340-0025@6")).describe()

    assert "45" in text and "6초" in text


def test_describe_without_windows():
    assert Cadence(45).describe() == "45초 간격"
