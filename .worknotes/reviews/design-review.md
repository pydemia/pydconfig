# 설계 리뷰 기록

작성일: 2026-09-26. 담당: 독립 구현 구조 리뷰 agent, 독립 설정 규칙 리뷰 agent. 주 담당자는 두 리뷰의 중복 지적을 합치고 문서에 반영했다. 런타임 구현 승인 또는 출시 승인을 의미하지 않는다.

## 검토 기준

최초 검토는 [고정 원본](initial-proposal.md)을 대상으로 수행했다. SHA-256은 `662877e0cac8f8aeb59d669bfa033bcbf3caa8a20d917a2bdf734552db779ab5`다. 재검토 대상은 [상세 설계서](../technical-design.md)와 [기획서](../product-plan.md)다.

High는 입력 결과가 하나로 결정되지 않거나 구현 방식에 따라 요구한 동작이 깨지는 계약 문제다. Medium은 지원 범위·진단·이관을 보완해야 할 조건부 문제다. 확인된 런타임 버그의 심각도를 주장하는 등급이 아니다.

## 최초 지적과 반영

| ID | 등급 | 원본 행 | 최소 조건과 문제 | 수정 계약 |
| --- | --- | --- | --- | --- |
| D-R1 | High | 373 | after-validator가 value 2→4로 바꾼 뒤 다른 field를 override하면 최종 모델을 replay하는 구현에서 4→8로 재변환된다. | 검증 전 ResolvedInput과 validated output을 분리해 저장하고 input만 replay한다. |
| D-R2 | High | 318 | validated-data factory를 사전 materialize하는 시점과 nested partial override의 처리 순서가 없다. default model instance의 변환 입력도 복원할 수 없다. | 데이터 의존 factory·model instance default는 거부하고 raw default만 지원한다. exact ConfigModel class factory는 raw schema 확장으로 정의했다. load별 cache를 사용한다. |
| D-R3 | High | 266, 295, 301 | nullable list의 env null은 JSON decoding에 따르면 None, scalar null 금지 규칙에 따르면 오류다. | nullable 복합 타입의 JSON null은 None, scalar env null은 문자열로 검증한다. container 내부 null은 element schema로 결정한다. |
| D-R4 | High | 258, 265, 282, 295 | dotenv JSON에 missing placeholder가 있고 OS leaf가 덮는 경우 보간·JSON·merge 순서에 따라 실패 여부가 다르다. 치환값의 따옴표가 JSON 구조도 바꿀 수 있다. | MVP의 dotenv·OS는 literal. 보간은 최종 YAML 값에만 수행하고 삽입 문자열은 재보간하지 않는다. dotenv 보간은 후속 범위로 이동했다. |
| D-R5 | High | 301, 312, 318 | custom default pool.size=20을 null로 지운 뒤 OS timeout만 추가하면 size=20 복원/child default 10/오류 중 어느 결과인지 없다. | null/scalar는 subtree 삭제 장벽. 뒤 mapping이 열리면 지워진 custom default가 아닌 child schema default 10을 채운다. |
| D-R6 | Medium | 295 | str 또는 list union에 JSON처럼 생긴 env를 넣으면 decoding 여부에 따라 선택 branch가 다르다. | supported schema를 고정하고 다중 branch union·recursive/arbitrary/alias 선언을 register에서 거부한다. |
| D-R7 | Medium | 282, 291, 316 | ignore할 legacy root의 missing placeholder가 전체 tree 보간에서 실패할 수 있다. | unknown prune를 보간·모델 검증 전에 수행한다. 파일/JSON 문법 검사는 별도 유지한다. |
| D-R8 | Medium | 297, 435, 503 | bool만 수정한 YAML parser가 0012를 int, 날짜를 date로 바꾸면 string field의 결과가 달라진다. | decimal·float·leading zero·timestamp·null·key·tag 규칙을 YAML subset 표에 고정했다. |
| D-R9 | Medium | 390–394 | validator가 secret에서 공개 문자열을 만들면 공개 flag와 secret taint의 우선순위·전파를 보장할 수 없다. | explain은 입력 출처만 설명하고 output은 opaque-validation으로 구분한다. MVP에서 값 출력 dump를 제거했다. |

