# 기본 파일 예제

`app.py`는 pydconfig 1.0.1의 YAML·profile·dotenv·boolean 처리 예제다.
[README 설치 명령](../../README.md#installation)으로 패키지를 설치한 뒤
저장소 root에서 실행한다. CI는 이 예제를 임시 디렉터리에 복사해 실행하고
출력값을 검사한다.

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

예제는 root_dir을 파일 위치에 고정하고 `load(environ={})`로 사용자 OS 환경을 제외한다. 출력은 다음과 같다.

```json
{"profile": "local", "database_host": "local-db.internal", "database_port": 5432, "pool_size": 32, "pool_timeout": 2.5, "feature_enabled": false, "feature_hosts": ["primary", "replica"]}
```

실제 OS 환경을 사용하려면 `load(environ={})`를 `load()`로 바꾼다. 그러면
OS 설정이 기본·profile dotenv를 덮는다. source별 동작은
[사용자 가이드](../../docs/user-guide.md#quickstart)에 설명한다.
