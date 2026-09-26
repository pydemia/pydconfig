# pydconfig 기획서

상태: v1.0.0 구현 반영안 v6. 작성일: 2026-09-26. 사용자 지정 기반은 pydantic·pydantic-settings·python-dotenv다. 라이브러리 API는 src/pydconfig에 구현했다. 검증·배포 증거는 release-plan.md에 기록한다. 동작 계약과 내부 구조는 [상세 설계서](technical-design.md)에 정의한다. 최초 통합 문서는 [리뷰 기준 원본](reviews/initial-proposal.md)으로 보존했다.

## 해결할 문제와 사용 대상

현재 서비스마다 YAML 로딩, 환경변수 치환, 설정 클래스 분리, 기본값 병합을 반복 구현한다. 같은 설정이 코드·YAML·환경변수에 있으면 실제 적용값을 판단하기 어렵고 import 시점의 전역 객체 때문에 앱·테스트별 설정을 분리하기 어렵다.

Python 애플리케이션이 이름별 설정을 타입으로 선언하고, 환경별 값을 일관된 순서로 적용한 객체를 주입받도록 한다. 최초 대상은 FastAPI 서비스와 배치·CLI다. 웹 프레임워크 없이도 같은 설정을 사용할 수 있어야 한다.

## 패키지와 저장소 이름

| 항목 | 이름 또는 경로 |
| --- | --- |
| PyPI 배포명 / Python import | `pydconfig` / `pydconfig` |
| GitHub 저장소 | `pydemia/pydconfig` |
| 로컬 프로젝트 | `/Users/a09255/git/pydconfig` |
| 구현 패키지 경로 | `src/pydconfig/` |
| 기본 환경변수 / 프로파일 변수 | `PYDCONFIG_` / `PYDCONFIG_PROFILE` |

개인 계정명은 패키지명에 포함하지 않는다. 패키지 구현 경로는 src/pydconfig이며 wheel·sdist metadata의 배포명도 pydconfig다. 최초 리뷰 원본의 이전 이름은 당시 검토 근거로 보존한다.

## 요구사항과 인수 기준

| ID | 요구사항 | 인수 기준 |
| --- | --- | --- |
| R1 | name별 설정과 nested 구조 | 같은 타입을 `primary_db`, `replica_db`로 등록해 서로 다른 경로의 값을 조회한다. 이름 또는 등록 경로 충돌은 명시적 오류다. |
| R2 | env가 코드 기본값과 YAML을 override | YAML에 placeholder가 없어도 `MYAPP_DATABASE__POOL__SIZE=20`이 nested 값을 변경한다. |
| R3 | YAML의 `${ENVVAR}` | YAML 구조를 파싱한 뒤 값만 치환한다. unset·빈 값·fallback·escape가 문서 규칙과 일치한다. |
| R4 | `.env`와 `.env.<profile>` | 두 파일을 누적 적용하고 실제 프로세스 환경변수가 같은 변수의 값을 이긴다. `.env.local`은 local 프로파일에서만 읽는다. |
| R5 | 최상단 profile | 기본 YAML의 `profile`을 사용한다. 외부 선택값이 우선하며 profile 전용 파일은 선택을 다시 바꾸지 않는다. |
| R6 | 검증된 설정 주입 | 시작 시 모든 등록 모델을 검증한다. 소비자는 name과 타입을 지정해 객체를 받으며 부분 성공 snapshot은 없다. |
| R7 | 값의 출처 확인 | `explain(path)`에서 정의 source와 placeholder 참조 source를 구분한다. 원문 값을 출력하지 않는다. |
| R8 | 독립적인 실행·테스트 | import와 load가 `os.environ`을 수정하지 않는다. 서로 다른 root/profile/environ으로 만든 snapshot은 공유 상태가 없다. |
| R9 | 설정 변경 | 원본 snapshot을 보존하고 새 override를 재검증한다. 파일·환경의 재로딩은 명시적으로 요청한다. |
| R10 | 지정 기반 라이브러리 | pydantic·pydantic-settings·python-dotenv를 필수 사용한다. 실제 BaseSettings/custom source 실행과 dotenv 파싱을 확인한다. |
| R11 | 환경 설정 데이터에 한정한 타입 지원 | `arbitrary_types_allowed=False`를 유지한다. 임의 객체 필드·설정에 주입할 클라이언트 인스턴스·이를 허용하는 subclass는 등록에서 거부한다. |
| R12 | boolean 대소문자 처리 | `True/False`, `true/false`, `TRUE/FALSE`, 혼합 대소문자를 같은 boolean으로 읽는다. 실제 quote가 남은 환경 입력도 명시된 정규화 규칙으로 처리하며 알 수 없는 token은 오류다. |
| R13 | 환경 입력의 quote 처리 | bool·숫자·복합 JSON은 짝이 맞는 바깥 quote 한 겹을 제거한다. 문자열은 기본 보존하고 필드별 `env_quote_policy`로 제거를 선택한다. 내부 quote·escape·replay 입력을 반복 변환하지 않는다. |
| R14 | Python 3.10–3.14와 호환 | 표준 CPython 3.10–3.14를 대상으로 개발 기준 Python 3.14.7과 기반 의존성의 공개 API·파서 동작을 검증한다. 기반 probe와 실제 pydconfig 계약·배포 패키지 시험 결과를 구분한다. |

