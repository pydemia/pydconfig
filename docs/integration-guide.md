# 애플리케이션 연동

아래 코드는 구현 전 pydconfig API를 전제로 한 연동 예제다. 라이브러리 wheel에서 실행 검증한 상태가 아니다. 설정 모델·source 규칙은 [사용자 가이드](user-guide.md), 필드·오류 계약은 [설정 규칙](configuration-reference.md)을 따른다.

## 생성자 주입

설정 로딩을 application bootstrap에서 수행하고 완성된 객체를 소비자에게 전달한다. 소비자는 환경변수와 파일 경로를 직접 읽지 않는다.

```python
from pathlib import Path

from pydconfig import ConfigLoader, ConfigModel


class ClientConfig(ConfigModel):
    host: str = "localhost"
    timeout: float = 5.0


class ApiClient:
    def __init__(self, config: ClientConfig) -> None:
        self.host = config.host
        self.timeout = config.timeout


def build_client(config_root: Path) -> ApiClient:
    loader = ConfigLoader(root_dir=config_root)
    loader.register("client", ClientConfig)
    snapshot = loader.load()
    return ApiClient(snapshot.get("client", ClientConfig))
```

이 패턴은 배치·CLI에도 동일하게 적용한다. ConfigModel에 client 인스턴스 필드를 선언하거나 `arbitrary_types_allowed=True`를 켜지 않는다. logger 설정, DB pool 생성, 외부 서비스 연결은 load 성공 뒤 수행한다. 전체 설정을 검증하기 전에 부분 client를 만들지 않는다.

## FastAPI app별 설정

FastAPI는 application이 선택해서 설치한다. pydconfig의 core 필수 의존성으로 추가하지 않는다. 다음은 별도 adapter 없이 lifespan·dependency를 애플리케이션에서 연결하는 패턴이다. 초기화를 lifespan에 배치하면 요청 처리 전에 설정을 읽으며 import 시점에는 파일을 읽지 않는다. [FastAPI lifespan 문서](https://fastapi.tiangolo.com/advanced/events/)

```python
from collections.abc import Mapping
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from pydconfig import ConfigLoader, ConfigModel


class FeatureConfig(ConfigModel):
    enabled: bool = False


def get_feature(request: Request) -> FeatureConfig:
    return request.app.state.config.get("feature", FeatureConfig)


def create_app(
    config_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loader = ConfigLoader(root_dir=config_root, dotenv=False)
        loader.register("feature", FeatureConfig)
        app.state.config = loader.load(environ=environ)
        yield

    app = FastAPI(lifespan=lifespan)

    @app.get("/feature")
    def feature(config: FeatureConfig = Depends(get_feature)):
        return {"enabled": config.enabled}

    return app
```

snapshot은 각 app의 state에 보관한다. 같은 프로세스의 다른 app이 root·profile·환경을 공유하는 전역 `lru_cache`를 만들지 않는다. `app.state`는 application별 임의 상태를 보관하는 FastAPI API다. [FastAPI state reference](https://fastapi.tiangolo.com/reference/fastapi/#fastapi.FastAPI.state)

위 예제는 dotenv를 끄고 OS 또는 호출자가 전달한 environ을 사용한다. dotenv가 필요한 개발 앱은 `dotenv=True`로 구성한다. DB client를 추가하면 lifespan의 yield 전 생성하고 종료 시 해제하는 책임도 application에서 맡는다.

## 테스트 환경 격리

필드 단위 테스트에는 explicit environ과 override를 전달한다. `environ={}`는 OS 환경을 제외하지만 YAML·dotenv까지 끄지는 않는다. 파일 source를 제외하려면 빈 임시 root를 사용하고 dotenv를 끈다.

```python
from tempfile import TemporaryDirectory

from pydconfig import ConfigLoader

with TemporaryDirectory() as directory:
    loader = ConfigLoader(root_dir=directory, dotenv=False)
    loader.register("client", ClientConfig)
    baseline = loader.load(environ={})
    changed = baseline.with_overrides({"client": {"timeout": 1.0}})

    assert baseline.get("client", ClientConfig).timeout == 5.0
    assert changed.get("client", ClientConfig).timeout == 1.0
```

이 조각은 위의 ClientConfig 선언을 사용한다. 전역 `os.environ`을 변경할 필요가 없다. 기존 snapshot의 container를 변경하는 테스트도 다른 get 결과와 원본 snapshot이 유지되는지 확인한다.

FastAPI 테스트는 app factory에 환경을 주입한다. `TestClient`와 HTTP client 의존성은 application의 개발 의존성으로 설치한다. context manager로 lifespan을 실행한다. [FastAPI lifespan 테스트](https://fastapi.tiangolo.com/advanced/testing-events/)

```python
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

with TemporaryDirectory() as directory:
    app = create_app(
        Path(directory),
        environ={"PYDCONFIG_FEATURE__ENABLED": '"FALSE"'},
    )
    with TestClient(app) as client:
        assert client.get("/feature").json() == {"enabled": False}
```

dependency만 교체하려면 `app.dependency_overrides[get_feature]`를 해당 app에서 설정한다. 테스트 뒤 해제하고 다른 app의 설정을 변경하지 않는다. [FastAPI dependency override](https://fastapi.tiangolo.com/advanced/testing-dependencies/)

## 설정 갱신

일부 값을 변경할 때는 `with_overrides()`로 새 snapshot을 검증하고 애플리케이션이 사용할 참조를 교체한다. 이미 만들어진 client는 이전 설정을 보관할 수 있으므로 교체·종료 정책은 application에서 정한다.

파일·프로세스 환경을 다시 읽으려면 새 `load()`가 필요하다. 자동 watch, 자동 client 재생성, request마다 설정 재로딩은 제공하지 않는다. 여러 worker 프로세스의 snapshot도 자동 동기화하지 않는다.

## 기존 설정 코드 이관

| 기존 패턴 | 이관 방향 |
| --- | --- |
| `os.getenv()`를 model default에서 호출 | 안정적인 코드 기본값으로 바꾸고 loader의 source 바인딩 사용 |
| import 시 전역 settings 생성 | main·app factory·lifespan에서 명시적 load |
| 모델별 `_root_key` | `register(name, model, path=...)` |
| 설정 모델 안의 logger/client 생성 | snapshot 성공 뒤 application bootstrap |
| 미리 만든 nested model default | ConfigModel class factory 또는 raw mapping factory |
| 별도 `load_dotenv()` 후 env 읽기 | loader가 기본·profile dotenv를 개별 source로 읽도록 구성 |

기존 변수명과 새 경로가 다르면 실제 대응표를 먼저 작성한다. MVP는 alias를 추측하지 않는다. OS의 기존 변수만 최상위 overrides로 올리면 dotenv·YAML과의 순서가 바뀌므로 source별 mapping 정책 없이 동일한 동작이라고 판단하지 않는다.

최상단 `config:` wrapper, 여러 YAML 파일의 병합, 기존 dotenv 내부 변수 보간은 core MVP 계약과 다를 수 있다. 필요한 preprocessing·adapter를 별도로 정의하고 비민감 fixture로 비교한다. 지원되지 않는 alias·multi-YAML을 문서만으로 제공되는 기능처럼 취급하지 않는다.

부분 영역을 먼저 이관할 때 `unknown="ignore"`를 선택할 수 있으나 source report에 무시한 경로를 확인한다. 새 bootstrap 선택을 되돌릴 수 있게 유지하며 loader가 원래 파일·환경을 수정하는 방식으로 이관하지 않는다.
