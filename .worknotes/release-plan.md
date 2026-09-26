# v1.0.0 release 작업 기록

요청: build·push, release branch, v1.0.0 tag, GitHub Release에 wheel 첨부, 충분한 README·guide 작성. 날짜: 2026-09-26.

## 범위 정정

사용자 정정에 따라 Kubernetes 지원 요구를 제거했다. 제품의 대상은 Python 애플리케이션의 설정 데이터와 환경변수 주입이다. Python 지원 범위는 3.10–3.14를 유지한다. 기획 R14·설계 G11·CI를 Python 설정 기반에 맞추고 manifest 예제·schema 검사·jsonschema 의존성을 제거했다.

최초 리뷰 원본은 수정하지 않았다. 이전 검증 기록은 당시 commit·CI에 귀속시키며 새 변경의 검증으로 재사용하지 않는다.

## 확정한 배포 범위

사용자가 “설계한 설정 라이브러리를 구현·검증한 뒤 release”를 선택했다. 문서·probe만 패키징하는 선택은 진행하지 않는다. ConfigLoader·ConfigModel·ConfigSnapshot과 계약 시험, wheel·sdist를 구현해 v1.0.0으로 배포한다. release branch·tag·GitHub Release에도 반영하며 PyPI 인증이나 업로드가 동작하지 않으면 사용자가 수동 업로드한다.

아래 과거 문서·probe 기록은 당시 commit의 결과다. 이번 구현의 검증은 별도 단락에서 기록한다.

## 문서와 branch 준비

- main의 `68c8fc8e85fa2eb7ace7faab2a2b0703fe795da0`에서 로컬 release branch를 생성했다.
- README와 사용자·설정 규칙·연동·개발 가이드를 작성했다. 모든 API 예제에 구현 전 상태를 명시했다.
- basic 예제에 YAML·profile YAML·dotenv template·Python 예제를 추가했다. expected output은 설계 계약이며 runtime 실행 결과가 아니다.

## 검증과 push

- macOS CPython 3.14.4·3.13.13에서 수정한 기반 probe를 통과했다.
- 문서 16개에서 local link·anchor 56개를 확인했다. README·guide의 Python block 16개와 YAML block 4개, basic 파일 예제의 syntax·dotenv template 파싱을 확인했다.
- 기본 예제의 API 실행은 하지 않았다. 실제 라이브러리 구현이 없기 때문이다.
- git diff --check를 통과했고 최초 리뷰 원본 SHA256이 기존 값과 일치한다.