## MVP 범위와 확장 순서

MVP는 `ConfigLoader`, `ConfigModel`, `ConfigSnapshot`의 세 API를 중심으로 한다. 이름 등록, 단일 profile, 기본·profile YAML, dotenv 누적 로딩, nested env 바인딩, YAML 보간, 타입 검증, 독립 snapshot, 값 없는 출처 진단을 지원하며 R10의 기반 라이브러리를 사용한다. 환경 입력의 boolean과 quote 처리는 R12·R13에 따른다.

필수 기반은 **pydantic v2, pydantic-settings v2, python-dotenv**다. pydantic은 모델·타입 검증, pydantic-settings는 BaseSettings와 사용자 정의 설정 소스 실행, python-dotenv는 dotenv 파일 파싱을 담당한다. name registry·profile bootstrap·provenance는 이 기반 위에서 구현한다. 세부 schema 지원 범위는 설계서에 고정한다. 표준 CPython 3.10–3.14를 지원 목표로 두고 개발 기준은 최신 안정 Python 3.14.7로 고정한다. Python 3.15 pre-release와 free-threaded/PyPy 지원은 이번 검증 범위에 포함하지 않는다. 미지원 타입은 register 시 거부한다. 버전 확인 근거와 실행 범위는 [호환성 기준](compatibility-plan.md)에 기록한다.

| 시점 | 범위 | 완료 기준 |
| --- | --- | --- |
| 계약 prototype | BaseSettings custom source, source 충돌, nested default, 보간, snapshot 재검증 | 필수 세 라이브러리의 공개 확장 API로 계약을 구현할 수 있음을 확인한다. 불가능한 계약은 문서를 먼저 변경한다. |
| MVP | R1–R14, 문서·최소 예제·배포 패키지 | 설계서의 계약 시험 통과, clean install 후 예제 실행, import 부작용 없음 |
| 첫 서비스 적용 | template-backend의 작은 설정 영역 | 비민감 fixture로 기존 동작과 차이를 비교하고 이관·복구 절차를 확인한다. |
| 사용성 확장 | FastAPI adapter, alias, explicit multi-YAML, schema export | 필요한 호환 입력과 adapter의 앱별 격리를 검증한다. |
| 운영 확장 | 명시적 secret directory, custom sources, 검증 CLI | 추가 source의 순서·실패 정책을 공개하고 기존 기본 순서를 유지한다. |

