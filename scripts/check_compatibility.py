"""Check the upstream settings APIs independently of pydconfig's contract suite."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from copy import deepcopy
from importlib.metadata import version
from io import StringIO
from typing import Any
from unittest.mock import patch

from dotenv import dotenv_values
from pydantic import (
    BaseModel,
    ConfigDict,
    SecretStr,
    TypeAdapter,
    ValidationError,
    create_model,
    field_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


class RedactedInput(dict):
    def __repr__(self) -> str:
        return "<configuration input redacted>"


def check_settings_api() -> None:
    """Exercise forward annotations, aggregate validation, replay, and debug logs."""
    calls = []
    sources = []
    sentinel = "pydconfig-compatibility-secret-sentinel"

    class App(BaseModel):
        model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)
        pool: Pool
        password: SecretStr

    class Pool(BaseModel):
        size: int

        @field_validator("size")
        @classmethod
        def transform(cls, value: int) -> int:
            calls.append("validator")
            return value * 2

    App.model_rebuild(_types_namespace={"Pool": Pool})
    assert App.model_fields["pool"].annotation is Pool
    if sys.version_info >= (3, 14):
        namespace = {"__name__": "native_annotation_probe", "BaseModel": BaseModel}
        code = compile(
            "class Deferred(BaseModel):\n"
            "    child: Later\n"
            "class Later(BaseModel):\n"
            "    value: int\n",
            "<native deferred annotations>", "exec", dont_inherit=True,
        )
        exec(code, namespace)
        deferred = namespace["Deferred"]
        deferred.model_rebuild(_types_namespace=namespace)
        assert deferred.model_fields["child"].annotation is namespace["Later"]
        assert deferred.model_validate({"child": {"value": "7"}}).child.value == 7
    aggregate = create_model(
        "CompatibilityAggregate", __base__=BaseSettings, app=(App, ...)
    )
    raw = {"app": {"pool": {"size": 2}, "password": sentinel}}

    class Source(PydanticBaseSettingsSource):
        def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
            return raw.get(field_name), field_name, False

        def __call__(self) -> dict[str, Any]:
            calls.append("source")
            return RedactedInput(deepcopy(raw))

    class Bound(aggregate):
        model_config = SettingsConfigDict(
            env_file=None, secrets_dir=None, cli_parse_args=None
        )

        @classmethod
        def settings_customise_sources(
            cls, settings_cls, init_settings, env_settings,
            dotenv_settings, file_secret_settings,
        ):
            source = Source(settings_cls)
            sources.append(source)
            return (source,)

    output = StringIO()
    handler = logging.StreamHandler(output)
    logger = logging.getLogger("pydantic_settings")
    old_level = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with patch.dict(os.environ, {"PYDANTIC_SETTINGS_DEBUG": "1"}):
            first = Bound(_cli_parse_args=None, _cli_settings_source=None)
            second = Bound(_cli_parse_args=None, _cli_settings_source=None)
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
    assert first.app.pool.size == second.app.pool.size == 4
    assert raw["app"]["pool"]["size"] == 2
    assert calls == ["source", "validator", "source", "validator"]
    assert all(s.settings_sources_data.get("DefaultSettingsSource") == {} for s in sources)
    assert "Resolving settings" in output.getvalue(), "Debug path was not exercised"
    assert sentinel not in output.getvalue(), "Upstream source debug leaked input"


def check_environment_parsing() -> None:
    """Record native parsing; pydconfig's quote/boolean policy remains a separate gate."""
    adapter = TypeAdapter(bool)
    for value in ("True", "true", "TRUE", "tRuE"):
        assert adapter.validate_python(value) is True
    for value in ("False", "false", "FALSE", "fAlSe"):
        assert adapter.validate_python(value) is False
    try:
        adapter.validate_python('"False"')
    except ValidationError:
        pass
    else:
        raise AssertionError("Native quoted-boolean behavior changed")
    before = dict(os.environ)
    parsed = dotenv_values(
        stream=StringIO('FLAG="False"\nQUOTED=\'"False"\'\nTEXT=" spaced "\nREF=${MISSING}\n'),
        interpolate=False,
    )
    assert parsed == {"FLAG": "False", "QUOTED": '"False"', "TEXT": " spaced ", "REF": "${MISSING}"}
    assert dict(os.environ) == before


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("The compatibility baseline requires Python 3.10 or newer")
    check_settings_api()
    check_environment_parsing()
    print(json.dumps({
        "scope": "upstream settings APIs; not pydconfig runtime",
        "python": sys.version.split()[0],
        "dependencies": {name: version(name) for name in ("pydantic", "pydantic-settings", "python-dotenv", "PyYAML")},
        "result": "passed",
    }))


if __name__ == "__main__":
    main()
