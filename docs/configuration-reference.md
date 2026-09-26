# 설정 규칙

pydconfig 1.0.0의 공개 API와 입력 처리 규칙이다. 코드 예제의 기반 모델 선언은 [사용자 가이드](user-guide.md)에 있다.

## ConfigLoader 옵션

모든 생성자 인자는 keyword-only다.

```python
ConfigLoader(
    root_dir=None,
    yaml_file=None,
    env_prefix="PYDCONFIG_",
    dotenv=True,
    allowed_profiles=None,
    require_profile_yaml=False,
    unknown="error",
    env_quote_policy=None,
)
```

| 옵션 | 의미 |
| --- | --- |
| `root_dir` | `str` 또는 `Path`. 생략하면 loader 생성 시 cwd를 절대 경로로 고정한다. |
| `yaml_file` | 명시적 `.yaml`·`.yml` 경로. 상대경로는 root_dir 기준이다. 생략하면 `config.yaml`만 자동 탐색한다. |
| `env_prefix` | 비어 있거나 `[A-Z][A-Z0-9_]*_` 형태. 기본 `PYDCONFIG_`. |
| `dotenv` | False이면 `.env`·profile dotenv 읽기와 dotenv profile 후보를 제외한다. |
| `allowed_profiles` | 허용 profile 문자열 목록. 목록 밖 profile은 오류다. |
| `require_profile_yaml` | True이면 선택 profile과 그 YAML variant의 존재가 필수다. |
| `unknown` | `error` 또는 `ignore`. 최종 effective tree에서 등록되지 않은 경로를 처리한다. |
| `env_quote_policy` | 실제 필드·모델·container 경로에서 `preserve` 또는 `unwrap`을 선택한다. |

`root_dir`은 loader를 만든 후 cwd가 바뀌어도 유지한다. 설정 모델의 일반 Path 필드 상대경로를 root_dir로 자동 변환하지 않는다.

## 등록·로딩·조회

| API | 계약 |
| --- | --- |
| `register(name, model, path=None)` | model은 ConfigModel subclass. 생략한 path는 name. 충돌·미지원 schema를 거부한다. |
| `load(profile=None, environ=None, overrides=None)` | keyword-only. 등록 설정 전체 검증에 성공하면 새 ConfigSnapshot을 반환한다. |
| `snapshot.profile` | 선택한 profile 또는 None. |
| `snapshot.get(name, model)` | 등록 타입과 정확히 일치해야 한다. 검증 결과의 깊은 복사본을 반환한다. |
| `snapshot.explain(path)` | 값을 제외한 입력 provenance를 반환한다. |
| `snapshot.source_report()` | source 읽기 상태와 무시한 경로를 반환한다. |
| `snapshot.with_overrides(values)` | 외부 source를 다시 읽지 않고 Python override를 합쳐 새 snapshot을 검증한다. |

`environ=None`은 실제 OS 환경 복사본, `{}`는 빈 환경이다. `profile=None`은 외부 후보를 계속 검사한다는 뜻이며 자동 profile을 강제로 끄는 sentinel은 없다. `overrides`는 YAML root와 같은 mapping 구조이며 profile을 변경하지 않는다.

같은 loader에서 등록을 끝낸 후 독립 load를 동시에 수행할 수 있다. register와 load를 동시에 호출하는 사용은 지원하지 않는다. 기존 snapshot은 나중의 register 영향을 받지 않는다.

## Source 우선순위와 병합

| 낮은 순서 | Source |
| --- | --- |
| 1 | schema의 raw 기본값 |
| 2 | 기본 YAML |
| 3 | 선택한 profile YAML |
| 4 | 기본 `.env`의 직접 필드 바인딩 |
| 5 | `.env.<profile>`의 직접 필드 바인딩 |
| 6 | OS/environ의 직접 필드 바인딩 |
| 7 | 명시적 overrides |

mapping끼리는 key별로 재귀 병합한다. list·tuple은 전체 교체한다. scalar와 실제 null도 전체 교체한다. 빈 mapping은 낮은 mapping의 값을 지우지 않는다.