임의 Python 객체 타입 지원은 제품 범위에 포함하지 않는다. 설정을 읽어 애플리케이션에 주입하는 라이브러리이므로 DB client·logger·service 객체는 검증된 설정을 받은 application bootstrap에서 생성한다. `arbitrary_types_allowed=True`를 활성화하는 호환 모드도 제공하지 않는다.

초기 버전에서 범용 DI 컨테이너, 자동 서비스 탐색, 자동 reload, 원격 설정 서버, 복수 활성 profile, YAML include·표현식 실행은 제공하지 않는다. dotenv는 파일 형식 파싱만 사용하며 **dotenv 내부 변수 보간은 후속 기능**으로 둔다. `${...}` 보간의 MVP 적용 대상은 YAML 값이다. 이는 원래 사용자 요구를 충족하면서 별도 dotenv 참조 엔진의 구현 비용을 제한한 선택이다.

## 사용 경험

```python
from pathlib import Path
from pydantic import Field, SecretStr
from pydconfig import ConfigLoader, ConfigModel

class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1)

class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    password: SecretStr
    pool: PoolConfig = Field(default_factory=PoolConfig)

loader = ConfigLoader(root_dir=Path.cwd(), env_prefix="MYAPP_")
loader.register("database", DatabaseConfig)
settings = loader.load()
database = settings.get("database", DatabaseConfig)
```

```yaml
# config.yaml
profile: local
database:
  host: "${DB_HOST:-localhost}"
  password: "${DB_PASSWORD}"
```

```dotenv
# .env
DB_PASSWORD=example-only
MYAPP_DATABASE__POOL__SIZE=5
```

```dotenv
# .env.local
DB_HOST=127.0.0.1
MYAPP_DATABASE__POOL__SIZE=3
```

위 입력에서 profile은 local, host는 127.0.0.1, pool.size는 3이다. OS의 `MYAPP_DATABASE__POOL__SIZE=20`이 있으면 size는 20이 된다. 생성자 주입에서는 이 객체를 그대로 인자로 전달한다. Spring의 `@Value`에 대응하는 자동 decorator 주입은 MVP 사용 경험에 포함하지 않는다.

boolean 필드는 `False`, `false`, `FALSE`, 실제 quote를 포함한 `"False"`를 모두 False로 읽는다. 문자열 필드는 대소문자·공백·quote를 자동 변경하지 않는다. 배포 도구가 host 문자열에 quote까지 주입하는 환경은 `ConfigLoader(..., env_quote_policy={"database.host": "unwrap"})`로 해당 경로만 한 겹 제거한다. 비밀번호에 quote가 실제로 필요한 경우에는 보존한다. shell이나 dotenv의 문법상 quote와 ENVVAR에 저장된 quote 문자는 구분한다.

## 우선순위와 프로파일 정책

설정 필드의 우선순위는 낮은 순서부터 다음과 같다.

```text
모델 기본값 < 기본 YAML < profile YAML < .env 바인딩
             < .env.<profile> 바인딩 < OS env 바인딩 < 명시적 overrides
```

profile 선택은 `load(profile=...) > OS PYDCONFIG_PROFILE > 기본 .env의 PYDCONFIG_PROFILE > 기본 YAML profile > 미선택`이다. 미선택 시 기본 파일만 읽는다. 실제 환경변수명과 설정 경로의 우선순위는 구분한다. `${DB_HOST}`는 YAML 값의 참조이며 `.env`의 직접 필드 변수 `MYAPP_DATABASE__HOST`가 그 YAML 값을 덮으면 OS의 `DB_HOST`가 있어도 직접 필드 값이 유지된다.

프로파일 YAML이 없다는 이유만으로 선택한 profile이 유효하다고 판단하지 않는다. 배포에서 `allowed_profiles=("local", "test", "stg", "prd")`를 지정해 오타를 거부한다. profile YAML 존재가 필요하면 `require_profile_yaml=True`를 사용한다. 설정이 환경변수만으로 완성되는 앱에는 파일 존재를 강제하지 않는다.

## Reference와 구현 선택

