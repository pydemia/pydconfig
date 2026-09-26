# 작업 문서 위치와 지침 적용 확인

확인일: 2026-09-26. 이 기록은 pydconfig 기획·설계·리뷰 문서의 저장 위치를 바로잡은 근거다.

## 확인한 사실

- 최초 문서는 `docs/`에 작성됐다. 당시 세션에 제공된 지침과 저장소·상위 디렉터리·개인 Codex AGENTS에는 `.worknotes` 규칙이 없었다.
- 세션에 사용 가능한 스킬 목록에는 `software-engineering`, `persona-cross-review`가 없었다. 실제 사용한 로컬 스킬은 `evidence-based-code-review`였다.
- [skills.pydemia.ai](https://skills.pydemia.ai)의 공개 Skills 26개와 Prompts 27개 상세 페이지를 모두 조회했고 표시된 본문에서 `worknotes` 문자열이 발견되지 않았다. 조회 실패는 없었다. 해당 Hub의 표시 source revision은 `2465d7c4d843`였다.
- 관련 [개발 지침](https://skills.pydemia.ai/skills/software-engineering), [persona 리뷰 지침](https://skills.pydemia.ai/skills/persona-cross-review), [문서 작성 지침](https://skills.pydemia.ai/skills/document-writing-workflow)에도 저장 경로를 `.worknotes`로 지정하는 규칙은 없었다.
- 사이트가 링크한 GitHub 원본은 현재 인증 환경에서 HTTP 404로 조회되지 않았다. 공개 발행본과 최신 canonical 원본의 일치 여부는 확인하지 못했다. 로컬 agent-skills checkout은 `9317322`로 Hub revision과 달랐다.

## 수정

사용자의 `.worknotes` 저장 위치 지시를 현재 작업의 기준으로 적용했다. 기획서·상세 설계서·리뷰 보고서·최초 제안·문서 안내의 여섯 파일을 `.worknotes/`로 이동하고 README 링크를 변경했다. 이동 전후 파일 SHA-256이 같음을 확인했으며 최초 리뷰 baseline hash도 유지했다.

기획·설계의 내용과 최종 리뷰 판정은 이동으로 바꾸지 않았다. 관련 스킬을 설치하거나 사이트·canonical 지침을 변경한 것은 아니다. 공개 발행본에 없는 규칙을 읽고 적용했다고 소급 기록하지 않는다.
