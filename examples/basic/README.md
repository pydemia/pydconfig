# 기본 파일 예제

`app.py`는 아직 구현되지 않은 `pydconfig` 공개 API의 예제다. 현재는 syntax 검사만 가능하며 라이브러리 wheel 설치 후 실행·출력 검증을 수행할 예정이다. 설치된 버전과 예제 검증 결과가 명시되기 전에는 실행 가능한 quickstart로 취급하지 않는다.

구성 파일은 공개 예제 값만 사용한다. `.env.example`과 `.env.local.example`은 복사하기 전에는 loader가 읽지 않는다.

```bash
cp examples/basic/.env.example examples/basic/.env
cp examples/basic/.env.local.example examples/basic/.env.local
python examples/basic/app.py
```

PowerShell에서는 `Copy-Item`을 사용한다.

```powershell
Copy-Item examples/basic/.env.example examples/basic/.env
Copy-Item examples/basic/.env.local.example examples/basic/.env.local
python examples/basic/app.py
```

예제는 root_dir을 파일 위치에 고정하고 `load(environ={})`로 사용자 OS 환경을 제외한다. 설계 계약에 따른 기대 출력은 다음과 같다.

```json
{"profile": "local", "database_host": "local-db.internal", "database_port": 5432, "pool_size": 32, "pool_timeout": 2.5, "feature_enabled": false, "feature_hosts": ["primary", "replica"]}
```

실제 OS 환경을 사용하려면 `load(environ={})`를 `load()`로 바꾼다. 그러면 OS 설정이 기본·profile dotenv를 덮는다. source별 동작은 [사용자 가이드](../../docs/user-guide.md#빠른-시작)에 설명한다.
