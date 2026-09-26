from __future__ import annotations

import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pytest
from conftest import Database, Feature
from pydantic import Field, ValidationError, field_validator, model_validator

from pydconfig import (
    ConfigError,
    ConfigLoader,
    ConfigLookupError,
    ConfigModel,
    ConfigProfileError,
    ConfigValidationError,
)
from pydconfig.settings import PydConfigSource

SENTINEL = "pydconfig-secret-value-do-not-print"


def test_copy_isolation_and_frozen_fields(loader):
    result = loader.load(environ={}, overrides={"feature": {"hosts": ["original"]}})
    first = result.get("feature", Feature)
    first.hosts.append("changed")
    assert result.get("feature", Feature).hosts == ["original"]
    with pytest.raises(ValidationError, match="frozen_instance"):
        first.enabled = True
    changed = result.with_overrides({"feature": {"hosts": ["new"]}})
    assert changed.get("feature", Feature).hosts == ["new"]
    assert result.get("feature", Feature).hosts == ["original"]


def test_replay_prevalidation_input_without_sources_or_factories(tmp_path, monkeypatch):
    calls = []

    def factory():
        calls.append("factory")
        return 2

    class App(ConfigModel):
        value: int = Field(default_factory=factory)
        other: int = 0

        @field_validator("value")
        @classmethod
        def double(cls, value):
            calls.append("validator")
            return value * 2

        @model_validator(mode="before")
        @classmethod
        def mutate_input(cls, value):
            value["other"] += 1
            return value

    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("app", App)
    result = loader.load(environ={})
    assert result.get("app", App).value == 4 and result.get("app", App).other == 1

    def forbidden(*args, **kwargs):
        raise AssertionError("external source was re-read")

    monkeypatch.setattr("pydconfig.pipeline.read_yaml", forbidden)
    monkeypatch.setattr("pydconfig.pipeline.read_dotenv", forbidden)
    replay = result.with_overrides({"app": {"other": 7}})
    assert replay.get("app", App).value == 4 and replay.get("app", App).other == 8
    assert replay.with_overrides({}).get("app", App).other == 8
    assert result.get("app", App).other == 1
    assert calls == ["factory", "validator", "validator", "validator"]


def test_native_sources_and_cli_excluded(loader, monkeypatch):
    monkeypatch.setenv("PYDCONFIG_FEATURE__ENABLED", "TRUE")
    monkeypatch.setattr(sys, "argv", ["program", "--feature.enabled", "true"])
    sources = []
    original = PydConfigSource.__call__

    def record(self):
        result = original(self)
        sources.append(self)
        return result

    monkeypatch.setattr(PydConfigSource, "__call__", record)
    assert not loader.load(environ={}).get("feature", Feature).enabled
    assert len(sources) == 1
    assert sources[0].settings_sources_data["DefaultSettingsSource"] == {}
    assert set(sources[0].settings_sources_data) == {"PydConfigSource", "DefaultSettingsSource"}


def test_environment_and_logger_unchanged(loader):
    before_env = dict(os.environ)
    logger = logging.getLogger("pydantic_settings")
    before_logging = logger.level, tuple(logger.handlers)
    loader.load(environ={"PYDCONFIG_FEATURE__ENABLED": "TRUE"})
    assert dict(os.environ) == before_env
    assert (logger.level, tuple(logger.handlers)) == before_logging


def test_concurrent_independent_contexts(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("database", Database)

    def load(index):
        result = loader.load(
            profile=f"test-{index}", environ={"PYDCONFIG_DATABASE__PORT": str(5000 + index)}
        )
        return result.profile, result.get("database", Database).port

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(load, range(20)))
    assert results == [(f"test-{index}", 5000 + index) for index in range(20)]


def test_snapshot_registration_fixed_and_lookup_types(loader):
    result = loader.load(environ={})
    loader.register("later", Feature)
    with pytest.raises(ConfigLookupError):
        result.get("later", Feature)
    with pytest.raises(ConfigLookupError):
        result.get("database", Feature)
    with pytest.raises(ConfigLookupError):
        result.explain("database.absent")
    with pytest.raises(ConfigLookupError, match="invalid-path"):
        result.explain("database..host")


