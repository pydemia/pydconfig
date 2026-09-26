# 패키지·저장소 이름 변경

변경일: 2026-09-26. 사용자가 공개 패키지 이름을 `pydconfig`로 선택하고 저장소·디렉터리 이름 변경을 요청했다.

| 대상 | 변경 결과 |
| --- | --- |
| PyPI 배포명 / Python import | `pydconfig` / `pydconfig` |
| GitHub 저장소 | https://github.com/pydemia/pydconfig |
| Git origin | GitHub의 `pydemia/pydconfig` 경로로 변경 |
| 로컬 실제 디렉터리 | `/Users/a09255/git/pydconfig` |
| 구현 예정 경로 | `src/pydconfig/` |
| 기본 환경변수 / 프로파일 선택 | `PYDCONFIG_` / `PYDCONFIG_PROFILE` |
| 내부 source 클래스 | `PydConfigSource` |

GitHub 저장소 ID 1388674507과 로컬 HEAD `34765006f3426251edf077c20bdc9580f860a1e5`를 유지했다. 로컬 디렉터리 이동 전후의 파일 hash가 같고 기존 미커밋 변경이 보존됐다. 패키지 구현 파일이나 pyproject.toml은 아직 없으므로 현재 설계의 import·패키지 경로와 이름을 변경한 상태다. PyPI 업로드는 수행하지 않았다.

최초 이름 변경 당시 Codex에 등록된 프로젝트는 기존 경로를 참조했다. 해당 앱 조작은 도구의 안전 제한으로 차단되어 `/Users/a09255/git/pydemia-config`에 새 디렉터리를 가리키는 호환 심볼릭 링크를 남겼다. 이후 사용자가 새 폴더를 작업공간에 추가했다. 현재 작업 디렉터리와 Codex 등록 경로가 모두 `/Users/a09255/git/pydconfig`인 것을 확인하고 호환 링크를 제거했다.

최초 리뷰 원본 [initial-proposal.md](reviews/initial-proposal.md)는 당시 이름과 SHA-256 `662877e0cac8f8aeb59d669bfa033bcbf3caa8a20d917a2bdf734552db779ab5`를 보존한다. 그 외 현 기획·설계·리뷰 설명의 패키지 이름은 새 이름으로 맞췄다.
