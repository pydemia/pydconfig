# pydconfig

Python 애플리케이션의 이름별 설정, 프로파일, 환경변수 주입을 위한 configuration library를 설계하고 있습니다.

PyPI 배포명, Python import 이름, 저장소 이름은 모두 `pydconfig`입니다. 기본 환경변수 접두사는 `PYDCONFIG_`, 프로파일 선택 변수는 `PYDCONFIG_PROFILE`로 설계합니다.

기본 구현은 pydantic, pydantic-settings, python-dotenv를 기반으로 합니다.

[기획서](.worknotes/product-plan.md)와 [상세 설계서](.worknotes/technical-design.md)에 요구사항, API, 설정 우선순위, 프로파일·dotenv 처리, 주입과 검증 계약을 정리했습니다. [리뷰 기록과 최초 제안](.worknotes/configuration-library-design.md)도 함께 보관합니다.

현재 구현 전 단계이며 문서의 API는 제안입니다.