- code commit `0370734a007cf16a711a20f91474dd07945fea92`를 origin/release에 push하고 원격 branch의 존재를 확인했다.
- [CI 실행 36239341897](https://github.com/pydemia/pydconfig/actions/runs/36239341897)의 7개 job이 모두 completed/success다. Ubuntu Python 3.10–3.14와 macOS·Windows 3.14.7에서 기반 API를 확인했다.

검증 결과 기록은 문서만 변경하며 code 검증 commit과 구분한다. main은 release의 문서·probe 변경을 fast-forward로 반영한다. 태그·GitHub Release는 범위 확정과 배포물 검증 뒤 진행한다.

## v1.0.0 구현 검증 진행

src/pydconfig와 build metadata, 계약 시험을 작성했다. macOS CPython 3.14.4에서 172개 시험이 통과했고 타입·배포물·플랫폼 검증은 진행 중이다. CI는 설치한 wheel에 전체 계약 시험을 실행하도록 변경한다. 태그와 GitHub Release는 이 검증이 통과한 commit을 가리키게 한다. 완료 결과와 PyPI 상태는 검증 후 기록한다.

## 최종 구현·플랫폼 검증

검증 code/test commit: `790a3d05790fe81ef462bb4134a33f0f28da7ab1`. [CI 36245893892](https://github.com/pydemia/pydconfig/actions/runs/36245893892)는 7개 job 모두 completed/success다. Ubuntu CPython 3.10·3.11·3.12·3.13·3.14.7, macOS·Windows 3.14.7에서 sdist→wheel build, 실제 wheel 설치 후 계약 시험, 기본 예제, upstream probe, mypy, Ruff, pip check, twine check를 완료했다.

로컬 CPython 3.14.4에서는 계약 시험 173개와 mypy 15개 source 파일, Ruff를 통과했다. checkout 밖 별도 venv에 wheel을 설치한 뒤 같은 173개 시험, site-packages import·version·py.typed·기본 파일 예제, pip check와 twine check를 확인했다. 이 build는 sdist를 먼저 만들고 그 sdist로 wheel을 만든다. 사용자 문서 6개에서 Python block 17개를 compile하고 local link/anchor 25개를 확인했다. FastAPI 0.141.1·httpx 0.28.1·Starlette 1.7.0의 문서 예제는 생성자 주입, snapshot override와 독립된 두 app의 TestClient 호출을 로컬에서 확인했다. FastAPI는 core/CI 의존성이나 모든 버전 지원 선언에 포함하지 않는다.

첫 CI의 Windows 계약 단계가 오래 실행돼 취소했다. 진단 verbose 실행에서 oversized fixture의 자동 test ID가 1 MiB 원문을 포함해 수 MB 로그를 만드는 문제를 확인했다. 짧은 explicit ID, concise 출력, 3분 step 제한과 faulthandler를 적용한 최종 CI가 모든 플랫폼에서 통과했다. 취소된 run 36245085310·36245623148은 최종 성공 근거로 재사용하지 않는다. 원격 로그 다운로드는 BlobNotFound로 확보하지 못했으며, 실제 job·step의 success와 로컬 시험 출력을 검증 증거로 사용한다.

배포 파일 검사는 py.typed 포함, wheel 내 tests·dotenv 파일 제외, sdist 내 예제 dotenv template 포함 및 실제 dotenv 제외를 확인했다. 코드·문서에서 credential pattern을 발견하지 않았고 최초 리뷰 원본 SHA256은 기존 값과 일치한다. 저작자·라이선스 값은 사용자 결정이 없어 metadata에 임의로 넣지 않았다.

이 기록 commit은 문서만 변경한다. 실행 code·test·workflow는 위 검증 commit과 같다. 최종 tag·GitHub Release·PyPI의 외부 게시 상태는 게시 후 별도로 확인해 기록한다.

## 원격 게시 완료와 PyPI 수동 업로드

main·release에 배포 commit `3c687c9c2c4c2d270d363312071c13986b9ceeda`를 push하고 annotated `v1.0.0`을 생성·push했다. 원격 tag object `03cf55e396eff8cd650c16d85c701283bcc6c401`의 대상이 이 commit임을 GitHub API로 확인했다.

[GitHub Release v1.0.0](https://github.com/pydemia/pydconfig/releases/tag/v1.0.0)는 draft=false, prerelease=false다. wheel·sdist·SHA256SUMS.txt의 uploaded 상태·파일 크기·GitHub digest를 확인했고, 세 파일을 실제 다운로드해 로컬 배포물과 SHA256이 일치함을 확인했다.

| 파일 | 크기 | SHA256 |
| --- | --- | --- |
| pydconfig-1.0.0-py3-none-any.whl | 25,700 bytes | bec96f3670ccfe1925950a5ca9664c3b22924d26a80cf6d8f19ea44605854798 |
| pydconfig-1.0.0.tar.gz | 94,427 bytes | 4096e1454d48cf11d86e9ed0b2dd552101119a4726c2cfea7802b11f329839dd |
| SHA256SUMS.txt | 188 bytes | e61dda0b6c6be462cbd1860c409818b5dfccad141ae61796094bb1da0ae19fa2 |

PyPI 업로드는 기존 twine 인증 설정을 사용해 공식 https://upload.pypi.org/legacy/ 대상으로 non-interactive 실행했다. `CERTIFICATE_VERIFY_FAILED: self-signed certificate in certificate chain`으로 실패했다. 인증서 검증을 끄거나 credential을 공개하지 않았으며 인증 유효성은 이 실패로 판단할 수 없다. 사후 PyPI pydconfig/1.0.0 JSON 조회는 HTTP 404다. 사용자가 요청한 수동 fallback을 적용하며 검증된 dist 또는 GitHub Release 파일을 [수동 업로드 절차](../docs/development.md#pypi-수동-업로드)에 따라 올릴 수 있다.

이번 단락은 외부 게시 후 확인한 결과를 보관하는 문서 기록이다. main·release에 문서 commit으로 반영하고 이미 게시한 v1.0.0 tag와 배포 파일은 변경하지 않는다. 실행 source·test·workflow·metadata는 tag와 동일하다.
