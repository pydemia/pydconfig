# Python·Kubernetes 호환성 기준

확인일: 2026-09-26. 사용자가 현재 내용을 먼저 원격에 push한 뒤 최신 Kubernetes·Python 버전에 맞추도록 요청했다. 기존 기획·설계·리뷰 snapshot은 commit `4934e10d36716b88421ce50fd0deddd8d3b72e7e`로 origin/main에 push하고 원격 SHA를 확인했다.

## 버전과 지원 목표

| 대상 | 기준 | 근거와 범위 |
| --- | --- | --- |
| Python 최신 안정 | 3.14.7 | [공식 릴리스](https://www.python.org/downloads/release/python-3147/). Python 3.15는 확인일 기준 pre-release다. |
| Python 지원 목표 | 표준 CPython 3.10–3.14 | Ubuntu에서 다섯 minor, macOS·Windows에서 3.14.7을 기반 probe CI 대상으로 둔다. free-threaded/PyPy는 이번 검증 범위 밖이다. |
| Kubernetes 최신 안정 | v1.37.1 | [공식 stable 채널](https://dl.k8s.io/release/stable.txt)을 직접 조회했다. [릴리스 목록](https://kubernetes.io/releases/)의 1.37 minor를 사용하며 schema는 v1.37.1 tag로 고정했다. |
| Kubernetes 소비 방식 | OS env와 mounted YAML | ConfigMap·Secret·explicit env를 사용한다. Kubernetes SDK·API 조회·watch는 라이브러리 의존성에 추가하지 않는다. |

지원 범위는 사용자가 지정한 Python 3.10–3.14다. `.python-version`과 예제 Python image는 개발 기준인 3.14.7로 고정했다. Python minor 지원은 실제 pydconfig 전체 계약 시험과 패키징 gate를 통과한 뒤 출시 지원으로 선언한다.

## 의존성 baseline

| 라이브러리 | 확인한 안정 버전 | 역할 |
| --- | --- | --- |
| pydantic | 2.13.5 | 모델·필드 검증·공개 model_fields/model_rebuild/create_model |
| pydantic-settings | 2.15.0 | BaseSettings·custom source·source debug |
| python-dotenv | 1.2.3 | interpolate=False 파일 파싱 |
| PyYAML | 6.0.3 | YAML reader와 manifest probe |
| jsonschema | 4.26.0 | Kubernetes OpenAPI schema probe 전용 |

확인한 버전의 Python Requires-Python과 3.14 classifier를 PyPI metadata에서 확인하고 고정 버전 설치를 수행했다. 이 정보만으로 실제 라이브러리 호환성을 승인하지 않는다. [Pydantic](https://pypi.org/project/pydantic/2.13.5/), [Pydantic Settings](https://pypi.org/project/pydantic-settings/2.15.0/), [python-dotenv](https://pypi.org/project/python-dotenv/1.2.3/), [PyYAML](https://pypi.org/project/PyYAML/6.0.3/)

## 실행 가능한 검사

[scripts/check_compatibility.py](../scripts/check_compatibility.py)는 현재 구현 전 단계에서 다음을 검사한다.

- forward reference를 public model_rebuild로 완성하고 model_fields의 annotation을 읽는다. [Python 3.14 annotation 변경](https://docs.python.org/3.14/whatsnew/3.14.html#pep-649-and-pep-749-deferred-evaluation-of-annotations)에 대응하는 기반 확인이다.
- 실제 BaseSettings/custom source, required aggregate field의 빈 DefaultSettingsSource, input deep copy와 2→4의 독립 재검증을 확인한다.
- 최신 Settings의 debug를 활성화하고 source의 값 없는 repr이 secret sentinel을 로그에 넣지 않는지 확인한다. 테스트 fixture가 debug를 켜는 것이며 제품이 debug를 끄거나 OS/logger를 변경해 값을 숨기는 구현이 아니다.
- Pydantic native boolean 대소문자 처리와 python-dotenv의 syntax quote·실제 quote·literal 보간·공백 보존을 확인한다. pydconfig의 quote 처리 구현은 아직 없다.
- [Kubernetes v1.37.1 공식 OpenAPI](https://raw.githubusercontent.com/kubernetes/kubernetes/v1.37.1/api/openapi-spec/swagger.json)로 Namespace·ConfigMap·Secret·Job 예제를 검증한다.

```bash
python -m pip install -r requirements/compatibility.txt
python scripts/check_compatibility.py --kubernetes-version 1.37.1
```

[Kubernetes 예제](../examples/kubernetes/env-injection.yaml)는 Python 3.14.7의 표준 라이브러리만으로 주입된 원문을 확인한다. ConfigMap은 TRUE·숫자·JSON·`${UNEXPANDED}`를 문자열로 제공하고 explicit env는 실제 quote를 포함한 `"False"`로 ConfigMap 값을 덮는다. Secret에는 공개 예제 전용 값만 넣으며 Job은 secret 원문을 출력하지 않는다. 이 Job의 성공은 Kubernetes의 원문 주입 확인이며 pydconfig의 boolean/quote decoding 시험이 아니다.

실제 테스트 클러스터를 사용할 때는 그 클러스터의 context를 명시한다.

```bash
kubectl --context kind-pydconfig-compat apply -f examples/kubernetes/env-injection.yaml
kubectl --context kind-pydconfig-compat -n pydconfig-compat wait --for=condition=complete job/pydconfig-env-injection --timeout=180s
kubectl --context kind-pydconfig-compat -n pydconfig-compat logs job/pydconfig-env-injection
```

이 명령은 기존 사용자 클러스터에 자동 실행하지 않는다. 라이브러리의 default source 순서는 유지하며 Pod의 envFrom·env 처리 결과를 OS source 하나로 받는다. 환경변수로 주입한 ConfigMap 변경은 Pod 재시작이 필요하고 projected YAML 파일 변경은 명시적 load로 읽는다. [Kubernetes ConfigMap 동작](https://kubernetes.io/docs/concepts/configuration/configmap/)

## 현재 검증 상태

- macOS arm64 / CPython 3.14.4에서 고정 최신 의존성 설치와 기반 probe·v1.37.1 schema 검증을 통과했다. 현재 시스템 Python을 교체하지 않고 임시 venv를 사용했다.
- macOS arm64 / CPython 3.13.13에서도 같은 기반 probe·schema 검증을 통과했다.
- Linux arm64 / 공식 Python 3.10.21-slim과 3.14.7-slim 컨테이너에서 고정 의존성 설치와 같은 기반 probe·v1.37.1 schema 검증을 통과했다.
- CI의 Ubuntu CPython 3.10·3.11·3.12·3.13·3.14.7과 macOS·Windows 3.14.7, 총 7개 job이 모두 통과했다. 검증 대상은 code commit `bd23d4b03d70acd9375cd4814c7fee446925b53f`이며 [실행 결과](https://github.com/pydemia/pydconfig/actions/runs/36237714964)는 completed/success로 확인했다.
- 실제 Kubernetes 클러스터의 환경 주입 Job은 아직 실행하지 않았다. 공식 schema와 manifest 안의 Python 코드 검증까지 수행했다.
- 전체 pydconfig 구현·wheel/sdist·G1–G11과 실제 클러스터에서의 라이브러리 검증은 아직 수행할 구현 단계 작업이다. 최초 리뷰 원본과 v2/v3의 승인 기록은 그대로 보존한다.