null 또는 scalar가 낮은 subtree를 덮으면 기존 값이 삭제되는 장벽이 된다. 뒤 source가 mapping을 만들더라도 삭제된 custom default·YAML은 복원하지 않는다. 부족한 child 값은 child schema의 기본값으로 채운다.

예를 들어 child schema size=10, 부모의 custom default size=20인 경우:

```text
부모 custom default: pool={size:20, timeout:5}
YAML:                pool=null
OS:                  pool.timeout=1
최종 검증 결과:      pool={size:10, timeout:1}
```

child schema에도 필수 값이 없으면 missing 오류다. 실제 None에는 child 기본값을 채우지 않는다.

## Profile과 파일

profile 문법은 `[a-z][a-z0-9_-]*`다. 선택 우선순위는 명시적 load 인자, OS `PYDCONFIG_PROFILE`, 기본 `.env`의 같은 변수, 기본 YAML의 `profile` 순서다. 존재하는 빈 후보와 잘못된 선언은 오류이며 낮은 후보로 fallback하지 않는다. 낮은 우선순위 선언도 문법·타입을 검사한다.

| 파일 | 부재·선택 규칙 |
| --- | --- |
| 자동 기본 YAML | `root_dir/config.yaml`; 없으면 생략 |
| 명시적 yaml_file | 없으면 오류 |
| profile YAML | `config.yaml` → `config.<profile>.yaml`, `service.yml` → `service.<profile>.yml` |
| profile YAML 부재 | 기본은 생략, require_profile_yaml=True이면 오류 |
| dotenv | `.env`와 선택한 `.env.<profile>`; 없으면 생략 |
| dotenv=False | 두 파일을 읽지 않음 |

자동 탐색은 `config.yml`을 추가 탐색하지 않는다. 존재하는 optional 파일의 읽기·encoding·문법 오류는 실패한다. UTF-8과 UTF-8 BOM을 허용한다. 파일별로 한 번 읽으며 여러 파일이 같은 시점의 filesystem snapshot이라는 보장은 없다.

profile은 string literal이어야 하며 보간하지 않는다. profile 전용 YAML·dotenv에서는 profile 재선언을 거부한다. `PYDCONFIG_PROFILE`은 env_prefix와 독립된 예약 제어 변수다.

## Boolean과 quote

bool은 실제 bool, 정수 0/1, 문자열 true/false/1/0만 허용한다. 문자열은 앞뒤 ASCII 공백을 제거한 뒤 대소문자를 구분하지 않는다. `bool("False")`처럼 truthiness로 해석하지 않는다. Pydantic 단독의 넓은 token 집합과 달리 `yes/no/on/off`는 지원하지 않는다.

아래 값은 shell 코드가 아닌 **파싱 후 환경 mapping의 실제 문자**다.

| 실제 문자 | 타입·정책 | 결과 |
| --- | --- | --- |
| `True`, `true`, `TRUE`, `tRuE` | bool 기본 | True |
| `False`, `false`, `FALSE`, `fAlSe` | bool 기본 | False |
| `"False"`, `'TRUE'`, `  " false "  ` | bool 기본 | False, True, False |
| `""True""` | bool 기본 | 한 겹만 제거하고 남은 quote 때문에 오류 |
| `"42"` | int 기본 | 42 |
| `'["a", "b"]'` | list[str] 기본 | JSON의 내부 quote를 보존하여 해석 |
| `"False"` | bool preserve | 오류 |
| `"abc"` | str/SecretStr 기본 | quote를 포함한 문자열 |
| `"abc"` | str unwrap | abc |
| `"abc`, `"abc'`, 단일 `"` | str unwrap | 그대로 보존 |
| `"null"` | nullable int | 오류; scalar 문자열 null을 None으로 만들지 않음 |
| `"null"` | nullable list | wrapper 후 JSON null을 None으로 해석 |
| `""` | bool / str 기본 | bool은 오류 / str은 quote 두 글자 보존 |

기본 smart wrapper 제거는 OS·dotenv의 직접 바인딩과 YAML 전체 placeholder로 가져온 **bool·숫자·복합 JSON**에 적용한다. 먼저 바깥 ASCII 공백을 제거하고 양끝의 일치하는 ASCII 작은따옴표·큰따옴표 한 쌍을 한 번만 제거한다.

