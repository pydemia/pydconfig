# v1.0.0 구현 검토

검토 대상: origin/release의 5797029 이후 src/pydconfig 구현, pyproject.toml, CI, 계약 시험과 사용자 문서. 날짜: 2026-09-26. 최초 기획·설계 리뷰 원본을 수정하지 않고 실제 source와 실행 시험을 기준으로 검토했다. 이번 기록은 기존 리뷰팀의 새 승인이나 외부 보안 감사 결과가 아니다.

## 재현한 문제와 수정

| Finding priority | 발생 조건·영향 | 수정과 시험 |
| --- | --- | --- |
| P2 Warning | 각각 한도를 만족한 여러 source를 합치면 전체 입력 tree·env 누적 한도를 초과할 수 있었다. | 최종 병합 tree·replay·JSON 전개 후 depth/node 검사, dotenv+profile+OS 후보의 누적 UTF-8 예산 검사. test_review_regressions.py에서 source 합계·replay 경계를 확인한다. |
| P2 Warning | 접두사 밖의 큰 변수 또는 반복 보간이 최종 문자열을 만든 뒤에야 한도를 초과했다. | 각 삽입 전에 보간 출력 예산을 검사한다. 단일 큰 참조와 반복 확장 실패를 확인한다. |
| P2 Warning | YAML whole-model placeholder를 JSON으로 펼친 하위 필드 explain에서 참조 변수가 빠졌다. | decoding 결과의 각 하위 node에 참조 source를 전달한다. database.host의 DB 참조를 확인한다. |
| P2 Warning | AnyUrl subclass만 허용하면 공개 PostgresDsn 등의 multi-host URL 타입을 등록할 수 없었다. | 공개 multi-host DSN 타입을 허용하고 typed default·환경 문자열을 검증한다. |

조회의 잘못된 경로 문법은 ConfigLookupError로 정리했다. ConfigModel의 Pydantic pretty-print protocol도 값을 반환하지 않으며 computed property를 평가하지 않는다. frozen assignment 실패 시험은 구체적인 ValidationError를 확인한다.

## 확인한 범위

Correctness는 source 순서, null/scalar 장벽, profile 후보·재선언, YAML subset, JSON 오류, quote·boolean, factory·validator 실행과 독립 replay를 확인했다. Security는 입력값이 parser/validator 오류·exception chain·repr·provenance·Settings debug 로그로 출력되지 않는 계약과 배포 파일의 credential pattern을 검사했다. 애플리케이션이 직접 값을 출력하거나 사용자 callback이 logger·외부 상태를 변경하는 행동을 차단하는 sandbox를 제공하지 않는다.

Maintenance와 Setting은 public Settings source·FieldInfo 기반, 기본 native source/CLI 제외, 파일 부재 정책, dotenv parser adapter의 의존성 범위와 CI, 문서의 구현 전 표현을 확인했다. Optimization은 구현된 입력 예산·depth/node 한도를 확인했으며 성능 benchmark나 처리시간 보장은 수행하지 않았다. Review History는 기존 설계의 R1–R14/G1–G11과 연결하며 과거 probe-only 성공을 현재 구현 성공으로 재사용하지 않았다.

## 실행 증거

macOS CPython 3.14.4: 계약 시험 173개 통과, mypy 15개 implementation 파일 통과, Ruff 통과. wheel·sdist build와 파일 구성 검사를 통과했다. 최초 리뷰 원본 SHA256은 662877e0cac8f8aeb59d669bfa033bcbf3caa8a20d917a2bdf734552db779ab5로 보존됐다. 플랫폼 CI·설치·배포의 최종 결과는 [release 기록](../release-plan.md)에 기록한다. 이 시점의 로컬 시험만으로 원격 7개 job·release·PyPI 완료를 주장하지 않는다.

최종 플랫폼 확인: code/test commit 790a3d05790fe81ef462bb4134a33f0f28da7ab1의 [CI 36245893892](https://github.com/pydemia/pydconfig/actions/runs/36245893892) 7개 job이 모두 success다. 각 job은 설치한 wheel에 계약 시험·예제·타입·형식·metadata·의존성 검사를 실행한다. 배포 직전 문서 기록 변경은 실행 code/test/workflow를 바꾸지 않는다. 검토한 범위에서 남은 기능 결함은 발견하지 않았다. PyPI/GitHub 외부 게시 완료는 해당 API와 다운로드 검증으로 별도 판단한다.