구조 리뷰의 A4와 설정 규칙 리뷰의 S6는 D-R9로 합쳤다. 서로 다른 리뷰가 같은 문제를 언급했다는 이유로 건수나 severity를 올리지 않았다.

## 재검토에서 추가된 지적

| ID | 등급 | 수정 설계의 조건 | 반영 내용 |
| --- | --- | --- | --- |
| D-R10 | High | list[ConfigModel]의 element factory cache와 override로 새 element가 생기는 경우가 미정 | MVP container 원소를 scalar·nullable scalar로 제한했다. model/container 원소는 후속 계약으로 분리했다. |
| D-R11 | Medium | before-validator가 전달받은 dict를 수정하면 stored raw input도 오염될 수 있음 | v2에서는 custom source가 AggregateSettings에 disposable deep copy를 전달하고 output 또는 mutated validation input을 보관 입력에 역반영하지 않는다. |
| D-R12 | Medium | Windows os.environ을 plain dict로 복사하면 대소문자 비구분 조회가 사라짐 | OS/environ 대문자 index와 dotenv exact lookup을 구분하고 OS 우선순위를 정의했다. 실제 Windows 검증은 구현 gate다. |
| D-R13 | High | 같은 source의 root JSON·nested JSON을 iteration 순으로 펼치면 값이 달라짐 | 경로 깊이 오름차순으로 root→nested JSON을 적용하고 마지막 scalar leaf를 적용한다. |
| D-R14 | Medium | scalar 아래 잘못된 env descendant를 ignore 뒤 제거하면 lower scalar가 이미 사라질 수 있음 | 해당 입력은 tree 삽입 전 binding 구조 오류이며 unknown 정책과 무관하게 거부한다. |
| D-R15 | Medium | 등록 path가 database.primary일 때 가상 ancestor DATABASE의 전체 JSON 지원 여부가 없음 | YAML grouping은 허용하지만 whole-env JSON은 실제 등록/nested model path에만 허용한다. 가상 ancestor 전체 값은 binding 구조 오류로 거부한다. |
| D-R16 | Medium | cli_parse_args=False에서도 CLI source가 구성되고 framework가 자동 default source를 추가함 | CLI는 None으로 비활성화하고 custom hook 반환과 자동 DefaultSettingsSource를 구분했다. required aggregate의 자동 default 결과는 {}여야 한다. |
| D-R17 | Medium | before-validator가 materialized default field를 삭제하면 native Pydantic factory가 다시 호출될 수 있음 | loader-controlled factory cache 보장으로 한정하고 factory-backed field 삭제·validator 내부 모델 재생성은 MVP 미지원으로 명시했다. |

## 확인한 기술 근거와 한계

주 담당자의 로컬 Python/Pydantic 2.13.0에서 nested default 일부가 타입 기본값으로 돌아가는 동작, bool yes 허용, validated-data factory의 data 요구, 기본 PyYAML의 on/date/0012 변환을 실행 확인했다.

독립 구조 리뷰 agent는 Pydantic 2.13.0에서 after-validator의 2→4→8 replay, before-validator 입력 dict 변경, container element factory의 재호출 사례를 실행 확인했다. 새 라이브러리 구현이나 전체 contract suite의 실행 결과가 아니다.

