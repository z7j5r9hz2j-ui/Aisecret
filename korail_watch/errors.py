"""폴러가 서로 다르게 대응해야 하는 오류 구분."""


class KorailWatchError(Exception):
    """이 패키지의 최상위 예외."""


class SpecError(KorailWatchError):
    """엔드포인트 스펙 파일이 잘못되었거나 비어 있음."""


class TransientError(KorailWatchError):
    """일시적 오류. 백오프 후 재시도할 가치가 있음."""


class BlockedError(KorailWatchError):
    """차단·탐지 신호. 재시도하지 말고 즉시 중단해야 한다.

    403/429, 매크로 탐지 문구 등이 여기 해당한다. 이걸 재시도로 뚫으려는
    시도는 하지 않는다 - 계정 정지와 업무방해로 가는 지름길이다.
    """


class AuthError(KorailWatchError):
    """로그인 실패. 자격증명 문제이므로 재시도해도 소용없다."""
