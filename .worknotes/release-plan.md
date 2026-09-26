# v1.0.0 release 작업 기록

요청: build·push, release branch, v1.0.0 tag, GitHub Release에 wheel 첨부, 충분한 README·guide 작성. 날짜: 2026-09-26.

## 범위 정정

사용자 정정에 따라 Kubernetes 지원 요구를 제거했다. 제품의 대상은 Python 애플리케이션의 설정 데이터와 환경변수 주입이다. Python 지원 범위는 3.10–3.14를 유지한다. 기획 R14·설계 G11·CI를 Python 설정 기반에 맞추고 manifest 예제·schema 검사·jsonschema 의존성을 제거했다.

최초 리뷰 원본은 수정하지 않았다. 이전 검증 기록은 당시 commit·CI에 귀속시키며 새 변경의 검증으로 재사용하지 않는다.

## 배포 범위 확인

현재 실제 ConfigLoader·ConfigModel·ConfigSnapshot 구현과 build metadata가 없다. wheel에 담을 기능이 정해져야 build·설치 검증·tag를 완료할 수 있다. 사용자에게 아래 선택을 요청한 상태다.

- 설계한 설정 라이브러리를 구현·검증한 뒤 release
- 현재 문서·호환성 검사만 패키징해 release

이 선택의 응답 전에는 라이브러리 구현 완료 또는 v1.0.0 배포 완료로 기록하지 않는다. GitHub Release·wheel은 아직 없다.

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
