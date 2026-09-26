from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated, Any, Literal

import pytest
from conftest import Database, Feature, Pool
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, PostgresDsn, create_model

from pydconfig import ConfigLoader, ConfigModel, ConfigRegistrationError, ConfigValidationError


@pytest.mark.parametrize(
    "annotation",
    [
        Any,
        bytes,
        set[str],
        dict[int, str],
        tuple[int, str],
        list[list[str]],
        str | int,
        list[Pool],
        BaseModel,
    ],
)
def test_unsupported_schema(tmp_path, annotation):
    model = create_model("Unsupported", __base__=ConfigModel, value=(annotation, ...))
    with pytest.raises(ConfigRegistrationError):
        ConfigLoader(root_dir=tmp_path).register("app", model)


@pytest.mark.parametrize(
    "config",
    [
        ConfigDict(arbitrary_types_allowed=True),
        ConfigDict(frozen=False),
        ConfigDict(extra="ignore"),
        ConfigDict(validate_default=False),
    ],
)
def test_model_policy_cannot_be_weakened(tmp_path, config):
    class Weakened(ConfigModel):
        model_config = config
        value: int = 1

    with pytest.raises(ConfigRegistrationError, match="model-policy"):
        ConfigLoader(root_dir=tmp_path).register("app", Weakened)


@pytest.mark.parametrize(
    "declaration",
    [
        Field(default=1, alias="VALUE"),
        Field(default=1, validation_alias="VALUE"),
        Field(default_factory=lambda data: data["other"]),
    ],
)
def test_alias_and_data_aware_factory_rejected(tmp_path, declaration):
    model = create_model("App", __base__=ConfigModel, value=(int, declaration))
    with pytest.raises(ConfigRegistrationError):
        ConfigLoader(root_dir=tmp_path).register("app", model)


def test_recursive_and_unresolved_models(tmp_path):
    class Recursive(ConfigModel):
        child: Recursive | None = None

    with pytest.raises(ConfigRegistrationError, match="recursive-model"):
        ConfigLoader(root_dir=tmp_path).register("app", Recursive)
    Unresolved = create_model(
        "Unresolved", __base__=ConfigModel, child=("ThisTypeDoesNotExist", ...)
    )
    with pytest.raises(ConfigRegistrationError):
        ConfigLoader(root_dir=tmp_path).register("app", Unresolved)


@pytest.mark.parametrize(
    "name, path",
    [
        ("Bad", None),
        ("a__b", None),
        ("a.b", None),
        ("ok", "a..b"),
        ("ok", "profile"),
        ("ok", "profile.child"),
        ("ok", "model_dump"),
    ],
)
def test_registration_names_and_reserved_paths(tmp_path, name, path):
    with pytest.raises(ConfigRegistrationError):
        ConfigLoader(root_dir=tmp_path).register(name, Feature, path=path)


