import os
from datetime import date

import pytest

from korail_watch.cli import build_parser, load_dotenv, main, parse_date


@pytest.mark.parametrize("value", ["2026-09-20", "20260920"])
def test_parse_date_formats(value):
    assert parse_date(value) == date(2026, 9, 20)


def test_parse_date_without_year_uses_current_year():
    assert parse_date("0920").year == date.today().year


def test_parse_date_rejects_garbage():
    with pytest.raises(Exception):
        parse_date("내일")


def test_parser_requires_route():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--dep", "서울"])


def test_load_dotenv_does_not_override_existing(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text('KORAIL_ID=from_file\nTELEGRAM_CHAT_ID="quoted"\n# 주석\n', encoding="utf-8")
    monkeypatch.setenv("KORAIL_ID", "from_shell")
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    load_dotenv(env)

    assert os.environ["KORAIL_ID"] == "from_shell"
    assert os.environ["TELEGRAM_CHAT_ID"] == "quoted"


def test_load_dotenv_missing_file_is_noop(tmp_path):
    load_dotenv(tmp_path / "absent")


def test_demo_run_completes(capsys):
    code = main(["--dep", "서울", "--arr", "부산", "--date", "2026-09-20", "--demo"])
    out = capsys.readouterr().out

    assert code == 0
    assert "빈자리 발견" in out


def test_bad_time_range_exits_with_usage_error(capsys):
    code = main(["--dep", "서울", "--arr", "부산", "--date", "2026-09-20", "--time", "9-13"])

    assert code == 2
    assert "시간대 형식" in capsys.readouterr().err


def test_missing_spec_file_reports_error(capsys, tmp_path):
    code = main([
        "--dep", "서울", "--arr", "부산", "--date", "2026-09-20",
        "--spec", str(tmp_path / "absent.json"),
    ])

    assert code == 1
    assert "엔드포인트 스펙이 없습니다" in capsys.readouterr().err
