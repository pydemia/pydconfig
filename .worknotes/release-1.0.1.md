# v1.0.1 문서·배포 기록

2026-09-27 요청에 따라 README와 사용자 가이드를 영어로 작성하고
quickstart, nested ConfigModel, YAML, dotenv 및 OS 환경변수 설명을
확장했다. 설치 명령은 PyPI의 `pydconfig==1.0.1`을 사용한다.

버전 metadata, `__version__`, 배포 검사 및 CI wheel 경로를 1.0.1로
맞췄다. 실행 라이브러리의 변경은 `__version__`뿐이며 설정 처리 동작은
변경하지 않았다. 문서의 버전과 변경된 heading을 참조하는 링크도 맞췄다.

Windows CPython 3.14.4에서 sdist를 생성한 뒤 그 sdist로 wheel을 만들고
별도 venv에 설치했다. 다음 검사를 실제 실행해 통과했다.

- pytest 173개
- mypy source 파일 15개 및 Ruff
- upstream 설정 API probe, pip check, twine check --strict
- 설치 버전, site-packages import, py.typed와 기본 파일 예제
- README·user guide의 Python block 16개 compile
- 문서 예제 및 YAML·dotenv·profile·OS override 시나리오 20회 실행
- 현재 사용자 문서와 기본 예제의 local/GitHub 문서 링크 17개

Ubuntu CPython 3.10–3.14와 macOS·Windows CPython 3.14의 원격 CI 및
외부 게시 결과는 해당 commit의 Actions run과 GitHub Release에서
확인한다. 이 문서는 로컬 검증 결과를 기록한다.

v1.0.0의 [초기 배포 기록](release-plan.md)은 당시 인증서 오류를
보존한다. 2026-09-27에는 기존 WSL 인증 정보로
[PyPI 1.0.0](https://pypi.org/project/pydconfig/1.0.0/)을 게시했고
GitHub 첨부 파일과 PyPI 실제 다운로드 SHA256의 일치 및 별도 venv
설치를 확인했다. 토큰 값을 문서, 작업 파일 또는 게시 로그에 복사하지
않았다.
