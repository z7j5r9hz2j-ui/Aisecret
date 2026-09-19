"""HAR 스크러버. 비밀번호가 새어나가면 안 되므로 꼼꼼히 본다."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scrub_har import REDACTED, main, scrub_har, scrub_text  # noqa: E402


def entry(url, *, method="POST", post=None, headers=None, response_text=None, mime="application/json"):
    return {
        "request": {
            "method": method,
            "url": url,
            "headers": headers or [],
            "queryString": [],
            "cookies": [],
            **({"postData": post} if post else {}),
        },
        "response": {
            "status": 200,
            "headers": [],
            "cookies": [],
            "content": {"mimeType": mime, "size": len(response_text or ""),
                        "text": response_text} if response_text else {"mimeType": mime},
        },
    }


def har(*entries):
    return {"log": {"version": "1.2", "entries": list(entries)}}


def test_credentials_in_json_body_are_removed():
    body = json.dumps({"userId": "hong", "password": "s3cret!", "txtPwd": "abcd",
                       "depPlaceNm": "서울"})
    data, _ = scrub_har(har(entry(
        "https://www.korail.com/login",
        post={"mimeType": "application/json", "text": body},
    )))

    text = data["log"]["entries"][0]["request"]["postData"]["text"]
    parsed = json.loads(text)

    assert "s3cret!" not in text and "abcd" not in text and "hong" not in text
    assert parsed["password"] == REDACTED
    assert parsed["txtPwd"] == REDACTED
    assert parsed["userId"] == REDACTED, "로그인 아이디도 값은 지운다"
    assert parsed["depPlaceNm"] == "서울", "역명은 남아야 한다"


def test_field_names_survive_so_the_spec_can_be_built():
    body = json.dumps({"txtMember": "hong", "txtPwd": "pw"})
    data, _ = scrub_har(har(entry(
        "https://www.korail.com/login",
        post={"mimeType": "application/json", "text": body},
    )))

    text = data["log"]["entries"][0]["request"]["postData"]["text"]

    assert "txtMember" in text and "txtPwd" in text


def test_urlencoded_body_is_scrubbed():
    data, _ = scrub_har(har(entry(
        "https://www.korail.com/login",
        post={"mimeType": "application/x-www-form-urlencoded",
              "text": "txtMember=hong&txtPwd=s3cret&dep=%EC%84%9C%EC%9A%B8"},
    )))

    text = data["log"]["entries"][0]["request"]["postData"]["text"]

    assert "s3cret" not in text
    assert "txtPwd=" in text
    assert "dep=%EC%84%9C%EC%9A%B8" in text, "예매 정보는 남아야 한다"


def test_form_params_list_is_scrubbed():
    data, _ = scrub_har(har(entry(
        "https://www.korail.com/login",
        post={"mimeType": "application/x-www-form-urlencoded",
              "params": [{"name": "txtMember", "value": "hong"},
                         {"name": "txtPwd", "value": "s3cret"},
                         {"name": "srchDvCd", "value": "2"}]},
    )))

    params = data["log"]["entries"][0]["request"]["postData"]["params"]

    assert [p["name"] for p in params] == ["txtMember", "txtPwd", "srchDvCd"], \
        "필드 이름은 전부 남아야 스펙을 만들 수 있다"
    assert params[0]["value"] == REDACTED
    assert params[1]["value"] == REDACTED
    assert params[2]["value"] == "2", "예매 파라미터는 남아야 한다"


def test_cookie_and_auth_headers_are_removed():
    data, _ = scrub_har(har(entry(
        "https://www.korail.com/search",
        headers=[{"name": "Cookie", "value": "JSESSIONID=abc123"},
                 {"name": "Authorization", "value": "Bearer tok"},
                 {"name": "User-Agent", "value": "Mozilla/5.0"}],
    )))

    headers = {h["name"]: h["value"] for h in data["log"]["entries"][0]["request"]["headers"]}

    assert headers["Cookie"] == REDACTED
    assert headers["Authorization"] == REDACTED
    assert headers["User-Agent"] == "Mozilla/5.0", "User-Agent 는 스펙에 필요하다"


def test_personal_info_in_response_is_removed():
    body = json.dumps({"data": {"trainList": [{"trainNo": "101", "generalSeat": "예약가능"}],
                                "memberPhone": "010-1234-5678",
                                "memberName": "홍길동",
                                "custNo": "1234567"}}, ensure_ascii=False)
    data, _ = scrub_har(har(entry("https://www.korail.com/search", response_text=body)))

    text = data["log"]["entries"][0]["response"]["content"]["text"]

    assert "010-1234-5678" not in text
    assert "홍길동" not in text, "이름이 남으면 안 된다"
    assert "1234567" not in text
    assert "예약가능" in text, "좌석 상태는 남아야 한다"
    assert "trainNo" in text


def test_train_and_station_names_are_not_mistaken_for_personal_names():
    """depPlaceNm, trnClsfNm 처럼 Nm 으로 끝나는 열차 정보는 지우면 안 된다."""
    body = json.dumps({"trainList": [
        {"trnClsfNm": "KTX", "depPlaceNm": "서울", "arvPlaceNm": "부산", "trnNo": "101"}
    ]}, ensure_ascii=False)
    data, _ = scrub_har(har(entry("https://www.korail.com/search", response_text=body)))

    text = data["log"]["entries"][0]["response"]["content"]["text"]

    for needed in ("KTX", "서울", "부산", "101"):
        assert needed in text, f"{needed} 가 사라졌다"


def test_nested_secrets_are_reached():
    body = json.dumps({"a": {"b": [{"accessToken": "xyz"}]}})

    assert "xyz" not in scrub_text(body, "application/json", _Stats())


class _Stats:
    redactions = 0


def test_static_assets_are_dropped():
    data, stats = scrub_har(har(
        entry("https://www.korail.com/img/logo.png", method="GET", mime="image/png"),
        entry("https://www.korail.com/css/main.css", method="GET", mime="text/css"),
        entry("https://www.korail.com/api/search"),
    ))

    urls = [e["request"]["url"] for e in data["log"]["entries"]]

    assert urls == ["https://www.korail.com/api/search"]
    assert stats.kept == 1 and stats.dropped == 2


def test_third_party_hosts_are_dropped_by_default():
    data, _ = scrub_har(har(
        entry("https://ads.example.com/track"),
        entry("https://www.korail.com/api/search"),
    ))

    assert len(data["log"]["entries"]) == 1


def test_all_hosts_keeps_everything():
    data, _ = scrub_har(har(
        entry("https://ads.example.com/track"),
        entry("https://www.korail.com/api/search"),
    ), host="")

    assert len(data["log"]["entries"]) == 2


def test_cli_writes_scrubbed_file_and_reports(tmp_path, capsys):
    source = tmp_path / "capture.har"
    source.write_text(json.dumps(har(entry(
        "https://www.korail.com/login",
        post={"mimeType": "application/json",
              "text": json.dumps({"id": "hong", "password": "s3cret"})},
    ))), encoding="utf-8")

    code = main([str(source)])
    out = capsys.readouterr().out
    written = (tmp_path / "capture.scrubbed.har").read_text(encoding="utf-8")

    assert code == 0
    assert "s3cret" not in written
    assert "남긴 요청 1개" in out
    assert "/login" in out, "무엇을 보내는지 목록으로 보여줘야 한다"


def test_cli_reports_missing_file(tmp_path, capsys):
    assert main([str(tmp_path / "absent.har")]) == 1
    assert "파일이 없습니다" in capsys.readouterr().err


def test_cli_warns_when_nothing_matched(tmp_path, capsys):
    source = tmp_path / "capture.har"
    source.write_text(json.dumps(har(entry("https://other.com/x"))), encoding="utf-8")

    main([str(source)])

    assert "남은 요청이 없습니다" in capsys.readouterr().out
