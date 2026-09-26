# pydemia-config 기획 및 설계안

작성일: 2026-09-26. 상태: 구현 전 제안. 아래 API와 패키지 구조는 목표 설계이며 현재 사용할 수 있는 기능이 아니다.

## 제품 범위

Python 애플리케이션이 설정을 이름별로 선언하고, YAML·프로파일·환경변수를 일관된 규칙으로 합쳐 검증된 객체로 주입받게 한다. 배포 환경을 바꿀 때 코드를 수정하지 않고, 특정 값이 어디에서 결정됐는지 확인할 수 있어야 한다.

초기 사용 대상은 기존 FastAPI 서비스와 배치·CLI 프로그램이다. 코어는 웹 프레임워크에 의존하지 않는다. 범용 IoC 컨테이너, 서비스 자동 탐색, 커넥션 생성과 수명주기 관리는 범위에서 제외한다.

첫 버전의 기본 선택은 다음과 같다.

| 항목 | 제안 |
| --- | --- |
| 배포명 / import | `pydemia-config` / `pydemia_config` — 배포명 사용 가능 여부는 출시 전 확인 |
| Python | 3.11 이상을 초기 지원 후보로 두고 실제 도입 서비스와 CI에서 확정 |
| 타입 선언·검증 | Pydantic v2의 `BaseModel`을 기반으로 한 `ConfigModel` |
| 주요 입력 | 모델 기본값, YAML, dotenv, 프로세스 환경변수, 명시적 override |
| 프로파일 | 컨텍스트 전체에 하나 적용; `local`, `test`, `stg`, `prd`는 예시이며 사용자 정의 가능 |
| 설정 조회 | 명시적으로 생성한 `ConfigSnapshot`에서 이름·타입으로 조회 |
| 환경 상태 | `.env`를 읽어도 `os.environ`을 수정하지 않음 |
| 변경 | 새 snapshot을 생성하고 재검증; 기존 객체를 암묵적으로 변경하지 않음 |

## 기존 구현에서 이어받을 부분

현재 `pydemia-config`에는 제목만 있는 README가 있다. 아래 근거는 2026-09-26의 로컬 소스를 정적으로 확인한 결과이며 서비스 실행 결과는 아니다. 체크아웃 HEAD는 `pydemia-config: 3476500`, `template-backend: af5722e`, `skax-successionX-backend: 74ddeec1`이다. 관찰 대상은 해당 시점 작업 트리다.

| 현재 구현과 근거 | 라이브러리 설계에 반영할 내용 |
| --- | --- |
| [template-backend 설정](/Users/a09255/git/template-backend/template_backend_sample/mainapp/core/config.py:55)의 `_root_key`로 `database`, `app` 등을 분리 | 명시적인 이름 → 모델 등록 API로 정리 |
| [shared/config.py](/Users/a09255/git/skax-successionX-backend/shared/config.py:21)의 재귀적 YAML 병합 | dictionary 재귀 병합, list·scalar 교체 규칙을 공개 계약으로 고정 |
| [환경변수 치환](/Users/a09255/git/skax-successionX-backend/shared/config.py:32)이 YAML 원문을 바꾼 뒤 파싱 | YAML 파싱 후 값 노드만 치환해 따옴표·개행 등으로 구조가 달라지는 문제 방지 |
| [소스 설정](/Users/a09255/git/skax-successionX-backend/shared/config.py:98)에 `env_file`이 있지만 반환하는 소스 목록에는 `dotenv_settings`가 없음 | dotenv를 명시적으로 로딩 파이프라인에 포함. 별도 외부 로더의 존재 여부와 무관하게 라이브러리 자체 동작 보장 |
| 같은 부분에서 `.env.local`이 있으면 `.env` 대신 선택 | `.env`와 선택한 프로파일 파일을 순서대로 누적 적용 |
| [공통 설정 사용](/Users/a09255/git/skax-successionX-backend/common/mainapp/core/config.py:126)에서 import 시점 객체 생성 | 애플리케이션 시작 시 명시적 로딩, 테스트별 독립 컨텍스트 지원 |
| 일부 하위 클래스가 `AppSettings.model_config.update(...)` 호출 | 부모 클래스 설정 dictionary를 직접 변경하지 않는 모델별 정책 |
| [서비스 설정](/Users/a09255/git/skax-successionX-backend/agentstore/mainapp/core/config.py:25)에 도메인 필드와 환경변수 조회가 혼재 | 도메인 모델은 서비스에 남기고 로딩 엔진만 공통화 |

DB URL 구성, Redis 연결 옵션, 로거 레벨 변경은 각 애플리케이션의 책임으로 남긴다. 라이브러리의 설정 검증은 로거나 외부 연결을 변경하지 않는다.

## 참고할 프레임워크와 채택 범위

