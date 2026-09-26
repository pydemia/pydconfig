# 기획 리뷰 기록

현 기획서는 v4다. 아래 기록은 기존 기획 리뷰를 보존한 것이다. boolean·quote·임의 객체 타입 관련 R11–R13의 독립 설정 규칙 검토는 [설계 리뷰의 v3 기록](design-review.md#v3-추가-요구의-제한-리뷰)에 구분했다. Python·Kubernetes 관련 v4 추가분은 [호환성 기록](../compatibility-plan.md)에 따른 기반 검사이며 이 기획 리뷰의 승인 범위에 자동 포함하지 않는다.

작성일: 2026-09-26. 담당: 독립 기획·요구사항 리뷰 agent. 문서 정리는 주 담당자가 수행했다. 검토 대상은 라이브러리 기획이며 실행 코드·배포를 검토한 결과가 아니다.

## 검토 기준

최초 baseline은 [initial-proposal.md](initial-proposal.md)이며 SHA-256은 `662877e0cac8f8aeb59d669bfa033bcbf3caa8a20d917a2bdf734552db779ab5`다. 원본을 수정하지 않고 지적 위치를 보존했다. 재검토 대상은 [기획서](../product-plan.md)와 [상세 설계서](../technical-design.md)다.

등급의 의미는 High=구현 착수 전에 해결할 동작 계약 문제, Medium=호환성·사용성·지원 범위 보완, Low=선택적 개선이다. 자동 코드 리뷰의 P1/P2 또는 실제 운영 장애 severity로 환산하지 않는다.

원래 요구와 인수 기준을 대조했으며 name별 nested 설정, env override, YAML placeholder, dotenv/profile 기본 요구는 최초 문서에 반영되어 있었다.

## 최초 지적과 반영

| ID | 등급 | 원본 행 | 입력·영향 | 반영 내용 |
| --- | --- | --- | --- | --- |
| P1 | Medium | 488, 492 | JWT__SSO_AUTHCODE_URL은 모델의 sso_url_authcode와 경로가 다르므로 env_prefix를 비워도 자동 바인딩되지 않는다. 기존 os.getenv를 제거하면 배포 변수 일부가 읽히지 않을 수 있다. | legacy→정규 이름 대응표와 source별 호환 변환을 명시했다. 정규·legacy 중복은 conflict 오류다. dotenv alias가 필요한 서비스는 adapter 지원 뒤 이관한다. |
| P2 | Medium | 39, 488 | 기존 logger 변경 validator를 유지하면 다른 모델 검증 실패나 snapshot 재검증 중 전역 로거가 바뀐다. | 보존할 validator를 순수 검증·변환으로 제한하고 logger·클라이언트 초기화는 전체 snapshot 성공 뒤 application bootstrap으로 이동하도록 정했다. |

P1의 실제 기존 소스는 [JWTConfig](/Users/a09255/git/template-backend/template_backend_sample/mainapp/core/config.py:143), P2는 [set_log_level](/Users/a09255/git/template-backend/template_backend_sample/mainapp/core/config.py:192)에서 확인했다. 이는 해당 작업 트리의 정적 근거이며 이관 후 동등성을 실행 확인한 것은 아니다.

## 재검토 결과

독립 기획 담당자가 수정 기획서와 상세 설계서를 다시 검토했다. P1·P2는 문서 수준에서 해결됐으며 R1–R9·MVP 범위에 추가로 보고할 중요한 요구사항 공백은 발견하지 못했다.

dotenv 내부 보간을 후속 범위로 둔 것은 원래 YAML `${ENVVAR}` 요구와 충돌하지 않는다. multi-YAML·alias·FastAPI adapter의 지원 시점과 MVP만으로 기존 shared 로더 전체를 대체할 수 없다는 제한도 명시됐다.

판정은 **검토한 문서 범위에서 구현 전 차단 계약 미발견**이다. 구현 단계에서는 설계서 G1–G9와 해당 서비스의 변수 대응표·bootstrap 복구 절차를 실제 fixture로 확인해야 한다. 이 판정은 실행 동작 또는 호환성 승인으로 사용하지 않는다.

사용자의 추가 지정인 pydantic·pydantic-settings·python-dotenv 기반은 v2의 필수 의존성과 실제 BaseSettings/custom source 구조에 반영했다. 독립 기획 리뷰가 이를 재확인했다. python-dotenv를 대체할 수 있다고 읽힐 문구도 제거하고 해당 기반을 유지하는 사전 검증 adapter로 한정했다. 추가 지정은 기획서 R10으로 추적한다.
