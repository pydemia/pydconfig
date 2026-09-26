# Python 호환성 기준

확인일: 2026-09-26. 지원 목표는 표준 CPython 3.10–3.14다. 라이브러리는 pydantic·pydantic-settings·python-dotenv를 필수 기반으로 사용하며 YAML 파싱에는 PyYAML을 사용한다.

## 버전과 지원 목표

| 대상 | 기준 | 근거와 범위 |
| --- | --- | --- |
| Python 개발 기준 | 3.14.7 | [공식 릴리스](https://www.python.org/downloads/release/python-3147/). 확인일 기준 최신 안정 버전이다. |
| Python 지원 목표 | 표준 CPython 3.10–3.14 | Ubuntu에서 다섯 minor, macOS·Windows에서 3.14.7을 기반 probe CI 대상으로 둔다. |
| 제외한 실행 환경 | pre-release·free-threaded·PyPy | 이번 실행·지원 판정에 포함하지 않는다. |

지원 범위는 사용자가 지정한 Python 3.10–3.14다. `.python-version`은 개발 기준인 3.14.7로 고정한다. 실제 pydconfig 전체 계약 시험과 패키징 gate를 통과한 뒤 라이브러리 지원으로 선언한다.

## 의존성 baseline

| 라이브러리 | 확인한 버전 | 역할 |
| --- | --- | --- |
| pydantic | 2.13.5 | 모델·필드 검증·공개 model_fields/model_rebuild/create_model |
| pydantic-settings | 2.15.0 | BaseSettings·custom source·source debug |
| python-dotenv | 1.2.3 | interpolate=False 파일 파싱 |
| PyYAML | 6.0.3 | YAML reader 기반 |

확인한 버전의 Python Requires-Python과 3.14 classifier를 PyPI metadata에서 확인하고 고정 버전 설치를 수행했다. metadata만으로 실제 라이브러리 호환성을 승인하지 않는다. [Pydantic](https://pypi.org/project/pydantic/2.13.5/), [Pydantic Settings](https://pypi.org/project/pydantic-settings/2.15.0/), [python-dotenv](https://pypi.org/project/python-dotenv/1.2.3/), [PyYAML](https://pypi.org/project/PyYAML/6.0.3/)

## 실행 가능한 검사

[scripts/check_compatibility.py](../scripts/check_compatibility.py)는 구현 전 단계에서 다음을 검사한다.

- forward reference를 public model_rebuild로 완성하고 model_fields의 annotation을 읽는다. [Python 3.14 annotation 변경](https://docs.python.org/3.14/whatsnew/3.14.html#pep-649-and-pep-749-deferred-evaluation-of-annotations)에 대응하는 기반 확인이다.
- 실제 BaseSettings/custom source, required aggregate field의 빈 DefaultSettingsSource, input deep copy와 2→4의 독립 재검증을 확인한다.
- Settings debug를 활성화하고 source의 값 없는 repr이 secret sentinel을 로그에 넣지 않는지 확인한다. 시험 fixture가 debug를 켜는 것이며 제품이 debug를 끄거나 OS/logger를 변경해 값을 숨기는 구현이 아니다.
- Pydantic native boolean 대소문자 처리와 python-dotenv의 syntax quote·실제 quote·literal 보간·공백 보존을 확인한다. pydconfig의 quote 처리 구현은 아직 없다.

```bash
python -m pip install -r requirements/compatibility.txt
python scripts/check_compatibility.py
```

## 이전 실행 기록

- macOS arm64 / CPython 3.14.4와 3.13.13에서 고정 의존성 설치와 기반 probe를 통과했다. 시스템 Python을 교체하지 않고 임시 venv를 사용했다.
- Linux arm64 / 공식 Python 3.10.21-slim과 3.14.7-slim 컨테이너에서 같은 기반 probe를 통과했다.
- Ubuntu CPython 3.10·3.11·3.12·3.13·3.14.7과 macOS·Windows 3.14.7의 7개 CI job이 모두 통과했다. 검증 code commit은 `bd23d4b03d70acd9375cd4814c7fee446925b53f`이며 [실행 결과](https://github.com/pydemia/pydconfig/actions/runs/36237714964)를 completed/success로 확인했다. 이는 이번 변경 전 기록이다.
- 전체 pydconfig 구현·wheel/sdist·G1–G11은 아직 수행할 구현 단계 작업이다. 최초 리뷰 원본과 v2/v3의 승인 기록은 보존한다.

## 이번 변경의 실행 기록

- macOS CPython 3.14.4·3.13.13에서 수정한 probe를 통과했다.
- Python 설정 API만 대상으로 정리한 code commit `0370734a007cf16a711a20f91474dd07945fea92`의 [CI](https://github.com/pydemia/pydconfig/actions/runs/36239341897)가 completed/success다.
- Ubuntu의 Python 3.10·3.11·3.12·3.13·3.14.7, macOS·Windows 3.14.7의 7개 job을 각각 completed/success로 확인했다.
- 이 결과는 기반 API 호환성 판정이다. ConfigLoader 구현·smart quote·전체 G1–G11·wheel 설치는 아직 검증되지 않았다.

## v1.0.0 구현 검증

위 기록은 probe-only 준비 단계의 결과다. 실제 src/pydconfig 구현과 pytest 계약 시험, mypy, sdist→wheel build·설치·예제 검증을 추가했다. 동일한 7개 Python/OS 조합의 새 CI 결과는 [release 기록](release-plan.md)에 귀속한다. 지원 범위 밖 Python 구현·버전은 이 결과로 보장하지 않는다.
