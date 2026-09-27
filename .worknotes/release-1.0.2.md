# v1.0.2 환경변수·배포 기록

2026-09-27 요청에 따라 기본 `env_prefix`를 `""`로 변경했다.
`DATABASE__HOST`는 `database.host`에 직접 바인딩한다. 기존 이름은
`env_prefix="PYDCONFIG_"`를 명시해 유지한다. `PYDCONFIG_PROFILE`은
독립된 예약 제어 변수다.

aggregate `BaseSettings`의 `env_nested_delimiter="__"`를 custom source가
읽어 dotenv와 OS 환경의 경로를 분리한다. underscore 한 개는 이름에
남기고 두 개는 nested level의 구분자로 쓴다. source 우선순위, strict
JSON·boolean·quote 규칙과 값 없는 진단은 기존 pipeline을 유지한다.

README·영어 user guide·설정 reference·dotenv template을 변경한 동작과
맞췄다. metadata, `__version__`, 배포 검사와 CI wheel 경로는 1.0.2다.
v1.0.1의 문서·검증 기록은 [이전 기록](release-1.0.1.md)에 보존한다.

Windows CPython 3.14.4에서 1.0.2 sdist로 만든 wheel을 별도 venv에
설치하고 다음 검사를 실제 실행해 통과했다.

- pytest 177개
- mypy source 파일 15개, Ruff
- upstream 설정 API probe, pip check, strict Twine metadata 검사
- 설치 버전, site-packages import, py.typed와 기본 파일 예제
- README·user guide의 Python block 16개 compile
- 문서 예제 및 YAML·dotenv·profile·OS override 시나리오 20회 실행
- 현재 문서와 예제의 local/GitHub 문서 링크 18개

최종 배포물은 검증 commit의 Git archive에서 build한다. source 파일의
일치와 다운로드 SHA256을 별도로 확인한다. 원격 CI와 외부 게시 결과는
해당 commit의 Actions run, GitHub Release와 PyPI metadata에서 확인한다.
