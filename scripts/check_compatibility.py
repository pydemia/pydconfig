"""Check upstream APIs and Kubernetes manifests before pydconfig is implemented."""

from __future__ import annotations

import argparse
from copy import deepcopy
from importlib.metadata import version
from io import StringIO
import json
import logging
import os
from pathlib import Path
import re
import sys
from typing import Any
from unittest.mock import patch
from urllib.request import urlopen

from dotenv import dotenv_values
from jsonschema import Draft4Validator
from pydantic import BaseModel, ConfigDict, SecretStr, TypeAdapter, ValidationError
from pydantic import create_model, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4
import yaml


ROOT = Path(__file__).resolve().parents[1]


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


def check_kubernetes_manifest(kubernetes_version: str) -> int:
    if not re.fullmatch(r"\d+\.\d+\.\d+", kubernetes_version):
        raise ValueError("Expected a stable Kubernetes x.y.z version")
    url = (
        "https://raw.githubusercontent.com/kubernetes/kubernetes/"
        f"v{kubernetes_version}/api/openapi-spec/swagger.json"
    )
    with urlopen(url, timeout=30) as response:
        schema = json.load(response)
    uri = f"urn:pydconfig:kubernetes:{kubernetes_version}"
    registry = Registry().with_resource(
        uri, Resource.from_contents(schema, default_specification=DRAFT4)
    )
    definitions = {
        ("v1", "Namespace"): "io.k8s.api.core.v1.Namespace",
        ("v1", "ConfigMap"): "io.k8s.api.core.v1.ConfigMap",
        ("v1", "Secret"): "io.k8s.api.core.v1.Secret",
        ("batch/v1", "Job"): "io.k8s.api.batch.v1.Job",
    }
    manifest = ROOT / "examples/kubernetes/env-injection.yaml"
    resources = list(yaml.safe_load_all(manifest.read_text()))
    for obj in resources:
        definition = definitions[(obj["apiVersion"], obj["kind"])]
        validator = Draft4Validator(
            {"$ref": f"{uri}#/definitions/{definition}"}, registry=registry
        )
        validator.validate(obj)
        if obj["kind"] in ("ConfigMap", "Secret"):
            values = obj.get("data", obj.get("stringData", {}))
            assert all(isinstance(value, str) for value in values.values())
        if obj["kind"] == "Job":
            container = obj["spec"]["template"]["spec"]["containers"][0]
            assert container["image"] == "python:3.14.7-slim"
            assert container["env"][0]["value"] == '"False"'
            compile(container["args"][0], str(manifest), "exec")
    return len(resources)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubernetes-version", default="1.37.1")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("The compatibility baseline requires Python 3.10 or newer")
    check_settings_api()
    check_environment_parsing()
    count = check_kubernetes_manifest(args.kubernetes_version)
    print(json.dumps({
        "scope": "upstream APIs and manifest schema; not pydconfig runtime",
        "python": sys.version.split()[0],
        "dependencies": {name: version(name) for name in ("pydantic", "pydantic-settings", "python-dotenv", "PyYAML")},
        "kubernetes_schema": args.kubernetes_version,
        "resources_validated": count,
        "result": "passed",
    }))


if __name__ == "__main__":
    main()
