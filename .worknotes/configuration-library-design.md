# pydconfig 문서 안내

기존 통합 제안서를 리뷰한 뒤 기획서와 상세 설계서로 분리했다. 초기 문서 리뷰를 보존하고 v1.0.0의 구현·시험·배포 기록을 별도로 연결한다.

| 문서 | 내용 |
| --- | --- |
| [기획서](product-plan.md) | 요구사항 R1–R14, 사용자 경험, MVP·후속 범위, 이관과 완료 기준 |
| [상세 설계서](technical-design.md) | API, 내부 데이터, 실행 순서, source·default·검증·snapshot의 동작 계약 |
| [기획 리뷰](reviews/planning-review.md) | 독립 기획 리뷰의 지적, 반영, 재검토 결과 |
| [설계 리뷰](reviews/design-review.md) | 구조·설정 규칙 리뷰의 지적, 반영, 재검토 결과 |
| [패키지 이름 변경](package-rename.md) | 배포명·import·저장소·실제 디렉터리 변경과 Codex 경로 전환 완료 |
| [호환성 기준](compatibility-plan.md) | Python 3.10–3.14, 의존성 baseline, 실행 가능한 기반 probe와 검증 한계 |
| [사용자 가이드](../docs/user-guide.md) | 기본 파일 예제, 이름·경로, 프로파일·환경변수·snapshot 사용 계약 |
| [설정 규칙](../docs/configuration-reference.md) | API 옵션, 파싱·병합·boolean·quote·오류 reference |
| [애플리케이션 연동](../docs/integration-guide.md) | 생성자 주입·FastAPI·테스트 격리·이관 |
| [개발 가이드](../docs/development.md) | 기반 probe·CI, 구현 후 build·설치·release 절차 |
| [Release 작업 기록](release-plan.md) | v1.0.0 요청, 배포 범위 확인, 문서·branch·검증 준비 상태 |
| [최초 제안 원본](reviews/initial-proposal.md) | 첫 리뷰의 고정 baseline; 이름 변경 전 표기를 포함하며 현재 설계와 다를 수 있음 |
