# pydconfig

Python 애플리케이션의 설정을 이름별로 등록하고, YAML·dotenv·환경변수를 타입이 있는 설정 모델로 읽어 주입하기 위한 라이브러리입니다. 기본 구현은 **pydantic, pydantic-settings, python-dotenv**를 사용합니다.

`ConfigLoader`, `ConfigModel`, `ConfigSnapshot`으로 이름별 등록, nested 모델, 프로파일, 환경변수 바인딩과 YAML 보간을 제공합니다. 배포명과 import 이름은 `pydconfig`이며 표준 CPython **3.10–3.14**를 지원합니다.

## 설치

GitHub Release의 wheel을 설치합니다.

```bash
python -m pip install https://github.com/pydemia/pydconfig/releases/download/v1.0.0/pydconfig-1.0.0-py3-none-any.whl
```

[배포물과 변경 내역](https://github.com/pydemia/pydconfig/releases/tag/v1.0.0). PyPI 업로드 결과는 [release 기록](.worknotes/release-plan.md)에 별도로 기록합니다.

## 문서

| 문서 | 내용 |
| --- | --- |
| [사용자 가이드](docs/user-guide.md) | 빠른 시작, 이름별 등록, nested 모델, 프로파일, 보간, snapshot과 override |
| [설정 규칙](docs/configuration-reference.md) | API 옵션, source 우선순위, boolean·quote, JSON, 타입·파일·오류 계약 |
| [애플리케이션 연동](docs/integration-guide.md) | 생성자 주입, FastAPI app별 설정, 테스트 격리, 기존 설정 이관 |
| [개발·검증·배포 가이드](docs/development.md) | 개발 환경, 계약 시험, wheel/sdist 설치·release 절차 |
| [기획서](.worknotes/product-plan.md) · [설계서](.worknotes/technical-design.md) | 요구사항 R1–R14, 구현 구조, release gate G1–G11 |
| [리뷰 기록](.worknotes/configuration-library-design.md) | 기획·설계 리뷰와 변경 이력 |

## 기능

- 같은 모델을 `primary_db`, `replica_db`처럼 서로 다른 이름·경로로 등록합니다.
- 코드 기본값, 기본·프로파일 YAML, 기본·프로파일 dotenv, OS 환경변수, 명시적 override 순으로 값을 적용합니다.
- `PYDCONFIG_DATABASE__POOL__SIZE`로 `database.pool.size`를 바꿉니다. YAML에 placeholder가 없어도 바인딩합니다.
- YAML `${DB_HOST}`, `${PORT:-5432}`, `$${LITERAL}`을 지원합니다. dotenv와 OS 문자열은 재보간하지 않습니다.
- YAML 최상단 `profile` 또는 `PYDCONFIG_PROFILE`로 `.env.local`, `.env.test`, `.env.stg`, `.env.prd`를 선택합니다. 기본 `.env`도 함께 읽습니다.
- `True/true/TRUE`, `False/false/FALSE`를 같은 boolean으로 읽고, bool·숫자·JSON 환경 입력의 바깥 quote 한 쌍을 처리합니다. 일반 문자열과 비밀값의 quote는 기본 보존합니다.
- 시작 시 모든 등록 설정을 검증합니다. 조회와 override는 원본 snapshot을 보존하며, 출처 진단은 원문 값을 출력하지 않습니다.
- 설정 필드는 환경 설정 데이터로 제한합니다. 클라이언트·서비스 인스턴스 등 임의 Python 객체 타입은 지원하지 않습니다.

낮은 우선순위부터 적용합니다.

```text
코드 기본값 < config.yaml < config.<profile>.yaml
           < .env < .env.<profile> < OS 환경변수 < 명시적 overrides
```

프로파일 선택은 별도 순서입니다.

```text
load(profile=...) > OS PYDCONFIG_PROFILE > .env PYDCONFIG_PROFILE
                  > config.yaml의 최상단 profile > 선택 없음
```

## 빠른 시작

아래 예제는 설정 파일이 없는 경로를 지정하며 `environ={}`는 실제 OS 환경을 제외합니다.

```python
from pydantic import Field
from pydconfig import ConfigLoader, ConfigModel


class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1)


class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    pool: PoolConfig = Field(default_factory=PoolConfig)


loader = ConfigLoader(root_dir="/path/to/empty-config-dir", dotenv=False)
loader.register("primary_db", DatabaseConfig, path="database.primary")
snapshot = loader.load(environ={
    "PYDCONFIG_DATABASE__PRIMARY__HOST": "db.internal",
    "PYDCONFIG_DATABASE__PRIMARY__POOL__SIZE": '"20"',
})

database = snapshot.get("primary_db", DatabaseConfig)
assert database.host == "db.internal"
assert database.pool.size == 20
```

`get()`은 등록 **이름**, 환경변수와 `explain()`은 설정 **경로**를 사용합니다. 전체 파일 예제는 [examples/basic](examples/basic/README.md)에 있습니다.

## 개발과 검증

```bash
git clone https://github.com/pydemia/pydconfig.git
cd pydconfig
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy
```

Windows 명령과 배포물 검증은 [개발 가이드](docs/development.md)에 있습니다. CI는 Ubuntu Python 3.10–3.14, macOS·Windows Python 3.14에서 sdist로 wheel을 만들고 설치한 패키지에 계약 시험과 파일 예제를 실행합니다. 로컬 개발의 editable 설치와 배포물 검증은 구분합니다.

지원 범위는 표준 CPython입니다. PyPy, free-threaded Python, 3.15 이상, 여러 프로파일 동시 병합, 자동 파일 watch와 임의 객체 타입은 지원하지 않습니다. alias와 중첩 container의 범위는 [설정 규칙](docs/configuration-reference.md#지원-타입)에 명시합니다.
