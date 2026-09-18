"""텔레그램 설정 도우미. 실제 네트워크 없이 MockTransport 로 검증한다."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from telegram_setup import (  # noqa: E402
    SetupError,
    find_chats,
    main,
    resolve_chat_id,
    send_test,
    upsert_env,
    verify_token,
)

TOKEN = "123456:FAKE"


def api(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def ok(result):
    return httpx.Response(200, json={"ok": True, "result": result})


def message_update(chat_id, **chat):
    return {"update_id": 1, "message": {"chat": {"id": chat_id, **chat}}}


def test_verify_token_reports_bot_name():
    client = api(lambda r: ok({"username": "my_korail_bot", "first_name": "코레일알림"}))

    assert verify_token(client, TOKEN) == "@my_korail_bot (코레일알림)"


def test_bad_token_explains_how_to_fix():
    client = api(lambda r: httpx.Response(401, json={"ok": False}))

    with pytest.raises(SetupError, match="BotFather"):
        verify_token(client, TOKEN)


def test_telegram_error_description_is_surfaced():
    client = api(lambda r: httpx.Response(200, json={"ok": False, "description": "chat not found"}))

    with pytest.raises(SetupError, match="chat not found"):
        verify_token(client, TOKEN)


def test_network_failure_is_explained():
    def handler(request):
        raise httpx.ConnectError("no route")

    with pytest.raises(SetupError, match="연결하지 못했습니다"):
        verify_token(api(handler), TOKEN)


def test_find_chats_deduplicates_and_labels():
    updates = [
        message_update(555, first_name="길동", last_name="홍"),
        message_update(555, first_name="길동"),
        message_update(-100, title="가족방"),
    ]
    client = api(lambda r: ok(updates))

    assert find_chats(client, TOKEN) == [("-100", "가족방"), ("555", "길동 홍")]


def test_find_chats_reads_channel_posts_too():
    client = api(lambda r: ok([{"update_id": 2, "channel_post": {"chat": {"id": 7, "title": "공지"}}}]))

    assert find_chats(client, TOKEN) == [("7", "공지")]


def test_resolve_prefers_explicit_chat_id():
    def handler(request):
        raise AssertionError("chat_id 가 주어지면 조회하지 않아야 한다")

    assert resolve_chat_id(api(handler), TOKEN, "999") == "999"


def test_no_conversation_tells_user_to_message_the_bot_first():
    client = api(lambda r: ok([]))

    with pytest.raises(SetupError, match="먼저 보내야"):
        resolve_chat_id(client, TOKEN, "")


def test_multiple_chats_lists_them_and_asks_to_choose(capsys):
    client = api(lambda r: ok([message_update(1, first_name="A"), message_update(2, first_name="B")]))

    with pytest.raises(SetupError, match="chat_id 를 지정"):
        resolve_chat_id(client, TOKEN, "")

    out = capsys.readouterr().out
    assert "1  A" in out and "2  B" in out


def test_send_test_posts_to_the_right_chat():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return ok({"message_id": 1})

    send_test(api(handler), TOKEN, "555")

    assert f"bot{TOKEN}/sendMessage" in seen["url"]
    assert "chat_id=555" in seen["url"]


def test_upsert_env_updates_without_touching_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# 주석\nKORAIL_ID=hong\nTELEGRAM_BOT_TOKEN=old\n", encoding="utf-8"
    )

    upsert_env(env, {"TELEGRAM_BOT_TOKEN": "new", "TELEGRAM_CHAT_ID": "555"})
    lines = env.read_text(encoding="utf-8").splitlines()

    assert "# 주석" in lines
    assert "KORAIL_ID=hong" in lines
    assert "TELEGRAM_BOT_TOKEN=new" in lines
    assert "TELEGRAM_CHAT_ID=555" in lines
    assert sum(1 for line in lines if line.startswith("TELEGRAM_BOT_TOKEN")) == 1


def test_upsert_env_creates_file_when_missing(tmp_path):
    env = tmp_path / ".env"

    upsert_env(env, {"TELEGRAM_CHAT_ID": "7"})

    assert env.read_text(encoding="utf-8") == "TELEGRAM_CHAT_ID=7\n"


def test_main_happy_path_saves_and_reports(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    calls = []

    def handler(request):
        calls.append(request.url.path)
        if request.url.path.endswith("getMe"):
            return ok({"username": "korail_bot", "first_name": "알림"})
        if request.url.path.endswith("getUpdates"):
            return ok([message_update(555, first_name="길동")])
        return ok({"message_id": 1})

    code = main(["--token", TOKEN], client=api(handler))
    out = capsys.readouterr().out
    env = (tmp_path / ".env").read_text(encoding="utf-8")

    assert code == 0
    assert "@korail_bot" in out
    assert "chat_id 를 찾았습니다: 555" in out
    assert "TELEGRAM_CHAT_ID=555" in env
    assert any(p.endswith("sendMessage") for p in calls)


def test_main_without_token_prints_botfather_steps(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)

    code = main([])

    assert code == 2
    assert "@BotFather" in capsys.readouterr().err


def test_main_no_save_leaves_env_alone(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def handler(request):
        if request.url.path.endswith("getMe"):
            return ok({"username": "b", "first_name": "b"})
        return ok({"message_id": 1})

    code = main(["--token", TOKEN, "--chat-id", "5", "--no-save"], client=api(handler))

    assert code == 0
    assert not (tmp_path / ".env").exists()


def test_main_reports_failure_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    client = api(lambda r: httpx.Response(401, json={"ok": False}))

    code = main(["--token", "bad"], client=client)

    assert code == 1
    assert "BotFather" in capsys.readouterr().err