def test_duplicate_name_path_and_parent_child_collision(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("primary", Database, path="database.primary")
    for name, path in [
        ("primary", "other"),
        ("other", "database.primary"),
        ("other", "database"),
        ("other", "database.primary.child"),
    ]:
        with pytest.raises(ConfigRegistrationError):
            loader.register(name, Database, path=path)


def test_same_type_multiple_registrations(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("primary_db", Database, path="database.primary")
    loader.register("replica_db", Database, path="database.replica")
    result = loader.load(
        environ={
            "PYDCONFIG_DATABASE__PRIMARY__HOST": "primary",
            "PYDCONFIG_DATABASE__REPLICA__HOST": "replica",
        }
    )
    assert result.get("primary_db", Database).host == "primary"
    assert result.get("replica_db", Database).host == "replica"


def test_literal_model_default_and_factory_model_result_rejected(tmp_path):
    class LiteralModel(ConfigModel):
        pool: Pool = Pool()

    with pytest.raises(ConfigRegistrationError):
        ConfigLoader(root_dir=tmp_path).register("app", LiteralModel)

    class FactoryModel(ConfigModel):
        pool: Pool = Field(default_factory=lambda: Pool())

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", FactoryModel)
    with pytest.raises(ConfigValidationError, match="model-instance-default"):
        loader.load(environ={})


def test_factories_once_even_shadowed_and_not_on_get_replay(tmp_path):
    calls = []

    def factory():
        calls.append("factory")
        return ["default"]

    class App(ConfigModel):
        values: list[str] = Field(default_factory=factory)

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    result = loader.load(environ={"PYDCONFIG_APP__VALUES": '["env"]'})
    assert calls == ["factory"]
    result.get("app", App)
    assert result.with_overrides({"app": {"values": ["override"]}}).get("app", App).values == [
        "override"
    ]
    assert calls == ["factory"]
    loader.load(environ={})
    assert calls == ["factory", "factory"]


def test_required_nested_parent_not_created_from_child_defaults(tmp_path):
    class App(ConfigModel):
        pool: Pool

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    with pytest.raises(ConfigValidationError):
        loader.load(environ={})
    assert loader.load(environ={}, overrides={"app": {"pool": {}}}).get("app", App).pool.size == 10


def test_supported_types_and_constraints(tmp_path):
    class Mode(str, Enum):
        test = "test"

    class App(ConfigModel):
        url: HttpUrl
        path: Path
        mode: Mode
        literal: Literal[1, 2]
        boolean: Literal[True, False]
        values: tuple[bool, ...]
        number: Annotated[int, Field(ge=2)] = 2
        identifier: str = Field(default="ok", pattern="^[a-z]+$")

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    env = {
        "PYDCONFIG_APP__URL": "https://example.com",
        "PYDCONFIG_APP__PATH": "./data",
        "PYDCONFIG_APP__MODE": "test",
        "PYDCONFIG_APP__LITERAL": '"1"',
        "PYDCONFIG_APP__BOOLEAN": "TRUE",
        "PYDCONFIG_APP__VALUES": '["FALSE", "TRUE"]',
    }
    result = loader.load(environ=env).get("app", App)
    assert result.mode is Mode.test and result.literal == 1 and result.boolean is True
    assert result.values == (False, True) and result.path == Path("./data")
    with pytest.raises(ConfigValidationError):
        loader.load(environ=env, overrides={"app": {"number": 1}})


def test_invalid_default_scalar_can_be_shadowed(tmp_path):
    class App(ConfigModel):
        value: int = "invalid"

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    with pytest.raises(ConfigValidationError):
        loader.load(environ={})
    assert loader.load(environ={"PYDCONFIG_APP__VALUE": "3"}).get("app", App).value == 3


def test_multihost_dsn_and_typed_default(tmp_path):
    value = PostgresDsn("postgresql://user:example@primary:5432,replica:5432/app")

    class App(ConfigModel):
        dsn: PostgresDsn = value

    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("app", App)
    result = loader.load(environ={}).get("app", App)
    assert result.dsn.hosts()[1]["host"] == "replica"
    result = loader.load(environ={"PYDCONFIG_APP__DSN": "postgresql://localhost/app"}).get(
        "app", App
    )
    assert result.dsn.hosts()[0]["host"] == "localhost"


def test_annotations_without_future_import(tmp_path):
    namespace = {}
    # Separate compilation also exercises Python 3.14 deferred annotations.
    exec(
        compile(
            "from pydconfig import ConfigModel\nclass Child(ConfigModel):\n    value: int = 7\nclass App(ConfigModel):\n    child: Child\n",
            "deferred_model.py",
            "exec",
            dont_inherit=True,
        ),
        namespace,
    )
    model = namespace["App"]
    model.model_rebuild(_types_namespace=namespace)
    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("app", model)
    assert (
        loader.load(environ={}, overrides={"app": {"child": {}}}).get("app", model).child.value == 7
    )
