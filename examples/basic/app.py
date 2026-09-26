"""Proposed API example; run after the pydconfig implementation is released."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import Field
from pydconfig import ConfigLoader, ConfigModel


class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1, le=100)
    timeout: float = Field(default=5.0, gt=0)


class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    pool: PoolConfig = Field(default_factory=PoolConfig)


class FeatureConfig(ConfigModel):
    enabled: bool = False
    hosts: list[str] = Field(default_factory=list)


def main() -> None:
    loader = ConfigLoader(root_dir=Path(__file__).resolve().parent)
    loader.register("database", DatabaseConfig)
    loader.register("feature", FeatureConfig)
    snapshot = loader.load(environ={})
    database = snapshot.get("database", DatabaseConfig)
    feature = snapshot.get("feature", FeatureConfig)
    print(json.dumps({
        "profile": snapshot.profile,
        "database_host": database.host,
        "database_port": database.port,
        "pool_size": database.pool.size,
        "pool_timeout": database.pool.timeout,
        "feature_enabled": feature.enabled,
        "feature_hosts": feature.hosts,
    }))


if __name__ == "__main__":
    main()
