"""korail-watch 데스크톱 GUI (tkinter).

폴러는 워커 스레드에서 돌고, 로그·상태·알림은 큐를 통해 UI 스레드로 전달된다.
tkinter 위젯은 UI 스레드에서만 건드린다.
"""

from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time as _time
from datetime import date
from pathlib import Path
from typing import Any

from .api import EndpointSpec, KorailPlusClient
from .cadence import DEFAULT_WINDOWS
from .envfile import load_dotenv
from .errors import KorailWatchError
from .forms import DEFAULTS, SEAT_CHOICES, FormError, RunSpec, build_run_spec
from .models import Train
from .notify import MultiNotifier, build_notifiers
from .poller import Poller, PollProgress, StopReason
from .sources import FakeTrainSource

SETTINGS_FILE = Path(".korail-watch-gui.json")
#: 저장하지 않는 칸. 자격증명은 .env 로만 다룬다.
UNSAVED_KEYS = {"password"}


class QueueNotifier:
    """Notifier 프로토콜 구현. 메시지를 UI 큐로 넘긴다."""

    def __init__(self, outbox: queue.Queue) -> None:
        self._outbox = outbox

    def send(self, title: str, body: str) -> None:
        self._outbox.put(("alert", title, body))


def demo_source(spec: RunSpec) -> FakeTrainSource:
    """스펙 없이 동작을 확인할 때 쓰는 가짜 소스."""
    hit = Train(
        train_no="101",
        train_name="KTX",
        dep_station=spec.criteria.dep_station,
        arr_station=spec.criteria.arr_station,
        dep_time=spec.criteria.time_from,
        arr_time=spec.criteria.time_to,
        seats={spec.criteria.seat_types[0]: max(spec.criteria.passengers, 1)},
    )
    return FakeTrainSource([[], [], [hit]])


def run_watch(
    spec: RunSpec,
    outbox: queue.Queue,
    stop_event: threading.Event,
    *,
    sleep=None,
) -> None:
    """워커 스레드 본체. 예외는 전부 큐로 돌려보낸다.

    기본 sleep 은 stop_event.wait 이다. 긴 대기 중에도 정지 버튼이 즉시 먹히게
    하려는 것이고, sleep 인자는 테스트에서 실제로 잠들지 않게 할 때만 쓴다.
    """
    notifiers: list[Any] = build_notifiers(dict(os.environ), extra=[QueueNotifier(outbox)])
    extra_channels = [type(n).__name__.replace("Notifier", "") for n in notifiers[1:]]
    if extra_channels:
        outbox.put(("log", f"알림 채널: {', '.join(extra_channels)} 로도 보냅니다."))

    client = None
    try:
        if spec.demo:
            source: Any = demo_source(spec)
            outbox.put(("log", "데모 모드: 가짜 응답으로 동작만 확인합니다."))
        else:
            endpoint_spec = EndpointSpec.load(spec.spec_path)
            client = KorailPlusClient(
                endpoint_spec,
                login_id=os.getenv("KORAIL_ID", ""),
                password=os.getenv("KORAIL_PW", ""),
            )
            source = client

        poller = Poller(
            source,
            spec.criteria,
            MultiNotifier(*notifiers),
            spec.config,
            reserve=spec.reserve,
            sleep=sleep or stop_event.wait,
            stop_event=stop_event,
            on_poll=lambda progress: outbox.put(("progress", progress)),
        )
        result = poller.run()
        outbox.put(("done", result))
    except KorailWatchError as exc:
        outbox.put(("error", str(exc)))
    except Exception as exc:  # 워커가 조용히 죽는 것보다 화면에 띄우는 게 낫다
        outbox.put(("error", f"예상치 못한 오류: {exc!r}"))
    finally:
        if client is not None:
            client.close()


def _require_tk():
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - 환경 의존
        raise SystemExit(
            "tkinter 를 찾을 수 없습니다.\n"
            "  Ubuntu/Debian: sudo apt install python3-tk\n"
            "  macOS(homebrew): brew install python-tk\n"
            "  Windows: 파이썬 설치 시 'tcl/tk' 옵션 포함\n"
            "GUI 없이 쓰려면 korail-watch 명령을 사용하세요."
        ) from exc
    return tk, ttk, filedialog, messagebox


