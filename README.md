# pydconfig

Python 애플리케이션의 이름별 설정, 프로파일, 환경변수 주입을 위한 configuration library를 설계하고 있습니다.

PyPI 배포명, Python import 이름, 저장소 이름은 모두 `pydconfig`입니다. 기본 환경변수 접두사는 `PYDCONFIG_`, 프로파일 선택 변수는 `PYDCONFIG_PROFILE`로 설계합니다.

기본 구현은 pydantic, pydantic-settings, python-dotenv를 기반으로 합니다.

지원 목표는 표준 CPython 3.10–3.14이며 개발 기준은 Python 3.14.7입니다. Kubernetes 호환성 기준은 v1.37.1의 ConfigMap·Secret 환경변수 주입입니다. [지원 버전과 검증 범위](.worknotes/compatibility-plan.md), [실행 가능한 환경 주입 예제](examples/kubernetes/env-injection.yaml)를 함께 제공합니다.

[기획서](.worknotes/product-plan.md)와 [상세 설계서](.worknotes/technical-design.md)에 요구사항, API, 설정 우선순위, 프로파일·dotenv 처리, 주입과 검증 계약을 정리했습니다. [리뷰 기록과 최초 제안](.worknotes/configuration-library-design.md)도 함께 보관합니다.

현재 구현 전 단계이며 문서의 API는 제안입니다.

기반 라이브러리의 공개 API와 Kubernetes manifest 스키마는 다음 명령으로 확인할 수 있습니다. 이 검사는 pydconfig 구현의 계약 시험을 대신하지 않습니다.

```bash
python -m pip install -r requirements/compatibility.txt
python scripts/check_compatibility.py
```
