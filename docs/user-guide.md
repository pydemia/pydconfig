# 사용자 가이드

pydconfig 1.0.0의 사용법이다. 설치는 [README](../README.md#설치), 개발·시험 방법은 [개발 가이드](development.md)를 따른다. 전체 파일 예제는 설치된 wheel에서 실행하고 출력까지 검사한다.

## 빠른 시작

`ConfigModel`에는 호스트, 포트, timeout처럼 환경 설정 데이터만 선언한다. 데이터베이스 client나 logger는 설정 로딩에 성공한 뒤 애플리케이션에서 생성한다.

```python
from pydantic import Field
from pydconfig import ConfigLoader, ConfigModel


class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1, le=100)
    timeout: float = Field(default=5.0, gt=0)


class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    pool: PoolConfig = Field(default_factory=PoolConfig)


class FeatureConfig(ConfigModel):
    enabled: bool = False
    hosts: list[str] = Field(default_factory=list)


loader = ConfigLoader(root_dir="/path/to/app-config")
loader.register("database", DatabaseConfig)
loader.register("feature", FeatureConfig)
snapshot = loader.load()

database = snapshot.get("database", DatabaseConfig)
feature = snapshot.get("feature", FeatureConfig)
```

`root_dir`에 파일을 둔다.

```text
app-config/
  config.yaml
  config.local.yaml
  .env
  .env.local
```

`config.yaml`:

```yaml
profile: local
database:
  host: "${DB_HOST:-localhost}"
  port: 5432
  pool:
    size: 16
feature:
  enabled: false
  hosts: [primary, replica]
```

`config.local.yaml`:

```yaml
database:
  host: local-db.internal
  pool:
    timeout: 2.5
```

`.env`:

```dotenv
PYDCONFIG_DATABASE__POOL__SIZE=24
PYDCONFIG_FEATURE__ENABLED=TRUE
```

`.env.local`:

```dotenv
PYDCONFIG_DATABASE__POOL__SIZE=32
PYDCONFIG_FEATURE__ENABLED='"False"'
```

OS에 같은 이름의 변수가 없으면 다음 값이 나온다.

| 필드 | 결과 | 적용 source |
| --- | --- | --- |
| `snapshot.profile` | `local` | 기본 YAML |
| `database.host` | `local-db.internal` | 프로파일 YAML; 가려진 기본 YAML의 placeholder는 평가하지 않음 |
| `database.port` | `5432` | 기본 YAML |
| `database.pool.size` | `32` | 프로파일 dotenv |
| `database.pool.timeout` | `2.5` | 프로파일 YAML |
| `feature.enabled` | `False` | 프로파일 dotenv의 실제 quote 한 쌍 제거 후 boolean 해석 |
| `feature.hosts` | `["primary", "replica"]` | 기본 YAML |

OS의 `PYDCONFIG_DATABASE__POOL__SIZE=40`은 32를 덮는다. `load(overrides={"database": {"pool": {"size": 48}}})`는 OS 값도 덮는다. 전체 파일은 [기본 예제](../examples/basic/README.md)에 제공한다.

## 이름과 설정 경로

등록 이름은 애플리케이션이 조회할 때 쓰는 식별자다. 설정 경로는 YAML, 환경변수, override와 출처 진단이 사용하는 위치다. `path`를 생략하면 이름과 경로가 같다.

```python
loader = ConfigLoader(root_dir="/path/to/config")
loader.register("primary_db", DatabaseConfig, path="database.primary")
loader.register("replica_db", DatabaseConfig, path="database.replica")
snapshot = loader.load()

primary = snapshot.get("primary_db", DatabaseConfig)
replica = snapshot.get("replica_db", DatabaseConfig)
```

이 등록은 다음 YAML과 연결한다.

```yaml
database:
  primary:
    host: primary.internal
  replica:
    host: replica.internal
```

환경변수는 `PYDCONFIG_DATABASE__PRIMARY__HOST`, `PYDCONFIG_DATABASE__REPLICA__HOST`다. `PYDCONFIG_PRIMARY_DB__HOST`는 등록 경로와 다르므로 자동 바인딩하지 않는다.

이름과 경로 segment는 소문자로 시작하고 소문자·숫자·밑줄을 사용한다. segment 안의 `__`는 허용하지 않는다. 같은 이름, 같은 경로, 부모·자식으로 겹친 등록 경로, 최상단 `profile` 등록은 거부한다. 조회 시 모델 타입도 등록 타입과 정확히 일치해야 한다.

`database.primary`만 등록한 경우 `database`는 구조를 위한 가상 ancestor다. 전체 JSON 환경변수는 `PYDCONFIG_DATABASE__PRIMARY`부터 사용할 수 있으며 `PYDCONFIG_DATABASE`는 구조 오류다.

## Nested 모델과 기본값

모든 nested 설정 모델도 `ConfigModel`을 상속한다. 기본 child 설정은 모델 class를 factory로 지정한다.

```python
class DatabaseConfig(ConfigModel):
    pool: PoolConfig = Field(default_factory=PoolConfig)
```

loader는 이 선언을 child schema의 원시 기본값으로 펼친다. `PoolConfig()`를 미리 만들어 default로 넣지 않는다. child 기본값을 일부 바꾸려면 factory가 raw mapping을 반환하게 한다.

```python
class DatabaseConfig(ConfigModel):
    pool: PoolConfig = Field(default_factory=lambda: {"size": 20})
```

factory는 인자가 없는 함수로 작성한다. raw scalar·container 결과는 load당 한 번 수집하며 상위 source가 값을 덮어도 실행한다. 검증된 모델 인스턴스를 반환하는 factory와 이전 필드 데이터에 의존하는 factory는 지원하지 않는다. 파일 읽기, logger 변경, client 생성은 factory·validator 밖에서 수행한다.

필수 nested 필드를 통째로 생략하면 child의 기본값만으로 부모를 자동 생성하지 않는다. parent 생성이 필요하면 위의 `Field(default_factory=...)`를 선언한다.

## 환경변수 바인딩

기본 접두사는 `PYDCONFIG_`이며 경로의 점을 `__`로 바꾸고 대문자로 표기한다.

| 설정 경로 | 기본 환경변수 |
| --- | --- |
| `database.host` | `PYDCONFIG_DATABASE__HOST` |
| `database.pool.size` | `PYDCONFIG_DATABASE__POOL__SIZE` |
| `feature.enabled` | `PYDCONFIG_FEATURE__ENABLED` |
| `feature.hosts` | `PYDCONFIG_FEATURE__HOSTS` |

```python
loader = ConfigLoader(root_dir="/path/to/config", env_prefix="MYAPP_")
```

접두사를 바꿔도 프로파일 선택 변수는 `PYDCONFIG_PROFILE`이다. `MYAPP_PROFILE`로 바뀌지 않는다.

복합 값은 전체 JSON으로 전달한다.

```dotenv
PYDCONFIG_DATABASE={"host":"db.internal","port":5432}
PYDCONFIG_DATABASE__POOL={"size":20,"timeout":1.5}
PYDCONFIG_FEATURE__HOSTS=["primary","replica"]
```

같은 source 안에서는 더 깊은 모델 JSON이 parent JSON을 덮고 scalar leaf가 마지막으로 적용된다. source가 다르면 source 우선순위가 먼저다. 따라서 OS의 parent JSON은 `.env`의 leaf보다 우선한다. container 원소를 `HOSTS__0`처럼 바꾸는 경로는 지원하지 않으며 전체 list를 교체한다.

POSIX에서는 정규 대문자 이름만 자동 바인딩한다. Windows OS 환경은 대소문자 비구분으로 처리하며 충돌하는 이름은 오류다. dotenv key는 Windows에서도 파일에 쓰인 대소문자를 보존한다.

## 프로파일과 dotenv

프로파일 선택은 다음 순서다.

```text
load(profile=...) > OS PYDCONFIG_PROFILE > .env PYDCONFIG_PROFILE
                  > 기본 YAML의 profile > 선택 없음
```

```python
loader = ConfigLoader(
    root_dir="/path/to/config",
    allowed_profiles=["local", "test", "stg", "prd"],
)
loader.register("database", DatabaseConfig)
loader.register("feature", FeatureConfig)
snapshot = loader.load(profile="test")
assert snapshot.profile == "test"
```

`test`를 선택하면 `config.yaml`과 `config.test.yaml`, `.env`와 `.env.test`를 누적 적용한다. `.env.local`은 함께 읽지 않는다. 기본 `.env`의 `PYDCONFIG_PROFILE=local`을 명시적 `test`가 덮어도 `.env`의 다른 값은 기본 source로 남는다.

프로파일은 소문자로 시작하고 소문자·숫자·밑줄·하이픈을 허용한다. 빈 문자열은 선택 없음이 아니라 오류다. 우선순위가 낮은 profile 선언도 타입·문법이 잘못되면 오류다. profile YAML의 `profile`, profile dotenv의 `PYDCONFIG_PROFILE`은 같은 값이더라도 재선언할 수 없다. `${ENVIRONMENT}`로 profile을 보간하지 않는다.

```python
loader = ConfigLoader(root_dir="/etc/app", dotenv=False)
```

`dotenv=False`는 기본·profile dotenv 읽기와 기본 `.env`의 profile 후보를 모두 끈다. OS 또는 YAML의 profile 선택은 유지한다. production에서 dotenv 파일을 사용하지 않는 구성에 적합하다.

`require_profile_yaml=True`는 선택한 profile의 YAML 존재를 요구한다. profile이 미선택이면 오류이므로 dotenv-only 배포에서 이 옵션을 켜지 않는다.

## YAML의 환경변수 참조

placeholder는 YAML 구조를 파싱한 뒤 **최종 사용되는 문자열 값**에만 적용한다. `.env < .env.<profile> < OS` 순서로 참조 환경값을 찾는다. 자동 바인딩 접두사 밖의 `DB_HOST` 같은 변수도 참조할 수 있다.

```yaml
database:
  host: "${DB_HOST:-localhost}"
  port: "${DB_PORT:-5432}"
feature:
  hosts: '${APP_HOSTS:-["primary"]}'
```

| 문법 | 동작 |
| --- | --- |
| `${VAR}` | 미정의면 오류, 정의된 빈 값은 빈 문자열 |
| `${VAR:-fallback}` | 미정의 또는 빈 값이면 literal fallback |
| `$${VAR}` | 결과에 `${VAR}`를 그대로 남김 |
| `prefix-${VAR}-suffix` | 문자열 일부를 대체 |

fallback에는 `}`나 중첩 placeholder를 넣을 수 없다. `${VAR-default}`와 `${VAR:default}`는 지원하지 않는다. YAML key는 보간하지 않는다.

OS의 직접 override로 가려진 `${MISSING}`은 평가하지 않는다. `unknown="ignore"`로 제거한 영역의 placeholder도 평가하지 않는다. 다만 읽은 YAML의 문법·중복 key 오류는 source 단계에서 실패한다.

dotenv의 `A=${B}`는 literal이다. YAML `${A}`에 삽입해도 `${B}`를 다시 확장하지 않는다. `load_dotenv()`를 별도로 호출해 전역 환경을 바꾸면 source 간 구분이 달라지므로 loader에 dotenv 읽기를 맡긴다.

## Boolean과 quote

boolean은 실제 bool, 정수 0/1, 문자열 `true/false/1/0`을 지원한다. 문자열은 대소문자를 구분하지 않고 앞뒤 ASCII 공백을 제거한다. `yes/no/on/off`, 빈 문자열과 알 수 없는 token은 오류다.

bool·숫자·JSON 환경 입력은 짝이 맞는 ASCII quote 한 쌍을 한 번 제거한다. 문자열·`SecretStr`·Path·URL·string Enum·string Literal은 기본 보존한다. 문자열의 quote도 제거하려면 필드 **경로**로 지정한다.

```python
loader = ConfigLoader(
    root_dir="/path/to/config",
    env_quote_policy={
        "database.host": "unwrap",
        "feature.enabled": "preserve",
    },
)
```

위 설정의 `feature.enabled`에 실제 `"False"`가 들어오면 오류다. `preserve`가 wrapper 제거를 껐기 때문이다. shell의 `export FLAG="False"`는 구문상의 quote가 제거되어 실제 값이 `False`다. `export FLAG='"False"'`는 실제 quote가 남는 다른 입력이다.

맞지 않는 quote, 단일 quote 한 글자, 내부 quote와 backslash는 임의로 수정하지 않는다. 중첩 quote를 반복 제거하지 않는다. 전체·부분 placeholder와 빈 값·fallback의 차이는 [quote 규칙](configuration-reference.md#boolean과-quote)을 확인한다.

## Snapshot 조회와 변경

`load()`는 모든 등록 모델 검증에 성공한 경우에만 snapshot을 반환한다. `get()`은 등록 이름과 타입을 받고 깊은 복사본을 돌려준다. 조회가 validator와 factory를 다시 실행하지 않는다.

```python
database = snapshot.get("database", DatabaseConfig)
changed = snapshot.with_overrides({"database": {"pool": {"size": 12}}})

assert changed.get("database", DatabaseConfig).pool.size == 12
# snapshot의 설정은 그대로 유지한다.
```

`with_overrides()`는 보관된 검증 전 입력에 새 Python 값을 합쳐 재검증한다. 파일·환경변수를 다시 읽거나 기존 입력의 quote를 다시 제거하지 않는다. 새 override 문자열은 YAML 보간 대상이 아니다. profile 변경은 이 API로 할 수 없다.

파일 또는 환경 변경을 읽으려면 `loader.load()`를 다시 호출한다. 서비스가 새 snapshot을 쓰게 하는 전환은 애플리케이션에서 수행한다. 설정 client를 자동으로 다시 만들거나 기존 연결을 종료하지 않는다.

## 출처와 오류 진단

```python
explanation = snapshot.explain("database.pool.size")
report = snapshot.source_report()
```

`explain()`은 값 없이 입력을 정의한 source, placeholder 참조 source, 가려진 source, null 장벽과 schema 기본값 fallback을 설명한다. 임의 validator가 만든 최종 출력의 데이터 의존관계까지 추적하지 않는다. `source_report()`는 읽음·부재로 생략·비활성 파일과 무시한 경로 등을 보고한다. 두 반환 객체는 frozen dataclass이며 `dataclasses.asdict()`로 값 없는 진단 mapping을 만들 수 있다. [진단 객체 reference](configuration-reference.md#오류와-진단)

| 문제 | 확인할 사항 |
| --- | --- |
| 환경변수가 반영되지 않음 | name 대신 path를 사용했는지, prefix와 `__`·대문자가 맞는지, `environ={}`로 OS를 제외했는지 |
| profile 파일이 읽히지 않음 | 실제 선택 profile, loader 생성 시 `root_dir`, 파일 variant 이름, source report의 skipped 상태 |
| bool을 읽지 못함 | 허용 token인지, 실제 quote가 몇 겹인지, 해당 path의 preserve 정책 |
| 문자열에 quote가 남음 | 기본 보존 정책인지, shell·dotenv 구문 quote와 실제 문자 quote를 구분했는지 |
| `${VAR}` 오류 | 최종 사용되는 YAML 값인지, 변수명이 정의되었는지, fallback이 필요한지 |
| unknown 오류 | 등록 경로·필드 오타 또는 의도하지 않은 접두사 변수인지 |
| source 오류 | UTF-8, duplicate key, 허용 YAML subset, JSON 문법과 크기·깊이 제한 |
| 조회 타입 오류 | `get()`의 이름과 모델 타입이 등록 내용과 정확히 일치하는지 |

오류 계약은 [오류 reference](configuration-reference.md#오류와-진단)에 정리했다. 오류를 조사할 때 환경 전체나 모델 전체를 출력하지 않는다. `SecretStr`도 애플리케이션이 원문을 꺼내 출력하면 보호되지 않는다.
