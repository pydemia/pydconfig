# 개발·검증·배포 가이드

현재 저장소에서 실행할 수 있는 대상은 기반 호환성 probe다. `src/pydconfig`, pyproject와 계약 tests는 아직 없으며 build·wheel 설치·v1.0.0 release는 미완료다. 아래 배포 절차는 구현과 metadata가 준비된 후 적용한다.

## 개발 환경

표준 CPython 3.10–3.14를 사용한다. 개발 기준은 3.14.7이다. `.python-version`이 Python 자체를 설치하지는 않으며 pyenv 등 도구 사용 여부는 개발 환경에서 선택한다.

macOS·Linux:

```bash
git clone https://github.com/pydemia/pydconfig.git
cd pydconfig
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements/compatibility.txt
.venv/bin/python scripts/check_compatibility.py
```

Windows PowerShell:

```powershell
git clone https://github.com/pydemia/pydconfig.git
Set-Location pydconfig
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements/compatibility.txt
.venv\Scripts\python.exe scripts/check_compatibility.py
```

해당 실행 파일이 없으면 설치된 3.10–3.14 버전으로 바꾼다. 기본 system Python과 전역 package를 교체할 필요가 없다. 의존성 설치에는 네트워크가 필요하며 설치 후 probe는 외부 서비스에 접속하지 않는다.

## 의존성과 현재 검사

`requirements/compatibility.txt`는 재현 가능한 기반 검사를 위한 고정 버전이다. package metadata나 서비스 전체의 lockfile이 아니다.

| 기반 | 고정 baseline |
| --- | --- |
| pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| python-dotenv | 1.2.3 |
| PyYAML | 6.0.3 |

probe는 public forward annotation API, 실제 BaseSettings custom source, 원시 입력 복사·독립 검증, source debug의 원문 비밀값 미출력, Pydantic native bool, dotenv quote·literal·환경 무변경을 확인한다. 성공 출력에는 `scope="upstream settings APIs; not pydconfig runtime"`과 `result="passed"`가 포함된다.

현재 검사는 pydconfig의 smart quote, strict YAML·dotenv adapter, profile, registry, provenance, snapshot의 실제 구현을 검사하지 않는다. 검사 성공과 라이브러리 완료는 구분한다. [실행 근거와 한계](../.worknotes/compatibility-plan.md)

## CI 범위

[compatibility workflow](../.github/workflows/compatibility.yml)는 push·pull request·수동 실행에서 다음 조합으로 같은 probe를 수행한다.

| OS | Python |
| --- | --- |
| Ubuntu | 3.10, 3.11, 3.12, 3.13, 3.14.7 |
| macOS | 3.14.7 |
| Windows | 3.14.7 |

구현 후에는 이 matrix에서 전체 계약 tests와 wheel 설치 예제를 추가로 실행한다. PyPy·free-threaded·pre-release 지원을 이 matrix로 선언하지 않는다.

## 문서와 예제 유지

- README는 프로젝트 상태, 현재 실행 가능한 명령, 문서 진입점을 제공한다.
- docs는 사용자 계약·연동·개발 방법을 설명한다. 구현 전 예제와 설치 검증한 예제를 표시한다.
- examples/basic은 기본·profile YAML과 dotenv template을 사용한다. 공개 예제 값만 저장한다.
- .worknotes는 기획·상세 설계·검증 결과·리뷰 기록을 보관한다. 최초 리뷰 원본은 수정하지 않는다.

API·우선순위·파싱 정책을 변경하면 설계와 사용자 문서를 같이 변경한다. 문서의 Python 코드 syntax, local link·anchor, YAML·dotenv template은 검사하고 기능 예제는 installed wheel에서 실행한다. syntax 검사는 API 실행 검증을 대신하지 않는다.

## 구현 후 build와 설치 검증

이 절차는 PEP 517 build metadata와 `src/pydconfig` 구현이 준비된 뒤 실행한다. version은 package metadata의 `1.0.0`, Git tag는 `v1.0.0`으로 맞춘다. author·license·지원 API는 실제 결정한 값을 기록하며 임의로 넣지 않는다.

```bash
python -m pip install build twine
python -m build
python -m twine check dist/*
```

build는 wheel과 sdist를 생성한다. wheel filename은 `pydconfig-1.0.0-<python>-<abi>-<platform>.whl` 형태이며 실제 생성된 파일명을 사용한다. [Python Packaging build·metadata 안내](https://packaging.python.org/en/latest/tutorials/packaging-projects/)

검증은 source checkout의 import가 설치 결과를 가리지 않도록 별도 venv·checkout 밖 cwd에서 수행한다. 생성된 **정확한 wheel 절대경로**를 사용한다.

```bash
python -m venv /tmp/pydconfig-wheel-check
/tmp/pydconfig-wheel-check/bin/python -m pip install /absolute/path/to/dist/pydconfig-1.0.0-py3-none-any.whl
cd /tmp
/tmp/pydconfig-wheel-check/bin/python -c "from importlib.metadata import version; print(version('pydconfig'))"
```

위 wheel명은 pure Python build 예시다. 생성 결과가 다르면 바꾼다. Windows PowerShell은 `$env:TEMP` 아래 venv와 `Scripts/python.exe`를 사용한다. 설치 후 import 경로가 venv의 site-packages에 있는지 확인하고 기본 예제와 공개 API 계약 시험을 실행한다. sdist에서도 wheel을 다시 만들고 동일하게 설치 검증한다. `pip check`로 의존성 충돌을 확인한다.

## Release 완료 조건

| 대상 | 완료 근거 |
| --- | --- |
| 구현 계약 | 상세 설계 G1–G8·G10 통과 |
| Python 호환성 | 3.10–3.14에서 실제 구현 계약·설치 검사 G11 통과 |
| 배포물 | wheel·sdist clean install과 공개 API·예제 실행 G9 통과 |
| 문서 | 실제 API·설치 명령·기능 제한과 README·guide 일치 |
| Git | 검증 commit의 release branch와 annotated v1.0.0 tag를 원격에서 확인 |
| GitHub Release | tag 대상 commit 일치, wheel 첨부와 다운로드 파일 checksum 확인 |

사용자가 요청한 대상은 Git push, release branch, `v1.0.0` tag와 GitHub Release의 wheel 첨부다. PyPI 업로드는 별도 요청 범위다. 배포 전 모든 gate를 통과한 commit으로 tag를 생성하고, 기존 tag·release가 있으면 덮어쓰지 않고 먼저 상태를 확인한다.

build 도구와 저장소 정책을 위한 참고는 [PyPA](https://packaging.python.org/en/latest/tutorials/packaging-projects/), [GitHub CLI release create](https://cli.github.com/manual/gh_release_create)다. 현재 준비 상태는 [release 작업 기록](../.worknotes/release-plan.md)에 기록한다.