text-like 타입(str, SecretStr, Path, URL, string Enum·Literal)은 기본 보존한다. 명시적 `unwrap`에서는 문자열의 정확한 첫·끝 문자로 wrapper를 판별하고 공백을 제거하지 않는다. 내부 quote·backslash를 별도 unescape하거나 shell parsing하지 않는다. JSON은 정상 JSON decoder만 사용한다.

`env_quote_policy`는 조회 name이 아닌 설정 path를 사용한다. 없는 path, 가상 ancestor, container 원소 path는 거부한다. 모델·container path의 정책은 전체 env JSON 문자의 wrapper만 처리하며 내부 원소에는 반복 적용하지 않는다.

`prefix-${VAR}-suffix`처럼 부분 보간에서는 기본 smart 정책이 참조 문자를 보존한다. 명시적 unwrap은 참조 환경값에만 적용하며 YAML literal 부분은 바꾸지 않는다. 전체 placeholder fallback은 YAML literal이므로 환경 wrapper 제거를 적용하지 않는다.

fallback의 unset·empty 판단은 quote 제거 전이다. OS의 실제 quote 두 글자 `""`는 non-empty이므로 fallback하지 않는다. `.env FLAG=""`는 dotenv 문법 파싱 후 빈 문자열이어서 fallback한다. 기존 snapshot 입력은 replay에서 다시 정규화하지 않는다. 새 Python override에도 env quote 제거를 적용하지 않는다.

## 지원 타입

| Schema | 지원 입력 |
| --- | --- |
| str, SecretStr | 문자열; 숫자·null을 임의 추측하지 않음 |
| bool | 위의 고정 token 집합 |
| int, float | Pydantic 검증·제약; float NaN/Infinity는 거부 |
| Path, URL, string Enum, scalar Literal | 공개 Pydantic 타입 검증 |
| nested ConfigModel | mapping, 고정 nested env 경로 |
| list[S], tuple[S, ...], dict[str, S] | S는 지원 scalar 또는 nullable scalar; YAML·Python container 또는 env JSON |
| T 또는 None | 지원 타입의 optional; 실제 None 허용 |
| Annotated | 지원 타입의 Pydantic 제약 metadata |

Any, 다중 branch union, recursive model, 일반 BaseModel nested, dataclass, 임의 객체·core-schema 변환, container 안의 model·container, 고정 길이 heterogeneous tuple, set·bytes, non-string dict key는 거부한다. alias·validation_alias·alias_generator도 거부한다.

`arbitrary_types_allowed=False`, `extra="forbid"`, `frozen=True`, `validate_default=True`를 유지한다. 이를 완화한 ConfigModel subclass는 거부한다. frozen 모델의 list·dict는 Python 수준에서 수정 가능하지만 get의 깊은 복사로 원본 snapshot과 다른 get 결과를 보호한다.

## YAML·dotenv·JSON 형식

YAML은 root mapping, 문자열 key, 단일 document만 허용한다. duplicate key, explicit tag(`!!str` 포함), anchor·alias, merge key `<<`는 거부한다. pydconfig 전용 SafeLoader subclass를 사용하여 전역 PyYAML 동작은 바꾸지 않는다.

| YAML 표기 | Node |
| --- | --- |
| true, false | 소문자 표기만 implicit bool |
| null, ~, 빈 값 | None |
| 12, -12, 0 | JSON식 십진수 int |
| 1.5, 1e3 | finite float |
| 0012, 0x10, 1:20, on, yes, 날짜 | 문자열 |
| quoted scalar | 문자열 |

YAML에서 `TRUE`는 문자열로 읽은 뒤 bool 필드의 lexical 규칙으로 True가 될 수 있다. str 필드에서는 `TRUE` 그대로다. YAML parser가 값의 타입을 바꾼 뒤 field별 복원을 추측하지 않는다.