요구하신 Spring 방식 중 직접 대응되는 기능은 Spring Boot의 externalized configuration과 `@ConfigurationProperties`다. 여러 설정 소스의 우선순위, 구조화된 객체 바인딩, 검증을 참고한다. Spring의 전체 우선순위나 환경변수 표기법과의 호환성을 목표로 하지는 않는다. [Spring Boot 공식 문서](https://docs.spring.io/spring-boot/reference/features/external-config.html)

Pydantic Settings의 환경변수·dotenv·중첩 필드 처리와 사용자 정의 소스는 Python에서 재사용할 수 있는 기반이다. 다만 이름별 단일 로딩, 프로파일 bootstrap, 치환의 실행 시점과 provenance를 일관되게 제어하기 위해 코어는 독립적인 source pipeline을 갖고 Pydantic의 공개 검증 API를 사용한다. `BaseSettings`를 모델마다 생성해 환경을 반복 로딩하는 방식은 사용하지 않는다. [Pydantic Settings 공식 문서](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)

Dynaconf의 명시적 병합 정책과 OmegaConf의 구조화된 설정·보간 기능도 참고한다. 초기에는 병합 규칙을 단순하게 고정하고 설정 간 참조·표현식은 뒤로 미룬다. 이는 인기 순위를 측정한 판단이 아니라 공식 문서에 있는 기능과 현재 요구사항의 적합성을 기준으로 한 선택이다. [Dynaconf 병합](https://www.dynaconf.com/merging/), [OmegaConf 사용법](https://omegaconf.readthedocs.io/en/latest/usage.html)

## 사용자 경험과 공개 API

### 이름과 경로

`name`은 설정을 조회·주입할 때 사용하는 식별자다. YAML 경로는 기본적으로 name과 같고 필요할 때 `path`로 분리한다. 하나의 모델을 여러 이름에 등록할 수 있다.

```python
from pathlib import Path

from pydantic import Field, SecretStr
from pydemia_config import ConfigLoader, ConfigModel


class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1)
    timeout_seconds: float = Field(default=5.0, gt=0)


class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    username: str = "app"
    password: SecretStr
    pool: PoolConfig = Field(default_factory=PoolConfig)


class AppConfig(ConfigModel):
    name: str = "sample"
    debug: bool = False
    allowed_hosts: tuple[str, ...] = ("localhost",)


loader = ConfigLoader(
    root_dir=Path(__file__).resolve().parent,
    env_prefix="MYAPP_",
)
loader.register("app", AppConfig)
loader.register("database", DatabaseConfig)

# 이 호출에서 파일을 읽고 환경변수를 복사한 뒤 설정을 검증한다.
settings = loader.load()
db = settings.get("database", DatabaseConfig)
app = settings.get("app", AppConfig)

assert db.pool.size >= 1
```

등록만으로 파일을 읽거나 환경을 조회하지 않는다. `load()`가 등록된 모든 모델을 검증하고 성공한 경우에만 snapshot을 반환한다. 라이브러리 import 자체에는 설정 I/O가 없다.

```python
named_loader = ConfigLoader(root_dir=Path.cwd(), env_prefix="MYAPP_")
named_loader.register("primary_db", DatabaseConfig, path="database.primary")
named_loader.register("replica_db", DatabaseConfig, path="database.replica")

# database.primary와 database.replica 구조의 별도 YAML을 사용한다.
named_settings = named_loader.load()
primary = named_settings.get("primary_db", DatabaseConfig)
```

이 경우 환경변수는 name이 아니라 YAML 경로를 따른다. `MYAPP_DATABASE__PRIMARY__HOST`가 `database.primary.host`를 변경한다. 이름 중복, 동일 경로 중복, 등록 경로의 부모·자식 중첩은 초기 버전에서 오류로 처리한다. 같은 타입이 여러 이름에 있을 수 있으므로 타입만으로 대상을 추측하지 않는다.

등록 이름과 경로 segment는 기본적으로 소문자 `snake_case`를 사용한다. 경로 구분자인 `.`과 환경변수 구분자인 `__`를 개별 segment 안에 넣지 않는다. 동적 dictionary key의 대소문자는 보존하며 환경변수 전체 JSON 값으로 전달하도록 한다.

### YAML과 dotenv 예시

```yaml
# config.yaml
profile: local

app:
  name: sample
  debug: false
  allowed_hosts: [localhost]

database:
  host: "${DB_HOST:-localhost}"
  port: 5432
  username: app
  password: "${DB_PASSWORD}"
  pool:
    size: 10
    timeout_seconds: 5.0
```

```yaml
# config.local.yaml
app:
  debug: true
database:
  pool:
    size: 5
```

```dotenv
# .env — 아래 비밀번호는 설명용 값
DB_PASSWORD=example-only
MYAPP_DATABASE__PORT=15432
```

```dotenv
# .env.local
DB_HOST=127.0.0.1
MYAPP_DATABASE__POOL__SIZE=3
```

위 입력만 있으면 profile은 `local`, host는 `127.0.0.1`, port는 `15432`, pool.size는 `3`이다. 프로세스에 `MYAPP_DATABASE__POOL__SIZE=20`이 있으면 `20`을 사용한다.

환경변수 주입은 두 방식으로 구분한다.

| 방식 | 예시 | 용도 |
| --- | --- | --- |
| 경로 자동 바인딩 | `MYAPP_DATABASE__HOST=db.internal` | YAML에 placeholder를 작성하지 않고 필드 override |
| 명시적 보간 | YAML의 `host: "${DB_HOST}"` | 배포 환경에서 이미 쓰는 변수명을 그대로 참조 |

`DB_HOST` 같은 prefix 없는 변수는 placeholder나 명시적 alias로만 사용한다. 시스템의 모든 환경변수를 설정 필드로 가져오지 않는다.

## 설정 우선순위

아래에서 뒤에 있는 값이 앞의 값을 덮어쓴다. 객체를 통째로 교체하는 대신 경로별로 적용한다.

```text
모델 기본값
  < config.yaml
  < config.<profile>.yaml
  < .env에서 바인딩한 값
  < .env.<profile>에서 바인딩한 값
  < 프로세스 환경변수에서 바인딩한 값
  < load(overrides=...)로 전달한 값
```

`overrides`는 일반적인 코드 기본값과 다르다. 호출자가 특정 실행에 명시적으로 전달한 최우선 값이다. 모델 기본값은 계속 최하위에 둔다.

```python
settings = loader.load(
    profile="test",
    overrides={"database": {"pool": {"size": 1}}},
)
```

`profile`은 bootstrap 입력이므로 `overrides`에 넣으면 오류다. override 경로는 조회용 name이 아니라 YAML 경로를 사용한다.

자동 바인딩과 placeholder가 같은 필드를 가리키면 자동 바인딩이 승리한다. 예를 들어 YAML `host: "${DB_HOST}"`와 `.env`의 `MYAPP_DATABASE__HOST=x`가 있으면 최종 host는 `x`다. OS의 `DB_HOST=y`는 YAML placeholder의 참조값일 뿐이므로 결과를 다시 `y`로 바꾸지 않는다. **변수 저장소에서의 우선순위와 설정 경로에서의 우선순위를 구분한다.**

고급 `sources=`는 후속 API로 두되 순서가 결과를 결정하게 한다. 숨겨진 우선순위 숫자와 등록 순서를 혼용하지 않는다. CLI 연동도 `sys.argv`를 자동으로 읽지 않고 호출자가 파싱한 값을 `overrides`로 전달하게 한다.

## 프로파일 bootstrap

프로파일은 모든 named config에 공통으로 적용한다. 최상단 `profile`을 예약 키로 사용하고 `settings.profile`로 조회한다. 각 모델의 필드에 복제하지 않는다.

프로파일 결정 우선순위는 다음과 같다.

```text
load(profile=...)
  > 프로세스의 PYDEMIA_PROFILE
  > 기본 .env의 PYDEMIA_PROFILE
  > 기본 config.yaml의 profile
  > 미선택(None)
```

`PYDEMIA_PROFILE`은 loader 제어 변수이며 `env_prefix`와 무관하다. 임의의 `ENVIRONMENT`, `APP_PROFILE`을 자동으로 해석하지 않는다. 기존 서비스의 같은 이름이 다른 용도로 쓰일 수 있기 때문이다.

bootstrap 순서:

1. `root_dir`과 기본 YAML 경로를 확정하고 환경변수를 한 번 복사한다.
2. 기본 `.env`를 보간 없이 읽고 기본 YAML을 안전하게 파싱한다.
3. 위 우선순위로 profile을 한 번 결정한다. YAML의 `profile`과 `.env`의 `PYDEMIA_PROFILE`은 초기 버전에서 literal 문자열만 허용한다.
4. 선택한 profile의 `config.<profile>.yaml`, `.env.<profile>`을 읽는다.
5. profile을 변경하지 않은 채 나머지 설정을 병합·보간·검증한다.

profile 미선택 시 기본 파일만 읽는다. library가 임의로 `local`을 선택하지 않는다. local 기본 동작이 필요하면 예시처럼 `config.yaml`에 `profile: local`을 선언한다.

profile 문법은 `[a-z][a-z0-9_-]*`로 제한한다. 빈 문자열, 경로 구분자, `..` 등이 들어간 값은 오류다. `allowed_profiles=("local", "test", "stg", "prd")`를 지정하면 선언하지 않은 값도 오류가 된다.

프로파일 YAML에 `profile`, 프로파일 dotenv에 `PYDEMIA_PROFILE`이 있으면 같은 값이어도 오류다. 자신을 읽게 할 프로파일을 그 파일에서 결정할 수 없게 한다. Spring Boot 역시 활성 프로파일 선언을 프로파일 전용 문서에 허용하지 않는다. [Spring Boot 프로파일 규칙](https://docs.spring.io/spring-boot/reference/features/profiles.html)

`.env.local`은 `local`일 때만 읽는다. `.env.<profile>.local`, 복수 활성 profile, profile group은 초기 버전에서 지원하지 않는다.

## 경로와 파일 탐색

`root_dir`의 기본은 loader 생성 시점의 현재 디렉터리다. 서비스에서는 예시처럼 명시할 것을 권장한다. 상위 디렉터리를 순회하거나 사용자 홈의 `.env`를 자동 탐색하지 않는다.

| 파일 | 기본 정책 |
| --- | --- |
| 기본 탐색 이름 `config.yaml` | 없으면 생략하여 환경변수만으로 구성 가능 |
| 자동 선택 `config.<profile>.yaml` | 없으면 생략 |
| `.env`, `.env.<profile>` | 없으면 생략 |
| `yaml_file=...`로 명시한 파일 | 없으면 오류 |
| 존재하지만 읽기 실패·문법 오류가 있는 파일 | optional 여부와 관계없이 오류 |

`require_profile_yaml=True`로 프로파일 YAML 존재를 강제할 수 있다. 배포 환경이 환경변수만 사용하면 이 옵션을 켜지 않는다. 누락된 optional 파일도 source report에 기록한다.

`yaml_file="config/service.yaml"`이면 profile variant는 `config/service.<profile>.yaml`이다. dotenv는 여전히 `root_dir`에서 찾는다. 모든 상대 입력 경로는 `root_dir` 기준이다. YAML의 일반 `Path` 필드 값까지 자동으로 파일 위치 기준 경로로 바꾸지는 않는다.

여러 YAML 경로를 읽는 기능은 후속 단계에서 추가하며 명시한 순서대로 적용한다. 초기에는 YAML 내부 `include`, glob, 원격 URL, 실행 가능한 tag를 지원하지 않는다.

## 환경변수와 보간의 정확한 규칙

### 환경변수 view

dotenv는 `dotenv_values(..., interpolate=False)`로 읽고 다음 순서의 독립적인 mapping을 만든다.

```text
E = .env < .env.<profile> < load 시작 시 복사한 os.environ
```

`dotenv_values`가 프로세스 환경을 수정하지 않는 성질을 활용한다. 기본 내장 보간을 그대로 사용하면 파일 파싱 시점의 우선순위가 섞일 수 있으므로 보간은 라이브러리 resolver에서 담당한다. [python-dotenv 공식 문서](https://bbc2.github.io/python-dotenv/)

테스트용 `load(environ={...})`는 프로세스 환경 입력을 완전히 대체한다. dotenv는 별도로 `dotenv=False`로 끌 수 있다. profile과 YAML variant 선택에 사용되는 환경도 동일한 mapping이다.

dotenv의 값 없는 `KEY` 선언은 오류, `KEY=`는 빈 문자열이다. 사용되는 dotenv 값의 변수 참조는 최종 E를 기준으로 해석하며 순환 참조는 경로만 포함한 오류로 보고한다. 참조되는 OS 값은 literal로 취급해 그 안의 `${...}`를 재해석하지 않는다. 파일 내 순서에 따라 참조 결과가 달라지지 않아야 한다. 이 보간 정책은 python-dotenv의 기본 동작과 구분하여 문서화한다.

### 환경변수 이름 바인딩

- 기본 prefix는 `PYDEMIA_`이고 서비스에서는 `MYAPP_`처럼 교체할 수 있다. bootstrap 변수 `PYDEMIA_PROFILE`은 항상 별도로 예약한다.
- 고정 모델 경로를 대문자로 변환하고 `.`을 `__`로 바꾼다. `pool_size`의 `_`는 그대로 보존한다.
- 자동 바인딩은 정규 대문자 이름만 인정한다. POSIX에서 소문자 대체 이름은 추측하지 않는다. Windows의 환경변수 대소문자 비구분 특성은 플랫폼 계약에 명시한다.
- 같은 source에서 모델 전체 JSON과 세부 경로가 함께 있으면 세부 경로가 승리한다. source가 다르면 source 우선순위를 먼저 적용한다.
- list, tuple, dict, nested model 전체 값은 JSON으로 전달한다. 쉼표 분리나 Python literal 평가는 하지 않는다.
- 동적 dictionary의 key는 전체 JSON 안에서 원래 대소문자를 보존한다. list index와 임의 dictionary key에 대한 `__` 부분 override는 초기 버전에서 지원하지 않는다.
- source별로 경로를 정규화한 뒤 병합한다. 전체 E를 한 번 바인딩하면 서로 다른 변수명이 같은 경로를 덮는 경우 source 우선순위를 잃을 수 있다.
- alias 기능 도입 시 alias는 전용 등록 옵션으로 관리한다. 같은 source에서 alias와 정규 이름이 동일 경로를 중복 정의하면 오류로 처리한다. Pydantic 직렬화 alias를 환경변수 alias로 자동 간주하지 않는다.

### YAML placeholder

| 문법 | 의미 |
| --- | --- |
| `${VAR}` | unset이면 오류, 빈 문자열은 그대로 사용 |
| `${VAR:-default}` | unset 또는 빈 문자열이면 fallback 사용 |
| `$${VAR}` | literal `${VAR}` |
| `prefix-${VAR}-suffix` | 문자열 일부 치환 |

초기 문법은 변수명 `[A-Za-z_][A-Za-z0-9_]*`와 literal fallback만 지원한다. fallback 안의 중첩 placeholder, `${VAR-default}`, `${VAR:default}`, shell 명령, Python 표현식은 지원하지 않으며 placeholder처럼 시작한 미지원 구문은 오류로 보고한다. Spring 문법 전체를 지원한다고 표방하지 않는다.

YAML을 먼저 파싱하고 병합한 후 **최종 결과에 남은 YAML 문자열 값 노드**만 보간한다. mapping key는 보간하지 않는다. 코드 기본값과 `overrides`의 문자열, 직접 바인딩한 OS 문자열은 literal이다. dotenv 문자열의 보간은 E resolver 규칙으로 별도 처리한다.

이 순서는 다음을 보장한다.

- 직접 env override가 이긴 경우 아래 YAML에 남아 있던 미정의 placeholder 때문에 로딩이 실패하지 않는다.
- 환경변수 값에 `:`, `#`, 따옴표, 개행이 있어도 새로운 YAML 구조로 해석하지 않는다.
- 미정의 변수를 `${VAR}` 문자열 그대로 남기지 않는다. 최종 사용 값이면 startup 오류다.
- 보간은 URL encoding을 수행하지 않는다. 자격 증명으로 DSN을 만드는 작업은 애플리케이션에서 처리한다.

구문 오류와 중복 키는 덮어써질 파일에도 허용하지 않는다. 소스 파싱 오류와 최종 값 해석 오류를 구분한다.

### 타입, 빈 문자열, null

환경변수와 보간 결과는 기본적으로 문자열이다. 최종 필드 schema를 기준으로 변환한다. 복합 필드의 전체 값이면 JSON decoding을 먼저 수행하고 Pydantic에 전달한다. 문자열 필드의 `"0012"`, `"null"`을 임의로 숫자나 null로 바꾸지 않는다.

bool 문자열은 대소문자를 구분하지 않는 `true`, `false`, `1`, `0`만 허용하는 것으로 계약을 좁힌다. YAML도 boolean `true`/`false` 표기를 사용한다. YAML loader는 `on`, `off`, `yes`, `no`를 암묵적인 boolean으로 바꾸지 않는 resolver 정책을 갖는다.

숫자 범위, enum, URL, Path 등은 schema로 검증한다. 초 단위 timeout처럼 단위를 필드명에 표시한다. `"30s"`, `"128MiB"`를 기본적으로 추측하지 않고 이후 명시적 사용자 타입으로 추가할 수 있다.

`null`은 명시적 값이다. YAML의 `null` 또는 override의 `None`은 하위 값을 지우고 nullable 필드에만 허용한다. 환경변수의 빈 문자열은 값을 제공한 것이며 기본값으로 자동 복귀하지 않는다. 문자열 `null`도 자동으로 `None`이 되지 않는다. 환경변수 전용 null token은 초기 버전에서 두지 않는다.

## 병합·검증 정책

| 입력 | 동작 |
| --- | --- |
| mapping + mapping | key별 재귀 병합 |
| list/tuple | 상위 source 값으로 전체 교체 |
| scalar | 상위 source 값으로 교체 |
| 명시적 null | 값 교체 후 schema 검증 |
| 빈 mapping `{}` | 하위 mapping을 비우지 않음 |
| 타입이 다른 노드 | 상위 노드로 교체하고 최종 schema로 검증 |

list append, set union, list index patch, delete sentinel은 초기 버전에 두지 않는다. YAML의 duplicate key는 오류다. YAML root는 mapping이어야 하며 다중 document, merge key `<<`, 사용자 정의 tag, 순환 alias는 초기 지원에서 제외한다. 파서에 입력 크기·노드 수·깊이 제한을 둔다.

모델은 `extra="forbid"`, `validate_default=True`, `frozen=True`를 기본으로 한다. 잘못된 key를 조용히 버리지 않는다. YAML의 등록되지 않은 최상위 영역과 env_prefix 아래의 알 수 없는 변수는 기본적으로 오류다. prefix 외 변수는 무시하고 placeholder resolver에서만 접근한다. 기존 설정을 일부만 이관할 때는 `unknown="ignore"`를 명시하고 진단 보고서에 무시된 **경로만** 남긴다.

기본값은 최종 바인딩 단계에서 채운다. 부모 모델의 default instance/default factory가 만든 nested 값도 부분 override 시 보존해야 한다. 예를 들어 `PoolConfig(size=20)`이 기본이고 timeout만 override하면 size는 20이다. 이 동작은 Pydantic 기본 바인딩에 전적으로 맡기지 않고 defaults adapter의 계약 시험으로 확인한다. factory는 load당 필요한 지점에서 한 번만 실행하고 조회마다 다시 실행하지 않는다. 필수값 누락을 확인하려고 모든 모델을 먼저 생성하지 않는다.

검증 실패 시 이름, 경로, source, 오류 종류를 모아 `ConfigValidationError`를 발생시킨다. 일부 모델만 성공한 snapshot은 반환하지 않는다. 파일 접근, YAML parsing, profile, 보간, binding 오류도 공통 `ConfigError` 하위로 분류한다.

## 설정 주입과 실행 중 변경

### 기본 주입: 생성자 인자

```python
class UserRepository:
    def __init__(self, database: DatabaseConfig):
        self.database = database


repository = UserRepository(settings.get("database", DatabaseConfig))
```

`get(name, model_type)`은 등록 타입과 요청 타입의 일치를 확인하고 타입 힌트를 보존한다. 문자열을 평가하거나 호출 스택에서 설정을 찾지 않는다.

snapshot 내부 tree는 변경 불가능하게 보관한다. 모델 반환 시 캐시된 검증 결과의 방어적 deep copy를 사용해 한 소비자가 list/dict를 수정해도 다른 소비자와 snapshot에 전파되지 않게 한다. `frozen=True`만으로 nested container까지 불변이 되는 것은 아니므로 tuple 등 immutable 필드 타입을 권장한다. 코어 모델은 복제 가능한 설정 데이터로 제한하고 연결 객체나 임의 runtime 객체를 넣지 않는다.

### FastAPI 연동: 선택 의존성

아래는 후속 adapter의 목표 사용법이다. startup/lifespan에서 한 번 로딩하고 application instance에 보관한다.

```python
from typing import Annotated

from fastapi import Depends, FastAPI
from pydemia_config.integrations.fastapi import config_dependency

api = FastAPI()
api.state.config = settings

DatabaseDep = Annotated[
    DatabaseConfig,
    Depends(config_dependency("database", DatabaseConfig)),
]


@api.get("/health/configured")
def configured(database: DatabaseDep):
    return {"configured": bool(database.host)}
```

dependency는 현재 request의 app state를 사용한다. 전역 singleton이나 전역 `lru_cache`로 여러 앱의 설정을 공유하지 않는다. 다른 DI 컨테이너와는 provider 함수로 연결할 수 있다. `@inject`, `Annotated[..., ConfigRef(...)]` 같은 자동 주입은 실제 사용 사례가 확인된 뒤 별도 adapter로 검토한다.

### 변경 API

```python
test_settings = settings.with_overrides(
    {"database": {"pool": {"size": 1}}}
)
```

`with_overrides()`는 기존 snapshot의 해석된 값에 새 값을 합쳐 다시 검증한 독립 snapshot을 반환한다. 환경·파일을 다시 읽지 않고 profile을 바꾸지 않는다. 원본 객체는 유지된다. 파일 또는 환경의 변경을 반영하려면 `loader.load()`를 다시 호출한다.

자동 reload와 file watch는 초기 범위에서 제외한다. 이후 지원하더라도 새 snapshot을 완전히 검증한 뒤 atomic swap하고 요청 단위로 같은 generation을 보게 해야 한다. 설정이 바뀌었다고 기존 DB pool이나 클라이언트가 자동 재생성되는 것은 아니다.

## 출처 추적과 비밀값 처리

`explain(path)`는 운영 시 어떤 source가 이겼는지 확인하는 읽기 전용 API다. 기본 출력에는 원문 값을 넣지 않는다.

```python
settings.explain("database.pool.size")
# path: database.pool.size
# winner: process-env:MYAPP_DATABASE__POOL__SIZE
# shadowed: .env.local -> config.local.yaml -> config.yaml -> model-default
```

placeholder는 두 종류의 출처를 보존한다. `database.password`의 정의 위치는 YAML이고 값의 참조 위치는 `.env:DB_PASSWORD`일 수 있다. shadowed placeholder를 출처 추적 목적으로 평가하지 않는다.

`SourceValue`는 source ID, 파일/환경변수명, 설정 경로, 가능하면 YAML line/column, 보간 참조, sensitive 여부를 가진다. line/column은 파서 adapter가 실제로 제공하는 경우만 표시한다. 검증기가 새로 계산한 값은 원래 source 값인 것처럼 표시하지 않고 derived/default로 구분한다.

비밀값은 `SecretStr`, `SecretBytes` 또는 명시적 field metadata로 표시한다. `dump()`는 기본적으로 모든 env/dotenv 유래 값과 secret field를 가리고 모델에서 공개 출력으로 지정한 필드만 노출한다. `password`, `token`, `secret` 등 이름 기반 마스킹은 보조 수단이다. placeholder를 조합한 문자열에도 민감도를 전파한다.

검증 실패 전 원시 입력, Pydantic error의 `input`·`ctx`, chained exception, 잘못된 YAML 원문이 로그로 새지 않게 오류를 새로 구성한다. 필드 경로·source·기대 타입을 제공하되 임의 validator가 만든 원문 오류 메시지는 그대로 출력하지 않는다. `get()`은 애플리케이션 사용을 위한 실제 값 접근 API이며 진단 출력과 구분한다.

## 내부 구조와 의존성

```text
ConfigLoader + Registry
  → BootstrapResolver                  profile·파일 경로 확정
  → SourceReaders                      YAML / dotenv / process env / override
  → EnvBinder + MergeEngine            source별 경로 정규화·우선순위 병합
  → PlaceholderResolver                최종 노드와 E의 참조 해석
  → ModelBinder                        기본값 적용·타입 변환·검증
  → ConfigSnapshot                     조회·복제·출처 설명
```

소스 리더는 원시 값과 provenance를 반환한다. 병합 엔진은 파일을 읽지 않고 입력 tree를 변경하지 않는다. resolver는 `os.environ`에 직접 접근하지 않고 전달받은 환경 view만 사용한다. 등록된 schema 정보는 env 복합 타입 해석과 최종 바인딩에서 공유한다.

```text
src/pydemia_config/
  __init__.py
  loader.py
  registry.py
  bootstrap.py
  models.py
  sources/{base,yaml,dotenv,environment,overrides}.py
  binding.py
  merge.py
  interpolation.py
  provenance.py
  snapshot.py
  errors.py
  integrations/fastapi.py               # 후속 optional extra
tests/
  unit/
  contracts/
  integration/
examples/
  basic/
  named_databases/
  fastapi/                             # adapter 도입 시
```

필수 의존성 후보는 `pydantic>=2,<3`, `python-dotenv`, `PyYAML`이다. PyYAML은 전역 resolver를 수정하지 않는 전용 SafeLoader subclass로 감싼다. 필요한 YAML scalar 규칙·duplicate key 감지·source mark를 구현한다. 구체적인 최소 버전은 prototype과 CI 결과로 고정한다.

`pydantic-settings`를 그대로 감싼 구현도 prototype에서 비교한다. 단일 custom source로 최종 tree를 전달해 이 설계의 우선순위·기본값·오류 마스킹·출처 추적을 보존할 수 있다면 채택할 수 있다. 초기 권장안은 Pydantic 모델 검증과 별도 loader다. 이 선택으로 직접 유지해야 할 env binding과 defaults adapter 비용도 평가한다. 내부/private API override는 피한다.

## 지원 기능의 단계

| 단계 | 구현 범위 | 완료 조건 |
| --- | --- | --- |
| 계약 prototype | source 우선순위, nested defaults, 보간 순서, profile bootstrap을 최소 코드로 비교 | Pydantic 직접 사용/Settings adapter 선택과 실패 사례가 계약 시험으로 고정됨 |
| MVP | 이름 등록, nested 모델, YAML·프로파일 dotenv·OS env·override, 타입 검증, snapshot, 최소 explain·마스킹 | 문서의 기본 예시와 아래 계약 시험 통과; import 부작용 없음 |
| 실서비스 적용 | template-backend를 대상으로 호환 adapter와 migration 예시 | 기존 필수 설정의 동등성 확인, 의도한 차이 기록, 앱 생성·테스트 격리 검증 |
| 사용성 확장 | FastAPI extra, schema export, `.env.example` 생성, explicit multi-YAML, alias | 코어만 설치한 환경의 의존성 유지, 문서 예시 smoke test 통과 |
| 운영 확장 | 명시적 secrets directory source, custom source protocol, validation CLI | source 순서·누락 정책·마스킹 계약 추가; 기존 순서에 숨겨진 변경 없음 |

파일 secret source를 추가할 때는 `YAML < secrets directory < dotenv < process env < overrides`를 기본 후보로 삼고 활성화한 경우에만 삽입한다. 원격 secret store·Vault·config server는 별도 plugin과 명시적 timeout/cache 정책이 필요하므로 초기 개발에서 제외한다.

설정 간 참조는 후속 기능으로 `${config:database.host}`처럼 환경변수와 구문을 분리하는 방향을 검토한다. 도입 시 순환 감지, 타입 보존, secret 전파를 함께 지원해야 한다. shell 실행, `eval`, 파일 내 임의 Python 실행은 지원 대상이 아니다.

## 검증 계획

MVP의 계약 시험은 단순 getter 호출보다 소스 경계와 실패 동작에 집중한다.

| 시험 | 기대 결과 |
| --- | --- |
| 모든 source에 같은 필드 정의 | 명시적 override가 승리하고 출처 일치 |
| code default·기본 YAML·profile YAML·dotenv·OS 순차 제거 | 정의된 순서대로 다음 값 선택 |
| `.env`와 `.env.test`가 서로 다른 필드 정의 | 두 값 모두 유지 |
| `prd` 선택 시 `.env.local`이 존재 | 읽지 않음 |
| `load(profile=...)`, OS, 기본 dotenv, YAML이 서로 다름 | bootstrap 우선순위 준수 |
| profile 파일이 profile을 재선언 | 로딩 오류, 재탐색 없음 |
| profile 미선택·선택 오타·필수 파일 누락 | 정해진 정책과 diagnostics 일치 |
| YAML `${MISSING}`을 직접 env 값으로 override | 미정의 변수 오류 없이 env 값 사용 |
| 최종 YAML `${MISSING}` 유지 | 명확한 startup 오류 |
| unset·빈 문자열·fallback·escape | placeholder 표의 규칙과 일치 |
| 보간값에 개행·따옴표·콜론·`#` 포함 | YAML 구조 불변, 문자열 보존 |
| dotenv 참조의 OS override·순환 참조 | 최종 E 사용, 순환 시 경로만 보고 |
| OS 값 자체가 `${OTHER}` 포함 | 재보간하지 않음 |
| 저우선 source의 세부 경로와 고우선 source의 JSON 객체 충돌 | source 우선순위 먼저, 같은 source에서만 세부 경로 우선 |
| nested 기본 instance의 한 필드만 override | 기본 instance의 나머지 값 보존 |
| list·빈 mapping·null·scalar/mapping 교체 | 병합 계약과 schema 검증 준수 |
| bool `false`, 숫자 오류, JSON list, 문자열 `0012` | 필드 타입에 맞는 변환·오류 |
| YAML duplicate key·unknown field·unknown prefixed env | startup 오류 또는 명시한 ignore 정책 |
| 여러 name에 같은 모델 등록 | 서로 다른 값 주입, 잘못된 타입 요청 거부 |
| 동시 테스트에서 서로 다른 root/profile/environ | 환경 오염·전역 cache 공유 없음 |
| 반환 모델의 nested container 수정 | 원본 snapshot과 다른 조회에 영향 없음 |
| import 전후 및 load 전후 `os.environ` 비교 | 변경 없음 |
| 실패 값과 비밀값을 모든 오류·로그·dump 경로에 주입 | 원문 값이 노출되지 않음 |
| optional 파일 부재와 존재하는 invalid 파일 | 부재만 생략, invalid 파일은 실패 |

Linux·macOS·Windows에서 환경변수 이름과 경로 처리의 차이를 확인한다. 배포 전 wheel/sdist 설치, 지원 Python/Pydantic 조합, 공개 예제 실행, 타입 검사까지 검증한다. 설정값을 재현하기 위해 실제 서비스의 비밀 파일을 테스트 fixture로 복사하지 않는다.

## 기존 서비스 이관

기존 `_root_key="database"`는 `register("database", DatabaseConfig)`로 옮긴다. nested 도메인 모델과 validation은 서비스에 유지하되 `os.getenv()`를 필드 기본값에서 제거한다.

1. 테스트에 필요한 비민감 synthetic fixture를 만들고 기존 loader의 동작을 기록한다.
2. 기존 YAML의 `config:` wrapper가 필요하면 호환 adapter의 `root_key="config"`로 처리한다. core가 wrapper 유무를 추측하지 않는다.
3. `DATABASE__HOST` 등 기존 변수명을 유지해야 하면 `env_prefix=""`를 명시한다. 이 모드에서는 등록한 root에 해당하는 변수만 검사하고 다른 시스템 환경변수는 무시한다.
4. `DEFAULT_CONFIG`, `APP_CONFIG` 경로 선택은 application bootstrap에서 명시적인 loader 입력으로 변환한다. multi-YAML 도입 전 이 동작을 core의 숨겨진 환경변수 규칙으로 추가하지 않는다.
5. 기존 import-time singleton을 startup load와 constructor/provider 주입으로 옮긴다. 임시 호환 모듈이 필요하면 초기화 전 접근에 오류를 내도록 한다.
6. dotenv 누적 로딩, 미정의 placeholder 오류, unknown key 검사, list 교체, 비밀 필드 타입 변경을 각각 호환성 변경으로 검토한다.

최초 검증 대상은 작은 template-backend 설정 모듈로 잡고 이후 shared 설정을 쓰는 서비스로 넓힌다. 라이브러리 설계만으로 기존 서비스의 동작 호환성이 검증됐다고 보지 않는다.

## 구현 전 결정사항의 상태

이 문서에서 권장 기본값으로 제시한 단일 profile, `profile` 최상단 키, Pydantic v2, `__` 구분자, source 우선순위, startup validation, 독립 snapshot은 MVP의 기준안이다.

Python 최소 버전, YAML loader의 지원 문법과 resource limit 수치, Pydantic Settings adapter 채택 여부, 배포명과 라이선스는 첫 prototype 및 패키징 단계에서 확정한다. API 예시와 계약을 먼저 고정한 뒤 구현을 시작하며 이 설계 작성 단계에서는 서비스 코드나 배포 설정을 변경하지 않는다.
