"""GUI 워커 스레드 로직. tkinter 없이 돈다."""

import queue
import threading
from datetime import date, time

import pytest

from korail_watch.errors import BlockedError
from korail_watch.forms import RunSpec
from korail_watch.gui import QueueNotifier, demo_source, load_dotenv, run_watch
from korail_watch.models import WatchCriteria
from korail_watch.poller import PollerConfig, StopReason

CRITERIA = WatchCriteria(
    dep_station="서울", arr_station="부산", travel_date=date(2026, 9, 20),
    time_from=time(9, 0), time_to=time(13, 0), seat_types=("일반실",),
)


def drain(q: queue.Queue) -> list[tuple]:
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def test_queue_notifier_implements_notifier():
    q: queue.Queue = queue.Queue()
    QueueNotifier(q).send("빈자리 발견", "KTX 101")

    assert drain(q) == [("alert", "빈자리 발견", "KTX 101")]


def test_demo_source_eventually_yields_a_matching_train():
    spec = RunSpec(criteria=CRITERIA, config=PollerConfig(), demo=True)
    source = demo_source(spec)

    results = [source.search(CRITERIA) for _ in range(3)]

    assert results[0] == [] and results[1] == []
    assert CRITERIA.matches(results[2][0])


def test_run_watch_demo_reports_alert_and_done(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    spec = RunSpec(
        criteria=CRITERIA,
        config=PollerConfig(interval=5, jitter=0.0, max_requests=10),
        reserve=True,
        demo=True,
    )
    q: queue.Queue = queue.Queue()

    run_watch(spec, q, threading.Event(), sleep=lambda _s: None)
    kinds = [m[0] for m in drain(q)]

    assert "alert" in kinds
    assert kinds[-1] == "done"


def test_run_watch_emits_progress_for_the_gui():
    spec = RunSpec(
        criteria=CRITERIA,
        config=PollerConfig(interval=5, jitter=0.0, max_requests=3),
        demo=True,
    )
    q: queue.Queue = queue.Queue()

    run_watch(spec, q, threading.Event(), sleep=lambda _s: None)
    progress = [m[1] for m in drain(q) if m[0] == "progress"]

    assert progress
    assert progress[0].polls == 1
    assert progress[0].next_delay == 5


def test_already_set_stop_event_halts_before_any_request():
    spec = RunSpec(criteria=CRITERIA, config=PollerConfig(), demo=True)
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    stop.set()

    run_watch(spec, q, stop)
    done = [m[1] for m in drain(q) if m[0] == "done"]

    assert done[0].reason is StopReason.INTERRUPTED
    assert done[0].polls == 0


def test_stop_event_interrupts_a_long_sleep():
    """정지 버튼이 45초 대기를 기다리지 않고 먹혀야 한다."""
    spec = RunSpec(
        criteria=CRITERIA,
        config=PollerConfig(interval=3600, jitter=0.0, max_duration=7200),
        demo=True,
    )
    q: queue.Queue = queue.Queue()
    stop = threading.Event()
    worker = threading.Thread(target=run_watch, args=(spec, q, stop), daemon=True)

    worker.start()
    stop.set()
    worker.join(timeout=5)

    assert not worker.is_alive(), "stop_event 가 sleep 을 깨우지 못했다"


def test_missing_spec_file_is_reported_as_error(tmp_path):
    spec = RunSpec(
        criteria=CRITERIA,
        config=PollerConfig(),
        spec_path=str(tmp_path / "absent.json"),
    )
    q: queue.Queue = queue.Queue()

    run_watch(spec, q, threading.Event())
    errors = [m for m in drain(q) if m[0] == "error"]

    assert errors and "엔드포인트 스펙이 없습니다" in errors[0][1]


def test_blocked_source_surfaces_as_done_not_crash():
    class Blocked:
        def search(self, criteria):
            raise BlockedError("매크로 의심")

    spec = RunSpec(criteria=CRITERIA, config=PollerConfig(), demo=True)
    q: queue.Queue = queue.Queue()
    import korail_watch.gui as gui

    original = gui.demo_source
    gui.demo_source = lambda _spec: Blocked()
    try:
        run_watch(spec, q, threading.Event())
    finally:
        gui.demo_source = original

    done = [m[1] for m in drain(q) if m[0] == "done"]
    assert done[0].reason is StopReason.BLOCKED


def test_load_dotenv_does_not_override_shell(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("KORAIL_ID=file\n", encoding="utf-8")
    monkeypatch.setenv("KORAIL_ID", "shell")

    load_dotenv(env)

    import os
    assert os.environ["KORAIL_ID"] == "shell"
