# korail-watch

코레일+ 열차의 빈자리를 저빈도로 감시해 알려주고, 원하면 **좌석 선점까지만** 수행하는 도구.
결제는 하지 않는다. 선점된 좌석은 코레일+ 앱에서 직접 결제해야 하며, 기한(약 20분)이
지나면 자동 취소되어 다른 사람에게 돌아간다.

## 왜 이 형태인가

- **결제 자동화 제외.** 코레일은 2025년 7월 매크로 탐지 솔루션 도입 이후 하루 평균 1.6만 건을
  차단하고 있고, 명절 승차권 매크로 예매자가 컴퓨터등장애업무방해로 검찰에 송치된 사례가 있다.
  대량 선점·재판매가 문제의 핵심이므로, 이 도구는 1건 감시·1건 선점에서 멈춘다.
- **차단 신호를 만나면 우회하지 않고 중단한다.** 401/403/429나 응답 본문의 매크로 탐지 문구를
  만나면 즉시 종료한다(`BlockedError`). IP 로테이션, 기기 지문 위조, CAPTCHA 우회는 넣지 않았고
  넣을 계획도 없다.
- **조회 간격 하한 30초.** `PollerConfig`가 그 아래 값을 거부한다. 기본값은 45초 ± 40% 지터.

## 먼저 확인할 것

이 도구를 돌리기 전에 **코레일+의 `예약대기`** 를 신청해두는 편이 대체로 낫다. 매진 열차에 대해
출발 2일 전까지 신청해두면 반환석 발생 시 자동으로 예약되고 SMS가 온다. 공식 기능이 하는 일을
굳이 폴링으로 대신할 이유는 없다.

## 1단계: API 파악 (직접 해야 하는 부분)

`코레일+`는 2026년 8월 출시된 통합 앱이라 공개된 API 래퍼가 없다. 기존 오픈소스
(`carpedm20/korail2`, `ryanking13/SRT`, `lapis42/srtgo`)는 전부 구 letskorail·SRT 엔드포인트
기준이고 모두 아카이브·방치 상태다. 그래서 이 저장소에는 URL이 하드코딩돼 있지 않다.
직접 캡처한 값을 `endpoints.json`에 채워야 동작한다.

1. Android 에뮬레이터(예: Android Studio AVD, Google Play 이미지가 아닌 것)에 코레일+ 설치
2. mitmproxy 실행 → 에뮬레이터 Wi-Fi 프록시를 호스트:8080으로 설정
3. mitmproxy CA 인증서를 **시스템 인증서**로 설치 (사용자 인증서는 앱이 무시할 수 있음)
4. 앱에서 로그인 1회, 열차 조회 1회, (선택) 좌석 선점 1회를 수행하고 흐름을 기록
5. 각 요청의 URL·헤더·본문 필드명과 응답 JSON 구조를 `endpoints.json`에 옮겨 적는다

인증서 피닝에 막힐 수 있다. 그 경우는 여기서 멈추고 알림 없이 예약대기 기능을 쓰는 편을 권한다.
피닝 우회는 이 저장소의 범위 밖이다.

## 2단계: 설정

```bash
pip install -e ".[dev]"
cp endpoints.example.json endpoints.json   # 캡처한 값으로 채우기
cp .env.example .env                       # KORAIL_ID / KORAIL_PW / 텔레그램 토큰
```

`.env`와 `endpoints.json`은 `.gitignore`에 있다. 자격증명을 커밋하지 말 것.

### endpoints.json 구조

| 키 | 설명 |
|---|---|
| `base_url` | 캡처한 API 호스트 |
| `headers` | 앱의 User-Agent 등 공통 헤더 |
| `login.json` | 로그인 요청 본문. `{login_id}` `{password}` 치환 |
| `login.token_path` | 응답에서 토큰을 꺼낼 점 경로 (`data.accessToken`) |
| `search.json` | 조회 요청 본문. `{dep_station}` `{arr_station}` `{date}` `{time}` `{passengers}` 치환 |
| `search.list_path` | 응답에서 열차 배열 경로 (`data.trainList`) |
| `search.fields` | 열차 1건의 필드명 매핑 |
| `search.seat_fields` | 좌석 종류 → 잔여석 필드명. 숫자면 그대로, `예약가능` 같은 상태 문자열이면 요청 인원만큼으로 계산 |
| `reserve.*` | 좌석 선점. 없으면 알림 전용으로 동작 |

치환 문자열이 값 전체면 타입이 보존된다(`"{passengers}"` → `2`).

## 3단계: 실행

```bash
# 알림만 (기본)
korail-watch --dep 서울 --arr 부산 --date 2026-09-20 --time 0900-1330 --seats 일반실 --passengers 2

# 좌석 선점까지 (결제는 앱에서)
korail-watch --dep 서울 --arr 부산 --date 2026-09-20 --reserve

# 스펙 없이 알림 경로만 점검
korail-watch --dep 서울 --arr 부산 --date 2026-09-20 --demo
```

주요 옵션: `--interval`(기본 45초, 최소 30), `--max-hours`(기본 6), `--trains KTX,SRT`,
`--spec`(기본 `endpoints.json`).

## 종료 사유

| 사유 | 의미 |
|---|---|
| `좌석 선점 완료` | 예약번호 발급. 앱에서 결제할 것 |
| `최대 실행 시간 도달` | 정상 종료 |
| `차단 신호 감지 - 중단` | 403/429 또는 탐지 문구. **재실행하지 말고 원인을 볼 것** |
| `연속 오류 한도 초과` | 5회 연속 실패(지수 백오프 30초→최대 10분) |
| `복구 불가 오류` | 로그인 실패 또는 스펙 오류 |

## 구조

| 파일 | 역할 |
|---|---|
| `korail_watch/models.py` | `Train`, `WatchCriteria`(매칭 규칙), `Reservation` |
| `korail_watch/api.py` | 스펙 구동 HTTP 클라이언트. 결제 메서드 없음 |
| `korail_watch/poller.py` | 지터 폴링, 백오프, 차단 시 중단, 알림 쿨다운 |
| `korail_watch/notify.py` | 콘솔 / 텔레그램 |
| `korail_watch/sources.py` | `TrainSource` 프로토콜과 테스트용 가짜 소스 |
| `korail_watch/cli.py` | 인자 파싱, 조립 |

```bash
pytest    # 58 tests
```

네트워크 없이 전부 돈다. HTTP 계층은 `httpx.MockTransport`로, 폴링 루프는 가상 시계로 검증한다.

## 하지 않는 것

암표 거래, 대량 선점, 탐지 회피, 결제 자동화. 상업적 이용도 대상이 아니다.
