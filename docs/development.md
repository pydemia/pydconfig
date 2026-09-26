# 개발·검증·배포 가이드

src/pydconfig는 실행 가능한 구현이며 tests는 공개 계약을 검사한다. editable 설치는 개발용으로 사용하고 배포 gate에서는 sdist로 만든 wheel을 설치해 같은 시험과 파일 예제를 실행한다.

## 개발 환경

표준 CPython 3.10–3.14를 사용한다. 개발 기준은 3.14.7이다. `.python-version`이 Python 자체를 설치하지는 않으며 pyenv 등 도구 사용 여부는 개발 환경에서 선택한다.

macOS·Linux:

```bash
git clone https://github.com/pydemia/pydconfig.git
cd pydconfig
python3.14 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy
.venv/bin/python scripts/check_compatibility.py
```

Windows PowerShell:

```powershell
git clone https://github.com/pydemia/pydconfig.git
Set-Location pydconfig
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install -e '.[dev]'
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m mypy
.venv\Scripts\python.exe scripts/check_compatibility.py
```

해당 실행 파일이 없으면 설치된 3.10–3.14 버전으로 바꾼다. 기본 system Python과 전역 package를 교체할 필요가 없다. 의존성 설치에는 네트워크가 필요하며 설치 후 probe는 외부 서비스에 접속하지 않는다.

## 의존성과 시험

`requirements/compatibility.txt`는 재현 가능한 기반 검사를 위한 고정 버전이다. pyproject.toml은 같은 최소 버전부터 해당 major 미만의 범위를 허용한다. 이 파일은 서비스 전체의 lockfile이 아니다.

| 기반 | 고정 baseline |
| --- | --- |
| pydantic | 2.13.5 |
| pydantic-settings | 2.15.0 |
| python-dotenv | 1.2.3 |
| PyYAML | 6.0.3 |

probe는 public forward annotation API, 실제 BaseSettings custom source, 원시 입력 복사·독립 검증, source debug의 원문 비밀값 미출력, Pydantic native bool, dotenv quote·literal·환경 무변경을 확인한다. 성공 출력에는 `scope="upstream settings APIs; not pydconfig runtime"`과 `result="passed"`가 포함된다.

probe와 별도로 pytest가 pydconfig의 source 우선순위, smart quote·boolean, strict YAML·dotenv·JSON, profile, registry, provenance, replay·snapshot 격리와 debug/error 비밀값 미출력을 검사한다. mypy는 public implementation의 타입을 검사하고 Ruff는 import와 기본 오류를 검사한다. [실행 근거와 한계](../.worknotes/compatibility-plan.md)

## CI 범위

[compatibility workflow](../.github/workflows/compatibility.yml)는 push·pull request·수동 실행에서 다음 조합으로 sdist·wheel build, 설치, pytest, mypy, Ruff, upstream probe, pip check, twine check와 파일 예제를 수행한다.

| OS | Python |
| --- | --- |
| Ubuntu | 3.10, 3.11, 3.12, 3.13, 3.14.7 |
| macOS | 3.14.7 |
| Windows | 3.14.7 |

`scripts/check_distribution.py`는 editable import를 거부하고 version·py.typed·임시 디렉터리의 파일 예제 출력을 확인한다. PyPy·free-threaded·pre-release 지원을 이 matrix로 선언하지 않는다.

## 문서와 예제 유지

- README는 프로젝트 상태, 현재 실행 가능한 명령, 문서 진입점을 제공한다.
- docs는 사용자 계약·연동·개발 방법을 설명한다. release별 public API를 설명하고 설치·실행 검증 범위를 기록한다.
- examples/basic은 기본·profile YAML과 dotenv template을 사용한다. 공개 예제 값만 저장한다.
- .worknotes는 기획·상세 설계·검증 결과·리뷰 기록을 보관한다. 최초 리뷰 원본은 수정하지 않는다.

API·우선순위·파싱 정책을 변경하면 설계와 사용자 문서를 같이 변경한다. 문서의 Python 코드 syntax, local link·anchor, YAML·dotenv template은 검사하고 기능 예제는 installed wheel에서 실행한다. syntax 검사는 API 실행 검증을 대신하지 않는다.

## Build와 설치 검증

PEP 517 build를 사용하며 기본 build는 sdist를 생성한 뒤 그 sdist로 wheel을 만든다. version은 package metadata의 `1.0.0`, Git tag는 `v1.0.0`으로 맞춘다. author·license·지원 API는 실제 결정한 값을 기록하며 임의로 넣지 않는다.

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

사용자가 요청한 대상은 Git push, release branch, `v1.0.0` tag와 GitHub Release의 wheel 첨부다. PyPI 업로드도 요청 범위에 포함됐다. 인증이 없어 업로드할 수 없으면 검증된 배포물로 사용자가 수동 업로드한다. 배포 전 모든 gate를 통과한 commit으로 tag를 생성하고, 기존 tag·release가 있으면 덮어쓰지 않고 먼저 상태를 확인한다.

build 도구와 저장소 정책을 위한 참고는 [PyPA](https://packaging.python.org/en/latest/tutorials/packaging-projects/), [GitHub CLI release create](https://cli.github.com/manual/gh_release_create)다. 현재 준비 상태는 [release 작업 기록](../.worknotes/release-plan.md)에 기록한다.

## PyPI 수동 업로드

검증한 wheel과 sdist를 같은 dist에 둔 뒤 업로드한다. PyPI token은 shell history·문서·Git에 넣지 않고 twine의 prompt 또는 보안 credential 저장소로 전달한다. 기존 v1.0.0은 덮어쓸 수 없다.

```bash
python -m pip install twine
python -m twine check dist/pydconfig-1.0.0-py3-none-any.whl dist/pydconfig-1.0.0.tar.gz
python -m twine upload dist/pydconfig-1.0.0-py3-none-any.whl dist/pydconfig-1.0.0.tar.gz
```

GitHub Release에도 SHA256SUMS.txt를 첨부한다. 다운로드한 배포물의 checksum을 확인하고 새 build와 섞지 않는다. 업로드 후 PyPI의 version·metadata·파일 checksum과 별도 venv 설치를 확인한다.
