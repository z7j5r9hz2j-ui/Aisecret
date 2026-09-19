#!/usr/bin/env python3
"""HAR 파일에서 비밀번호·쿠키·개인정보를 지우고 필요한 것만 남긴다.

브라우저가 내보낸 HAR 에는 로그인 비밀번호와 세션 쿠키가 평문으로 들어 있다.
그대로 공유하면 계정을 넘기는 것과 같으므로, 값은 지우고 필드 이름과 구조만
남긴다. endpoints.json 을 만드는 데는 이름과 구조만 있으면 된다.

    python3 scripts/scrub_har.py korail.har

결과는 korail.scrubbed.har 로 저장된다.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REDACTED = "<지움>"

#: 값을 지울 필드 이름. 이름 자체는 남는다.
SECRET_KEY = re.compile(
    # 인증 정보
    r"(pass|pwd|passwd|secret|token|auth|session|jsession|cookie|otp|"
    # 신원 정보
    r"jumin|resident|ssn|card|cvc|cvv|birth|phone|mobile|tel|email|"
    # 계정·승객 식별자. 역명(depPlaceNm)·열차명(trnClsfNm)까지 지우지 않도록
    # member/user 같은 접두어가 붙은 것만 고른다.
    r"member|user[_-]?id|userid|cust[_-]?(nm|name|no|id)|"
    r"psg[_-]?(nm|name)|passenger|guest|"
    r"비밀번호|주민|카드|생년|휴대|전화|이메일|성명|이름|고객|승객)",
    re.I,
)

#: 통째로 지울 헤더.
SECRET_HEADER = {
    "cookie", "set-cookie", "authorization", "proxy-authorization",
    "x-auth-token", "x-access-token", "x-csrf-token",
}

#: 남길 필요 없는 정적 리소스.
STATIC_MIME = re.compile(r"(image/|text/css|font/|javascript|text/html;\s*charset=.*icon)", re.I)
STATIC_EXT = re.compile(r"\.(png|jpe?g|gif|svg|webp|ico|css|js|woff2?|ttf|eot|map)(\?|$)", re.I)


class Stats:
    def __init__(self) -> None:
        self.kept = 0
        self.dropped = 0
        self.redactions = 0


def redact_value(stats: Stats) -> str:
    stats.redactions += 1
    return REDACTED


def scrub_json(node: Any, stats: Stats) -> Any:
    """JSON 본문을 훑으며 비밀 키의 값만 바꾼다."""
    if isinstance(node, dict):
        return {
            k: (redact_value(stats) if SECRET_KEY.search(str(k)) else scrub_json(v, stats))
            for k, v in node.items()
        }
    if isinstance(node, list):
        return [scrub_json(v, stats) for v in node]
    return node


def scrub_text(text: str, mime: str, stats: Stats) -> str:
    """본문 문자열을 형식에 맞게 지운다."""
    if not text:
        return text
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            return json.dumps(scrub_json(json.loads(text), stats), ensure_ascii=False)
        except json.JSONDecodeError:
            pass
    if "form-urlencoded" in (mime or "") or ("=" in text and "&" in text):
        parts = []
        for pair in text.split("&"):
            key, sep, _ = pair.partition("=")
            if sep and SECRET_KEY.search(key):
                parts.append(f"{key}={redact_value(stats)}")
            else:
                parts.append(pair)
        return "&".join(parts)
    return text


def scrub_named_values(items: list[dict], stats: Stats) -> list[dict]:
    """{name, value} 목록(쿼리스트링, 폼 파라미터, 쿠키)을 지운다."""
    out = []
    for item in items:
        name = str(item.get("name", ""))
        if SECRET_KEY.search(name):
            item = {**item, "value": redact_value(stats)}
        out.append(item)
    return out


def scrub_headers(headers: list[dict], stats: Stats) -> list[dict]:
    out = []
    for header in headers:
        name = str(header.get("name", "")).lower()
        if name in SECRET_HEADER or SECRET_KEY.search(name):
            header = {**header, "value": redact_value(stats)}
        out.append(header)
    return out


def is_static(entry: dict) -> bool:
    url = entry.get("request", {}).get("url", "")
    mime = entry.get("response", {}).get("content", {}).get("mimeType", "")
    return bool(STATIC_EXT.search(url) or STATIC_MIME.search(mime))


def scrub_entry(entry: dict, stats: Stats) -> dict:
    request = entry.get("request", {})
    response = entry.get("response", {})

    request["headers"] = scrub_headers(request.get("headers", []), stats)
    request["queryString"] = scrub_named_values(request.get("queryString", []), stats)
    request["cookies"] = [
        {**c, "value": redact_value(stats)} for c in request.get("cookies", [])
    ]

    post = request.get("postData")
    if post:
        if post.get("params"):
            post["params"] = scrub_named_values(post["params"], stats)
        if post.get("text"):
            post["text"] = scrub_text(post["text"], post.get("mimeType", ""), stats)

    response["headers"] = scrub_headers(response.get("headers", []), stats)
    response["cookies"] = [
        {**c, "value": redact_value(stats)} for c in response.get("cookies", [])
    ]
    content = response.get("content", {})
    if content.get("text"):
        content["text"] = scrub_text(content["text"], content.get("mimeType", ""), stats)

    return entry


def scrub_har(data: dict, *, host: str = "korail", keep_static: bool = False) -> tuple[dict, Stats]:
    stats = Stats()
    entries = data.get("log", {}).get("entries", [])
    kept = []
    for entry in entries:
        url = entry.get("request", {}).get("url", "")
        if host and host not in url:
            stats.dropped += 1
            continue
        if not keep_static and is_static(entry):
            stats.dropped += 1
            continue
        kept.append(scrub_entry(entry, stats))
        stats.kept += 1
    data.setdefault("log", {})["entries"] = kept
    return data, stats


def summarize(data: dict) -> list[str]:
    """남은 요청을 한 줄씩. 어떤 걸 보냈는지 본인이 확인할 수 있게."""
    lines = []
    for entry in data.get("log", {}).get("entries", []):
        request = entry.get("request", {})
        response = entry.get("response", {})
        size = response.get("content", {}).get("size", 0)
        lines.append(
            f"  {request.get('method', '?'):4} {response.get('status', '?')} "
            f"{size:>8}B  {request.get('url', '')[:96]}"
        )
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="HAR 에서 비밀번호·쿠키·개인정보를 지웁니다."
    )
    parser.add_argument("har", help="브라우저가 내보낸 .har 파일")
    parser.add_argument("-o", "--out", help="저장 경로 (기본: <이름>.scrubbed.har)")
    parser.add_argument(
        "--host", default="korail", help="이 문자열이 든 요청만 남긴다 (기본: korail)"
    )
    parser.add_argument("--all-hosts", action="store_true", help="호스트로 거르지 않는다")
    parser.add_argument("--keep-static", action="store_true", help="이미지·CSS 도 남긴다")
    args = parser.parse_args(argv)

    source = Path(args.har)
    if not source.exists():
        print(f"파일이 없습니다: {source}", file=sys.stderr)
        return 1
    try:
        data = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"HAR 파싱 실패: {exc}", file=sys.stderr)
        return 1

    data, stats = scrub_har(
        data,
        host="" if args.all_hosts else args.host,
        keep_static=args.keep_static,
    )

    target = Path(args.out) if args.out else source.with_suffix(".scrubbed.har")
    target.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"저장: {target}  ({target.stat().st_size / 1024:.0f} KB)")
    print(f"남긴 요청 {stats.kept}개 / 버린 요청 {stats.dropped}개 / 지운 값 {stats.redactions}개")
    print("\n남은 요청 목록 — 보내기 전에 훑어보세요:")
    print("\n".join(summarize(data)) or "  (없음)")
    if not stats.kept:
        print("\n남은 요청이 없습니다. --host 를 바꾸거나 --all-hosts 로 다시 해보세요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