dotenv는 python-dotenv의 문법으로 읽고 내부 보간은 비활성화한다. duplicate key, 문법 오류와 값 없는 `KEY`는 실패한다. `KEY=`는 빈 값이며 `export KEY=x`, 문법 quote·개행은 parser 지원 문법을 따른다. OS 환경을 수정하지 않는다.

JSON은 duplicate key와 NaN/Infinity를 거부한다. 복합 타입의 최상단 scalar는 거부하며 nullable 복합 타입의 JSON null만 None으로 허용한다. 구조를 펼쳐야 하는 JSON의 문법 오류는 상위 source에 가려져도 실패한다. scalar lexical 검증은 최종 winner에만 수행한다.

## Unknown과 입력 한도

`unknown="error"`는 등록되지 않은 최종 경로를 거부한다. `ignore`는 해당 subtree를 제거하고 경로만 보고하며 보간·최종 타입 검증을 하지 않는다. 파일 파싱·JSON 문법 오류까지 숨기지 않는다.

알려진 scalar·container 아래 env descendant는 unknown과 별도의 구조 오류다. string host 아래 `HOST__TYPO`, list 아래 `HOSTS__0`는 ignore로 허용되지 않는다. dict의 동적 key는 JSON 안에서 대소문자를 보존한다.

| 입력 | 기본 한도 |
| --- | --- |
| YAML·dotenv 파일 | 각 1 MiB |
| YAML node·병합된 입력 node | 각각 10,000개 |
| 입력 tree·JSON depth | 32 |
| 기본·profile dotenv와 OS의 바인딩 후보 누적 크기 | key와 값의 UTF-8 합계 1 MiB |
| YAML 보간 결과 | 문자열마다 UTF-8 1 MiB |
| JSON 문자열 | 64 KiB |
| profile·경로 후보 길이 | 128자 |

override와 replay에도 입력 node·depth 한도를 적용한다. 보간으로 생성한 JSON과 전체 병합 결과도 검사한다. 처리 속도나 성능 수치를 보장하는 한도는 아니다.

## 오류와 진단

| 예외 | 주된 원인 |
| --- | --- |
| ConfigRegistrationError | 이름·경로 충돌, 미지원 schema·정책 |
| ConfigSourceError | 파일 읽기·파싱, JSON·구조·한도 오류 |
| ConfigProfileError | profile 선언·문법·허용 목록 오류 |
| ConfigInterpolationError | 미정의 참조, 지원하지 않는 placeholder 문법 |
| ConfigValidationError | lexical 해석·모델 검증 실패 |
| ConfigLookupError | 없는 name/path, get의 타입 불일치 |

오류에는 path·source·정규화한 reason code와 가능한 위치 정보만 담는다. parser 원문 snippet, validator message와 input·ctx, 원본 exception chain은 노출하지 않는다. 임의 사용자 callback의 message를 그대로 출력하지 않는다.

출처 진단의 `defined_at`, `references`, `shadowed`는 검증 입력을 설명한다. null 장벽·schema fallback을 구분하며 출력은 `opaque-validation`으로 표시한다. custom serializer·computed property를 진단을 위해 실행하지 않는다. source report의 파일 상태는 `loaded`, `skipped-missing`, `disabled`로 구분한다.

진단 객체는 immutable dataclass다. `SourceRef(kind, name, line, column)`에서 name은 파일 경로·환경변수명·기본값 경로이며 line과 column은 확보된 경우 1부터 시작한다. `FieldExplanation`은 `path`, `defined_at`, `references`, `shadowed`, `steps`, `output`을 제공한다. `SourceReport`는 `sources`, `ignored_paths`, `noncanonical_variables`를 제공한다. `ConfigError.issues`는 `ConfigIssue(code, path, source, expected)`의 tuple이다. 위치와 식별자는 메타데이터이며 설정 원문 값은 포함하지 않는다.

```python
from dataclasses import asdict

diagnostic = asdict(snapshot.explain("database.pool.size"))
assert diagnostic["output"] == "opaque-validation"
```

값 출력 dump API는 제공하지 않는다. 애플리케이션이 get으로 받은 값을 직접 출력하는 행동까지 차단하지 않는다. Settings debug 활성 상태의 비밀값 유출 여부는 의존성별 release gate에서 검증한다.
