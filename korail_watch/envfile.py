"""`.env` 읽기/쓰기. 의존성 없이 필요한 만큼만.

토큰은 만료되면 갱신해서 다시 저장해야 하므로 쓰기도 필요하다.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_PATH = Path(".env")


def load_dotenv(path: Path | str = ENV_PATH) -> None:
    """`.env` 를 환경변수로 읽는다. 이미 설정된 값은 덮어쓰지 않는다."""
    path = Path(path)
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def upsert_env(path: Path | str, values: dict[str, str]) -> None:
    """키를 갱신하거나 없으면 추가한다. 주석 등 다른 줄은 건드리지 않는다."""
    path = Path(path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    out = []
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{key}={value}" for key, value in remaining.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    # 토큰이 들어가므로 본인만 읽게 한다.
    try:
        path.chmod(0o600)
    except OSError:
        pass
