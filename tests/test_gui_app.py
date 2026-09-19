"""실제 Tk 위젯이 뜨는지 확인하는 스모크 테스트.

tkinter 나 디스플레이가 없는 환경에서는 건너뛴다.
CI/헤드리스에서 돌리려면: xvfb-run -a pytest tests/test_gui_app.py
"""

import time

import pytest

tk = pytest.importorskip("tkinter", reason="tkinter 미설치")
from tkinter import filedialog, ttk  # noqa: E402

from korail_watch.gui import App  # noqa: E402


class SilentBox:
    """모달이 테스트를 멈추지 않게 호출만 기록한다."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def showinfo(self, title, message):
        self.calls.append(("info", title))

    def showerror(self, title, message):
        self.calls.append(("error", title, message))

    def showwarning(self, title, message):
        self.calls.append(("warning", title))

    def askokcancel(self, title, message):
        return True


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # 설정 파일이 저장소를 건드리지 않게
    try:
        root = tk.Tk()
    except tk.TclError as exc:  # pragma: no cover - 디스플레이 없음
        pytest.skip(f"디스플레이 없음: {exc}")
    box = SilentBox()
    instance = App(root, tk=tk, ttk=ttk, filedialog=filedialog, messagebox=box)
    instance.messages = box
    yield instance
    root.destroy()


def pump_until(root, predicate, timeout=40.0):
    deadline = time.time() + timeout
    while time.time() < deadline and not predicate():
        root.update()
        time.sleep(0.02)
    return predicate()


def test_window_builds_with_expected_fields(app):
    for key in ("dep", "arr", "date", "time", "seats", "passengers",
                "interval", "windows", "reserve", "demo", "spec_path"):
        assert key in app.vars, f"{key} 입력란이 없다"


def test_invalid_input_shows_error_and_does_not_start(app):
    app.vars["passengers"].set("두명")

    app._start()

    assert app.messages.calls[0][0] == "error"
    assert app.worker is None
    assert str(app.start_btn["state"]) == "normal"


def test_window_entry_disabled_when_unchecked(app):
    app.vars["use_windows"].set(False)
    app._toggle_windows()

    assert str(app.windows_entry["state"]) == "disabled"


def test_demo_run_logs_alert_and_reenables_buttons(app):
    app.vars["demo"].set(True)
    app.vars["interval"].set("5")
    app.vars["reserve"].set(True)
    app.vars["date"].set("2026-12-20")

    app._start()
    assert str(app.start_btn["state"]) == "disabled"
    assert str(app.stop_btn["state"]) == "normal"

    finished = pump_until(app.root, lambda: str(app.start_btn["state"]) == "normal")
    log = app.log_text.get("1.0", "end")

    assert finished, "감시가 끝나고 버튼이 복구되어야 한다"
    assert "빈자리 발견" in log
    assert "좌석 선점 완료" in log
    assert ("info", "좌석 선점 완료 - 결제 필요") in app.messages.calls
    assert app.status.get() == "좌석 선점 완료"


def test_stop_button_halts_a_long_wait(app):
    app.vars["demo"].set(True)
    app.vars["interval"].set("3600")
    app.vars["reserve"].set(False)
    app.vars["date"].set("2026-12-20")

    app._start()
    pump_until(app.root, lambda: app.worker is not None and app.worker.is_alive(), 5)
    app._stop()

    stopped = pump_until(app.root, lambda: not app.worker.is_alive(), 10)

    assert stopped, "정지 버튼이 긴 대기를 깨우지 못했다"


def test_settings_round_trip(app, tmp_path):
    app.vars["dep"].set("동대구")
    app.vars["interval"].set("30")

    app._save_settings()
    app.vars["dep"].set("바뀐값")
    app._restore_settings()

    assert app.vars["dep"].get() == "동대구"
    assert app.vars["interval"].get() == "30"