def test_failed_override_and_profile_change_preserve_snapshot(loader):
    result = loader.load(environ={})
    with pytest.raises(ConfigValidationError):
        result.with_overrides({"database": {"pool": {"size": 0}}})
    with pytest.raises(ConfigProfileError):
        result.with_overrides({"profile": "test"})
    assert result.get("database", Database).pool.size == 10


def test_definition_reference_and_shadow_history_without_values(loader, tmp_path):
    (tmp_path / "config.yaml").write_text('database:\n  host: "${HOST}"\n')
    result = loader.load(environ={"HOST": SENTINEL})
    explanation = result.explain("database.host")
    assert explanation.defined_at.kind == "yaml" and explanation.references[0].name == "HOST"
    assert explanation.shadowed[0].kind == "default" and explanation.output == "opaque-validation"
    for value in (
        result,
        result.get("database", Database),
        explanation,
        result.source_report(),
        asdict(explanation),
        asdict(result.source_report()),
    ):
        assert SENTINEL not in repr(value)


@pytest.mark.parametrize(
    "source, text",
    [
        ("yaml", f'database: ["{SENTINEL}"\n'),
        ("dotenv", f'A="{SENTINEL}\n'),
        ("json", f'{{"password":"{SENTINEL}",bad}}'),
    ],
)
def test_source_error_sanitizing(loader, tmp_path, source, text):
    env = {}
    if source == "yaml":
        (tmp_path / "config.yaml").write_text(text)
    elif source == "dotenv":
        (tmp_path / ".env").write_text(text)
    else:
        env["PYDCONFIG_DATABASE"] = text
    with pytest.raises(ConfigError) as caught:
        loader.load(environ=env)
    error = caught.value
    assert SENTINEL not in str(error) + repr(error) + repr(error.issues)
    assert error.__context__ is None and error.__cause__ is None


def test_validator_and_factory_messages_do_not_escape(tmp_path):
    class App(ConfigModel):
        value: str

        @field_validator("value")
        @classmethod
        def fail(cls, value):
            raise ValueError(value)

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    with pytest.raises(ConfigValidationError) as caught:
        loader.load(environ={"PYDCONFIG_APP__VALUE": SENTINEL})
    assert SENTINEL not in repr(caught.value.issues) + str(caught.value)
    assert caught.value.__context__ is None

    def bad_factory():
        raise RuntimeError(SENTINEL)

    class BadDefault(ConfigModel):
        value: str = Field(default_factory=bad_factory)

    other = ConfigLoader(root_dir=tmp_path)
    other.register("app", BadDefault)
    with pytest.raises(ConfigValidationError) as error:
        other.load(environ={})
    assert SENTINEL not in str(error.value) and error.value.__context__ is None


def test_settings_debug_has_no_raw_secret(loader, monkeypatch, caplog):
    monkeypatch.setenv("PYDANTIC_SETTINGS_DEBUG", "1")
    with caplog.at_level(logging.DEBUG, logger="pydantic_settings"):
        result = loader.load(environ={"PYDCONFIG_DATABASE__HOST": SENTINEL})
    assert "Resolving settings" in caplog.text and SENTINEL not in caplog.text
    assert result.get("database", Database).host == SENTINEL


def test_unknown_error_and_ignore_in_registered_model(tmp_path):
    (tmp_path / "config.yaml").write_text('feature:\n  wrong: "${MISSING}"\n')
    strict = ConfigLoader(root_dir=tmp_path)
    strict.register("feature", Feature)
    with pytest.raises(ConfigValidationError, match="unknown-field"):
        strict.load(environ={})
    relaxed = ConfigLoader(root_dir=tmp_path, unknown="ignore")
    relaxed.register("feature", Feature)
    result = relaxed.load(environ={})
    assert result.source_report().ignored_paths == ("feature.wrong",)