class App:
    def __init__(self, root, *, tk, ttk, filedialog, messagebox) -> None:
        self.root = root
        self.tk, self.ttk = tk, ttk
        self.filedialog, self.messagebox = filedialog, messagebox

        self.outbox: queue.Queue = queue.Queue()
        self.stop_event = threading.Event()
        self.worker: threading.Thread | None = None
        self.vars: dict[str, Any] = {}

        root.title("korail-watch — 코레일+ 빈자리 감시")
        root.minsize(620, 640)
        self._build()
        self._restore_settings()
        self._report_credentials()
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        root.after(150, self._drain)

    # -- 화면 구성 ----------------------------------------------------------

    def _build(self) -> None:
        tk, ttk = self.tk, self.ttk
        pad = {"padx": 6, "pady": 3}
        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        route = ttk.LabelFrame(outer, text="경로", padding=8)
        route.pack(fill="x")
        self._entry(route, "dep", "출발역", 0, 0, width=12)
        self._entry(route, "arr", "도착역", 0, 2, width=12)
        self._entry(route, "date", "출발일", 1, 0, width=12)
        self._entry(route, "time", "시간대", 1, 2, width=12)

        self.vars["seats"] = tk.StringVar(value=DEFAULTS["seats"])
        ttk.Label(route, text="좌석").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(
            route, textvariable=self.vars["seats"], values=list(SEAT_CHOICES),
            width=10, state="readonly",
        ).grid(row=2, column=1, sticky="w", **pad)
        self._entry(route, "passengers", "인원", 2, 2, width=5)
        self._entry(route, "trains", "열차명(선택)", 3, 0, width=28, span=3)

        how = ttk.LabelFrame(outer, text="조회 방식", padding=8)
        how.pack(fill="x", pady=(8, 0))

        numbers = ttk.Frame(how)
        numbers.pack(fill="x")
        self._entry(numbers, "interval", "기본 간격(초)", 0, 0, width=7)
        self._entry(numbers, "max_hours", "최대 실행(시간)", 0, 2, width=7)
        self._entry(numbers, "max_requests", "요청 상한", 0, 4, width=7)

        self.vars["use_windows"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            how, text="취소표 집중 구간 사용", variable=self.vars["use_windows"],
            command=self._toggle_windows,
        ).pack(anchor="w", pady=(6, 0))
        self.vars["windows"] = tk.StringVar(value=DEFAULT_WINDOWS)
        self.windows_entry = ttk.Entry(how, textvariable=self.vars["windows"])
        self.windows_entry.pack(fill="x", pady=2)
        ttk.Label(
            how,
            text="HHMM-HHMM@초 (자정 넘김 가능). 23:40~00:25 는 예약대기 미결제분이 풀리는 구간.",
            foreground="#666",
            wraplength=560,
        ).pack(anchor="w")

        self.vars["reserve"] = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            how, text="좌석 선점까지 (결제는 코레일+ 앱에서 직접)",
            variable=self.vars["reserve"],
        ).pack(anchor="w", pady=(6, 0))

        spec_row = ttk.Frame(how)
        spec_row.pack(fill="x", pady=2)
        ttk.Label(spec_row, text="스펙 파일").pack(side="left", padx=(0, 6))
        self.vars["spec_path"] = tk.StringVar(value=DEFAULTS["spec_path"])
        ttk.Entry(spec_row, textvariable=self.vars["spec_path"]).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(spec_row, text="찾기", command=self._pick_spec, width=6).pack(
            side="left", padx=(6, 0)
        )

        self.vars["demo"] = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            how, text="데모 모드 (스펙 없이 동작만 점검)", variable=self.vars["demo"]
        ).pack(anchor="w")

        buttons = ttk.Frame(outer)
        buttons.pack(fill="x", pady=(10, 4))
        self.start_btn = ttk.Button(buttons, text="감시 시작", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(
            buttons, text="정지", command=self._stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=6)

        self.status = tk.StringVar(value="대기 중")
        self.status_label = ttk.Label(outer, textvariable=self.status, anchor="w")
        self.status_label.pack(fill="x")

        log_frame = ttk.LabelFrame(outer, text="로그", padding=4)
        log_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.log_text = tk.Text(log_frame, height=14, wrap="word", state="disabled")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log_text.tag_configure("alert", foreground="#0a7", font=("TkDefaultFont", 10, "bold"))
        self.log_text.tag_configure("error", foreground="#c33")

    def _entry(self, parent, key, label, row, col, *, width=12, span=1):
        pad = {"padx": 6, "pady": 3}
        self.ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", **pad)
        self.vars[key] = self.tk.StringVar(value=DEFAULTS.get(key, ""))
        entry = self.ttk.Entry(parent, textvariable=self.vars[key], width=width)
        entry.grid(row=row, column=col + 1, columnspan=span, sticky="w", **pad)
        return entry

    # -- 동작 --------------------------------------------------------------

    def _toggle_windows(self) -> None:
        state = "normal" if self.vars["use_windows"].get() else "disabled"
        self.windows_entry.configure(state=state)

    def _pick_spec(self) -> None:
        chosen = self.filedialog.askopenfilename(
            title="endpoints.json 선택",
            filetypes=[("JSON", "*.json"), ("모든 파일", "*.*")],
        )
        if chosen:
            self.vars["spec_path"].set(chosen)

    def form_values(self) -> dict[str, Any]:
        return {key: var.get() for key, var in self.vars.items()}

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            spec = build_run_spec(self.form_values())
        except FormError as exc:
            self.messagebox.showerror("입력 오류", exc.message)
            return

        self._save_settings()
        self.stop_event = threading.Event()
        self.outbox = queue.Queue()
        self.log(
            f"감시 시작: {spec.criteria.dep_station} → {spec.criteria.arr_station} "
            f"{spec.criteria.travel_date:%Y-%m-%d} "
            f"{spec.criteria.time_from:%H:%M}~{spec.criteria.time_to:%H:%M} / "
            f"{', '.join(spec.criteria.seat_types)} {spec.criteria.passengers}명"
        )
        self.log(f"조회: {spec.config.cadence.describe()} / 요청 상한 {spec.config.max_requests}회")
        if not spec.reserve:
            self.log("알림 전용입니다. 취소표를 실제로 잡으려면 '좌석 선점까지'를 켜세요.")

        self.worker = threading.Thread(
            target=run_watch, args=(spec, self.outbox, self.stop_event), daemon=True
        )
        self.worker.start()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status.set("조회 중…")

    def _stop(self) -> None:
        self.stop_event.set()
        self.status.set("정지 요청… 현재 조회가 끝나면 멈춥니다")
        self.stop_btn.configure(state="disabled")

    def _finish(self, message: str) -> None:
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.status.set(message)

    def log(self, text: str, tag: str = "") -> None:
        stamp = _time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{stamp}] {text}\n", tag or ())
        if int(self.log_text.index("end-1c").split(".")[0]) > 500:
            self.log_text.delete("1.0", "100.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _report_credentials(self) -> None:
        if os.getenv("KAKAO_ACCESS_TOKEN"):
            self.log("카카오톡 알림이 설정되어 있습니다.")
        elif os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"):
            self.log("텔레그램 알림이 설정되어 있습니다.")
        if os.getenv("KORAIL_ID") and os.getenv("KORAIL_PW"):
            self.log("자격증명을 .env 에서 읽었습니다.")
        else:
            self.log(".env 에 KORAIL_ID / KORAIL_PW 가 없습니다. 데모 모드로만 동작합니다.")

    # -- 큐 처리 -----------------------------------------------------------

    def _drain(self) -> None:
        try:
            while True:
                self._handle(self.outbox.get_nowait())
        except queue.Empty:
            pass
        self.root.after(150, self._drain)

    def _handle(self, message: tuple) -> None:
        kind = message[0]
        if kind == "log":
            self.log(message[1])
        elif kind == "alert":
            self._handle_alert(message[1], message[2])
        elif kind == "progress":
            self._handle_progress(message[1])
        elif kind == "error":
            self.log(message[1], "error")
            self._finish("오류로 중단")
            self.messagebox.showerror("오류", message[1])
        elif kind == "done":
            result = message[1]
            self.log(
                f"종료: {result.reason.value} "
                f"(조회 {result.polls}회, 매치 {len(result.matches)}건)"
            )
            if result.detail:
                self.log(result.detail)
            self._finish(result.reason.value)
            if result.reason is StopReason.BLOCKED:
                self.messagebox.showwarning(
                    "차단 신호",
                    "차단 또는 탐지 신호를 받아 중단했습니다.\n"
                    "바로 다시 실행하지 말고 간격을 늘리거나 잠시 쉬세요.",
                )

    def _handle_alert(self, title: str, body: str) -> None:
        self.log(f"{title}\n{body}", "alert")
        self.root.bell()
        try:
            self.root.attributes("-topmost", True)
            self.root.after(1500, lambda: self.root.attributes("-topmost", False))
        except self.tk.TclError:  # pragma: no cover - 플랫폼 의존
            pass
        if "선점" in title and "완료" in title:
            self.messagebox.showinfo(f"{title}", f"{body}\n\n지금 코레일+ 앱에서 결제하세요.")

    def _handle_progress(self, progress: PollProgress) -> None:
        self.status.set(
            f"조회 {progress.polls}회 / 열차 {progress.trains_seen}개 / "
            f"매치 {progress.matches}건 / 현재 간격 {progress.interval:g}초 / "
            f"다음 조회 {progress.next_delay:.0f}초 후"
        )

    # -- 설정 저장 ---------------------------------------------------------

    def _save_settings(self) -> None:
        data = {k: v for k, v in self.form_values().items() if k not in UNSAVED_KEYS}
        try:
            SETTINGS_FILE.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            self.log(f"설정 저장 실패: {exc}")

    def _restore_settings(self) -> None:
        if not SETTINGS_FILE.exists():
            self.vars["date"].set(f"{date.today():%Y-%m-%d}")
            self._toggle_windows()
            return
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self.log(f"설정을 읽지 못해 기본값을 씁니다: {exc}")
            data = {}
        for key, value in data.items():
            if key in self.vars and key not in UNSAVED_KEYS:
                self.vars[key].set(value)
        if not self.vars["date"].get():
            self.vars["date"].set(f"{date.today():%Y-%m-%d}")
        self._toggle_windows()

    def _on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not self.messagebox.askokcancel("종료", "감시 중입니다. 정지하고 종료할까요?"):
                return
            self.stop_event.set()
        self._save_settings()
        self.root.destroy()


def main(argv: list[str] | None = None) -> int:
    tk, ttk, filedialog, messagebox = _require_tk()
    load_dotenv(Path(".env"))
    root = tk.Tk()
    App(root, tk=tk, ttk=ttk, filedialog=filedialog, messagebox=messagebox)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
