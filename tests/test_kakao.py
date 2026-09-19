"""카카오톡 알림과 설정 흐름. 네트워크 없이 검증한다."""

import json
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from kakao_setup import (  # noqa: E402
    SetupError,
    authorize_url,
    exchange_code,
    main,
    redirect_uri,
)

from korail_watch.envfile import load_dotenv, upsert_env  # noqa: E402
from korail_watch.notify import (  # noqa: E402
    KAKAO_TEXT_LIMIT,
    KakaoNotifier,
    build_notifiers,
)


def api(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


# -- KakaoNotifier ---------------------------------------------------------

def test_sends_text_template_with_bearer_token():
    seen = {}

    def handler(request):
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = request.content.decode()
        return httpx.Response(200, json={"result_code": 0})

    KakaoNotifier("TOK", client=api(handler)).send("빈자리 발견", "KTX 101 서울→부산")

    assert seen["auth"] == "Bearer TOK"
    assert "template_object" in seen["body"]
    assert "KTX+101" in seen["body"] or "KTX%20101" in seen["body"]


def test_long_messages_are_truncated_to_kakao_limit():
    seen = {}

    def handler(request):
        from urllib.parse import parse_qs
        payload = parse_qs(request.content.decode())["template_object"][0]
        seen["text"] = json.loads(payload)["text"]
        return httpx.Response(200, json={})

    KakaoNotifier("TOK", client=api(handler)).send("제목", "본문 " * 200)

    assert len(seen["text"]) <= KAKAO_TEXT_LIMIT
    assert seen["text"].endswith("…")


def test_message_links_to_korail_so_you_can_pay():
    seen = {}

    def handler(request):
        from urllib.parse import parse_qs
        payload = parse_qs(request.content.decode())["template_object"][0]
        seen["link"] = json.loads(payload)["link"]
        return httpx.Response(200, json={})

    KakaoNotifier("TOK", client=api(handler)).send("좌석 선점 완료", "결제하세요")

    assert "korail.com" in seen["link"]["web_url"]


def test_expired_token_is_refreshed_and_message_resent():
    calls = []
    saved = {}

    def handler(request):
        calls.append(str(request.url))
        if "oauth/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "NEW"})
        token = request.headers.get("authorization")
        if token == "Bearer OLD":
            return httpx.Response(401, json={"code": -401})
        return httpx.Response(200, json={"result_code": 0})

    notifier = KakaoNotifier(
        "OLD", "REFRESH", "KEY", client=api(handler),
        on_token_refresh=saved.update,
    )
    notifier.send("빈자리 발견", "KTX 101")

    assert sum("memo/default/send" in c for c in calls) == 2, "갱신 후 다시 보내야 한다"
    assert notifier.access_token == "NEW"
    assert saved == {"KAKAO_ACCESS_TOKEN": "NEW"}


def test_rotated_refresh_token_is_persisted():
    saved = {}

    def handler(request):
        if "oauth/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "NEW", "refresh_token": "NEWREF"})
        return httpx.Response(401 if request.headers["authorization"] == "Bearer OLD" else 200,
                              json={})

    notifier = KakaoNotifier("OLD", "OLDREF", "KEY", client=api(handler),
                             on_token_refresh=saved.update)
    notifier.send("t", "b")

    assert saved["KAKAO_REFRESH_TOKEN"] == "NEWREF"
    assert notifier.refresh_token == "NEWREF"


def test_refresh_without_credentials_warns_once(capsys):
    def handler(request):
        return httpx.Response(401, json={})

    KakaoNotifier("OLD", client=api(handler)).send("t", "b")

    assert "kakao_setup.py" in capsys.readouterr().err


def test_failed_refresh_does_not_raise(capsys):
    def handler(request):
        if "oauth/token" in str(request.url):
            return httpx.Response(400, json={"error": "invalid_grant"})
        return httpx.Response(401, json={})

    KakaoNotifier("OLD", "REF", "KEY", client=api(handler)).send("t", "b")

    assert "다시 인증" in capsys.readouterr().err


def test_network_error_never_stops_the_watch(capsys):
    def handler(request):
        raise httpx.ConnectError("down")

    KakaoNotifier("TOK", client=api(handler)).send("t", "b")

    assert "카카오 전송 오류" in capsys.readouterr().err


def test_empty_access_token_is_rejected():
    with pytest.raises(ValueError):
        KakaoNotifier("")


# -- 채널 선택 --------------------------------------------------------------

def test_build_notifiers_picks_kakao_and_telegram():
    notifiers = build_notifiers({
        "KAKAO_ACCESS_TOKEN": "a",
        "TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "1",
    })

    assert [type(n).__name__ for n in notifiers] == ["KakaoNotifier", "TelegramNotifier"]


def test_build_notifiers_keeps_extra_first():
    class Console:
        def send(self, title, body): ...

    notifiers = build_notifiers({"KAKAO_ACCESS_TOKEN": "a"}, extra=[Console()])

    assert type(notifiers[0]).__name__ == "Console"


def test_build_notifiers_skips_partial_telegram_config():
    assert build_notifiers({"TELEGRAM_BOT_TOKEN": "t"}) == []


# -- 설정 스크립트 ----------------------------------------------------------

def test_authorize_url_requests_talk_message_scope():
    url = authorize_url("KEY", 8910)

    assert "scope=talk_message" in url
    assert "response_type=code" in url
    assert "localhost%3A8910%2Fcallback" in url


def test_exchange_code_returns_tokens():
    def handler(request):
        body = request.content.decode()
        assert "grant_type=authorization_code" in body
        assert "code=CODE" in body
        return httpx.Response(200, json={"access_token": "A", "refresh_token": "R"})

    assert exchange_code(api(handler), "KEY", "CODE", 8910)["access_token"] == "A"


def test_exchange_failure_mentions_redirect_uri():
    def handler(request):
        return httpx.Response(400, json={"error_description": "invalid redirect"})

    with pytest.raises(SetupError, match="Redirect URI"):
        exchange_code(api(handler), "KEY", "CODE", 8910)


def test_main_without_key_prints_console_steps(capsys, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KAKAO_REST_API_KEY", raising=False)

    code = main([])
    err = capsys.readouterr().err

    assert code == 2
    assert "developers.kakao.com" in err
    assert redirect_uri(8910) in err, "등록할 Redirect URI 를 알려줘야 한다"


def test_main_happy_path_saves_tokens_and_sends_test(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for key in ("KAKAO_ACCESS_TOKEN", "KAKAO_REFRESH_TOKEN", "KAKAO_REST_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    opened, sent = [], []

    def handler(request):
        if "oauth/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "A", "refresh_token": "R"})
        sent.append(request.content.decode())
        return httpx.Response(200, json={"result_code": 0})

    code = main(
        ["--key", "KEY"],
        client=api(handler),
        opener=opened.append,
        wait=lambda port, **kw: "CODE",
    )
    env = (tmp_path / ".env").read_text(encoding="utf-8")

    assert code == 0
    assert opened and "kauth.kakao.com" in opened[0]
    assert sent, "테스트 메시지를 보내야 한다"
    assert "KAKAO_ACCESS_TOKEN=A" in env and "KAKAO_REFRESH_TOKEN=R" in env
    assert "두 달" in capsys.readouterr().out, "토큰 만료를 안내해야 한다"


def test_main_reports_denied_consent(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)

    def deny(port, **kw):
        raise SetupError("카카오가 인증을 거부했습니다: access_denied")

    code = main(["--key", "KEY"], client=api(lambda r: httpx.Response(200, json={})),
                opener=lambda url: None, wait=deny)

    assert code == 1
    assert "access_denied" in capsys.readouterr().err


# -- 공용 .env 처리 ---------------------------------------------------------

def test_upsert_env_keeps_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# 주석\nKORAIL_ID=hong\nKAKAO_ACCESS_TOKEN=old\n", encoding="utf-8")

    upsert_env(env, {"KAKAO_ACCESS_TOKEN": "new"})
    text = env.read_text(encoding="utf-8")

    assert "# 주석" in text and "KORAIL_ID=hong" in text
    assert "KAKAO_ACCESS_TOKEN=new" in text and "old" not in text


def test_env_file_is_owner_only(tmp_path):
    env = tmp_path / ".env"

    upsert_env(env, {"KAKAO_ACCESS_TOKEN": "secret"})

    assert oct(env.stat().st_mode)[-3:] == "600", "토큰이 든 파일은 본인만 읽어야 한다"


def test_load_dotenv_does_not_override_shell(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("KAKAO_ACCESS_TOKEN=file\n", encoding="utf-8")
    monkeypatch.setenv("KAKAO_ACCESS_TOKEN", "shell")

    load_dotenv(env)

    import os
    assert os.environ["KAKAO_ACCESS_TOKEN"] == "shell"