| Reference | 채택 내용 | 적용 범위 |
| --- | --- | --- |
| [Spring Boot](https://docs.spring.io/spring-boot/reference/features/external-config.html) | 소스 우선순위·구조화된 바인딩·시작 시 검증 | 사용 모델을 참고하며 전체 Spring 표기법 호환을 약속하지 않는다. |
| [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | BaseSettings·custom settings source | 필수 구현 기반. 단일 aggregate settings에서 사용자 정의 소스를 실행한다. |
| [Dynaconf](https://www.dynaconf.com/merging/) | 명시적 병합 정책 | MVP는 mapping 재귀 병합·list 교체로 제한한다. |
| [OmegaConf](https://omegaconf.readthedocs.io/en/latest/usage.html) | 계층형 설정·보간 | YAML 변수 보간만 채택하고 설정 간 참조는 후속 기능으로 둔다. |
| [python-dotenv](https://bbc2.github.io/python-dotenv/) | 환경을 수정하지 않는 파일 파싱 | `dotenv_values(interpolate=False)`를 사용한다. |

이미 있는 라이브러리 위에 필요한 차이만 추가한다. loader는 registry와 실행 컨텍스트를 만들고 pydantic-settings의 custom source가 bootstrap·병합·보간을 수행한다. 최종 검증도 실제 BaseSettings 생성에서 수행한다. 모델마다 별도 BaseSettings를 만들어 기본 env/dotenv 소스와 중복 로딩하지 않는다. Pydantic Settings를 선택 의존성이나 비교 후보로 두는 이전 제안은 사용자 지정에 따라 폐기했다.

## 기존 코드 이관과 호환성

기존 구현의 근거는 [최초 제안의 근거 표](reviews/initial-proposal.md#기존-구현에서-이어받을-부분)에 보존했다. 정적 소스 관찰이며 서비스 실행 검증은 아니다.

- `_root_key`를 name/path 등록으로 옮기고 `config:` wrapper는 명시적 호환 변환에서 제거한다.
- `env_prefix=""`는 경로와 정확히 일치하는 기존 변수만 보존한다. `JWT__SSO_AUTHCODE_URL`과 `sso_url_authcode`처럼 불일치하는 이름은 application bootstrap에서 명시적으로 mapping한다. alias adapter 출시 전 core가 추측하지 않는다.
- `DEFAULT_CONFIG`와 `APP_CONFIG` 두 파일의 병합은 explicit multi-YAML 기능 도입 후 이관한다. MVP만으로 기존 shared 로더 전체를 대체할 수 있다고 보지 않는다.
- 기존 validator는 순수 검증·변환만 옮긴다. 로거 변경, 클라이언트 생성 등 외부 상태 변경은 snapshot 성공 후 application bootstrap에서 실행한다.
- `unknown="ignore"`는 일부 영역의 단계적 이관에만 사용하고 무시한 경로를 보고한다. 등록하지 않은 영역의 placeholder는 평가하지 않는다.
- dotenv 누적 로딩, 미정의 placeholder 오류, strict key 검사, null·list 계약의 차이를 fixture로 확인한다.

이관 중에는 기존 로더와 새 로더를 독립적으로 실행해 비민감 설정만 비교한다. 사용 서비스에서 새 로더를 선택하는 bootstrap 변경을 되돌리는 것이 복구 방법이며 라이브러리가 원래 dotenv나 YAML을 수정하지 않는다.

## 완료와 검토의 의미

문서 리뷰 완료는 구현·호환성 검증 완료와 구분한다. MVP 완료는 R1–R14에 연결된 계약 시험, 플랫폼별 경로·환경 처리, wheel/sdist 설치, 타입 검사, 예제 실행 결과로 판단한다. 성능 수치는 측정 후 기록하며 현재 기획 단계에서 목표 처리시간을 임의로 약속하지 않는다.

리뷰의 지적·반영·재검토 결과는 [기획 리뷰](reviews/planning-review.md)와 [설계 리뷰](reviews/design-review.md)에 기록한다.
