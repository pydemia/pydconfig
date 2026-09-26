from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import Field, SecretStr

from pydconfig import ConfigLoader, ConfigModel


class Pool(ConfigModel):
    size: int = Field(default=10, ge=1, le=100)
    timeout: float = 5.0


class Database(ConfigModel):
    host: str = "localhost"
    port: int = 5432
    pool: Pool = Field(default_factory=Pool)
    password: SecretStr = SecretStr("example-only")


class Feature(ConfigModel):
    enabled: bool = False
    hosts: list[str] = Field(default_factory=list)
    labels: dict[str, str] = Field(default_factory=dict)


@pytest.fixture
def loader(tmp_path: Path) -> ConfigLoader:
    result = ConfigLoader(root_dir=tmp_path)
    result.register("database", Database)
    result.register("feature", Feature)
    return result