default factory와 FieldInfo는 [Pydantic 공개 API](https://docs.pydantic.dev/latest/api/fields/), source/nested default 대안은 [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/), Windows 환경 동작은 [Python os.environ](https://docs.python.org/3/library/os.html#os.environ)을 확인했다. Windows 실제 실행은 수행하지 않았다.

사용자 추가 지정 후 pydantic·pydantic-settings·python-dotenv를 필수 기반으로 고정했다. 단일 aggregate BaseSettings와 load별 custom source가 실제 소스 실행·검증을 담당하도록 v2를 작성하고 다시 리뷰했다. 로컬 pydantic 2.13.0 / pydantic-settings 2.13.1에서 source와 nested validator가 각각 한 번 호출되고 원래 raw 입력은 유지되는 것을 주 담당자와 독립 구조 담당자가 확인했다.

동일 로컬 버전에서 cli_parse_args=False가 CLI source를 생성하고 DefaultSettingsSource가 자동 추가되는 동작을 독립 구조 담당자가 확인했다. 설계는 CLI 비활성을 None으로 변경하고 자동 default source의 빈 결과를 gate로 구분했다. upstream source debug는 로컬 설치 버전과 최신 공식 문서의 동작이 달라 전체 보호 검증은 지원 버전별 G8에 남겼다.

## v2 최종 재검토

독립 구조 담당자는 C1까지 반영된 v2를 재확인했고 담당 범위의 미해결 High·Medium 지적이 없으며 **prototype 구현을 시작할 수 있음**으로 판정했다. 독립 설정 규칙 담당자도 T1–T5·default callback 경계가 해결됐고 source 우선순위·null 장벽·unknown 제거·YAML 보간·입력 replay가 유지됨을 확인했다.

이 판정은 문서 계약에 한정한다. 라이브러리 구현, 기존 서비스 호환성, Windows 실제 동작, 전체 G1–G9, debug 활성 버전의 비밀값 보호는 구현 단계의 검증으로 남아 있다. 구현에서 계약을 충족하지 못하면 해당 문서와 리뷰 상태를 먼저 갱신한다.

## v3 추가 요구의 제한 리뷰

사용자가 임의 객체 타입 지원 제외, boolean 대소문자 처리, 실제 ENVVAR quote 처리를 지정했다. 기획 R11–R13과 설계 D8–D9에 반영했다. 문자열·SecretStr은 실제 quote를 기본 보존하고 필드별 `env_quote_policy`로 unwrap을 선택하는 기준이다. 이 추가분은 독립 설정 규칙 담당자가 리뷰했으며 v2 전체 구조·기획 리뷰를 다시 수행한 결과는 아니다.

| ID | 등급 | 조건과 지적 | 반영·재확인 |
| --- | --- | --- | --- |
| Q1 | Medium | str 필드에 unwrap을 선택하고 실제 입력이 quote 한 글자이면 첫·끝 문자 비교만으로 wrapper라고 오인할 수 있음 | 길이 2 이상과 양끝의 같은 ASCII quote 조건을 명시했다. 단일 quote 보존을 예시 표와 G10에 추가했고 독립 담당자가 재확인했다. |

독립 담당자는 boolean token 계약, 정규화 전 fallback 판정, python-dotenv 파싱 후 실제 값의 처리, JSON 내부 quote 보존, 전체·부분 YAML 보간, 완료 leaf의 replay, 새 Python override 비정규화가 일관됨을 확인했다. Q1 반영 후 **v3 추가 요구의 검토 범위에 미해결 High·Medium 지적은 없다**. 실제 라이브러리의 G10은 아직 실행하지 않았으며 구현 단계의 검증으로 남아 있다.

주 담당자는 로컬 Pydantic 2.13.0이 True/true/TRUE와 False/false/FALSE를 허용하지만 quote·바깥 공백이 남은 boolean을 거부하는 동작을 확인했다. python-dotenv 1.2.1은 파일 문법의 quote를 제거하고 내부의 실제 quote와 공백은 보존했다. 독립 담당자도 dotenv의 quoted-empty와 내부 quote를 확인했다. 이 실험은 기반 라이브러리 관찰이며 pydconfig의 구현 시험 결과가 아니다. 근거는 [Pydantic boolean 문서](https://docs.pydantic.dev/latest/api/standard_library_types/#booleans)와 [python-dotenv 파일 형식](https://bbc2.github.io/python-dotenv/#file-format)이다.
