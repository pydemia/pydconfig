from __future__ import annotations

import os

import pytest
from conftest import Database, Feature, Pool
from pydantic import Field

from pydconfig import ConfigLoader, ConfigModel, ConfigSourceError, ConfigValidationError


@pytest.mark.parametrize(
    "value, expected",
    [
        ("True", True),
        ("true", True),
        ("TRUE", True),
        ("tRuE", True),
        ("False", False),
        ("false", False),
        ("FALSE", False),
        ("fAlSe", False),
        ("1", True),
        ("0", False),
        (' " false " ', False),
        ("'TRUE'", True),
        ('"False"', False),
        ("  false\t", False),
    ],
)
def test_boolean_variants(loader, value, expected):
    result = loader.load(environ={"FEATURE__ENABLED": value})
    assert result.get("feature", Feature).enabled is expected


@pytest.mark.parametrize(
    "value", ["", "2", "null", "yes", "no", "on", "off", '""True""', '"', "'", "\"false'"]
)
def test_boolean_rejections(loader, value):
    with pytest.raises(ConfigValidationError, match="invalid-boolean"):
        loader.load(environ={"FEATURE__ENABLED": value})


@pytest.mark.parametrize(
    "value, expected", [(True, True), (False, False), (0, False), (1, True), ("TRUE", True)]
)
def test_boolean_python_input(loader, value, expected):
    assert (
        loader.load(environ={}, overrides={"feature": {"enabled": value}})
        .get("feature", Feature)
        .enabled
        is expected
    )


@pytest.mark.parametrize("value", [2, 1.0, [], {}, '"False"'])
def test_boolean_python_input_not_environment_quoted(loader, value):
    with pytest.raises(ConfigValidationError):
        loader.load(environ={}, overrides={"feature": {"enabled": value}})


@pytest.mark.parametrize(
    "value", ['"abc"', ' a"b ', '"', "'", '"abc', "\"abc'", "  spaced  ", "\\x"]
)
def test_strings_and_secret_preserve(loader, value):
    result = loader.load(
        environ={"DATABASE__HOST": value, "DATABASE__PASSWORD": value}
    )
    database = result.get("database", Database)
    assert database.host == value
    assert database.password.get_secret_value() == value


@pytest.mark.parametrize(
    "value, expected",
    [('"abc"', "abc"), ("'abc'", "abc"), (' "abc" ', ' "abc" '), ('""abc""', '"abc"')],
)
def test_explicit_string_unwrap(tmp_path, value, expected):
    loader = ConfigLoader(root_dir=tmp_path, env_quote_policy={"database.host": "unwrap"})
    loader.register("db", Database, path="database")
    assert (
        loader.load(environ={"DATABASE__HOST": value}).get("db", Database).host
        == expected
    )


def test_boolean_preserve_and_policy_path_validation(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, env_quote_policy={"feature.enabled": "preserve"})
    loader.register("feature", Feature)
    with pytest.raises(ConfigValidationError):
        loader.load(environ={"FEATURE__ENABLED": '"False"'})
    invalid = ConfigLoader(root_dir=tmp_path, env_quote_policy={"unknown.field": "unwrap"})
    invalid.register("feature", Feature)
    with pytest.raises(ConfigSourceError, match="invalid-quote-policy-path"):
        invalid.load(environ={})


def test_numeric_and_json_quote_rules(loader):
    result = loader.load(
        environ={
            "DATABASE__PORT": "'5000'",
            "DATABASE__POOL__TIMEOUT": '"1.5"',
            "FEATURE__HOSTS": '\'["a", "b"]\'',
        }
    )
    assert result.get("database", Database).port == 5000
    assert result.get("database", Database).pool.timeout == 1.5
    assert result.get("feature", Feature).hosts == ["a", "b"]
    quoted = loader.load(environ={"FEATURE__HOSTS": '["\\"a\\""]'})
    assert quoted.get("feature", Feature).hosts == ['"a"']


def test_partial_placeholder_policy_and_fallback_order(tmp_path):
    (tmp_path / "config.yaml").write_text(
        'feature:\n  enabled: "${FLAG:-true}"\ndatabase:\n  host: "pre-${HOST}-post"\n'
    )
    loader = ConfigLoader(root_dir=tmp_path, env_quote_policy={"database.host": "unwrap"})
    loader.register("feature", Feature)
    loader.register("database", Database)
    result = loader.load(environ={"FLAG": '"False"', "HOST": '"abc"'})
    assert not result.get("feature", Feature).enabled
    assert result.get("database", Database).host == "pre-abc-post"
    with pytest.raises(ConfigValidationError):
        loader.load(environ={"FLAG": '""', "HOST": "a"})
    (tmp_path / ".env").write_text('FLAG=""\nHOST=abc\n')
    assert loader.load(environ={}).get("feature", Feature).enabled


def test_whole_placeholder_complex_json(loader, tmp_path):
    (tmp_path / "config.yaml").write_text('feature:\n  hosts: "${HOSTS}"\n')
    result = loader.load(environ={"HOSTS": "'[\"${UNEXPANDED}\"]'"})
    assert result.get("feature", Feature).hosts == ["${UNEXPANDED}"]


def test_same_source_specificity_and_cross_source_priority(loader, tmp_path):
    (tmp_path / ".env").write_text("DATABASE__HOST=lower\n")
    result = loader.load(
        environ={
            "DATABASE": '{"host":"higher","pool":{"size":11,"timeout":2}}',
            "DATABASE__POOL": '{"size":12}',
            "DATABASE__POOL__SIZE": "13",
        }
    )
    db = result.get("database", Database)
    assert (db.host, db.pool.size, db.pool.timeout) == ("higher", 13, 2)


@pytest.mark.parametrize(
    "value",
    ["{bad", '{"host":"a","host":"b"}', '{"port":NaN}', '{"port":1e999}', "1", '"not-json"'],
)
def test_json_syntax_even_when_shadowed(loader, tmp_path, value):
    (tmp_path / ".env").write_text(f"DATABASE={value}\n")
    with pytest.raises(ConfigSourceError):
        loader.load(environ={"DATABASE": "{}"})


def test_virtual_ancestor_and_scalar_descendants(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, unknown="ignore")
    loader.register("primary", Database, path="database.primary")
    with pytest.raises(ConfigSourceError, match="virtual-ancestor"):
        loader.load(environ={"DATABASE": "{}"})
    for name in (
        "DATABASE__PRIMARY__HOST__TYPO",
        "DATABASE__PRIMARY__POOL__SIZE__TYPO",
    ):
        with pytest.raises(ConfigSourceError, match="invalid-descendant"):
            loader.load(environ={name: "x"})


def test_list_replacement_and_dynamic_dict_merge(loader, tmp_path):
    (tmp_path / "config.yaml").write_text(
        "feature:\n  hosts: [a, b]\n  labels: {CaseKey: lower, Other: kept}\n"
    )
    result = loader.load(
        environ={
            "FEATURE__HOSTS": '["new"]',
            "FEATURE__LABELS": '{"CaseKey":"higher"}',
        }
    ).get("feature", Feature)
    assert result.hosts == ["new"]
    assert result.labels == {"CaseKey": "higher", "Other": "kept"}
    with pytest.raises(ConfigSourceError):
        loader.load(environ={"FEATURE__HOSTS__0": "bad"})


def test_nullable_parent_barrier_and_schema_fallback(tmp_path):
    class App(ConfigModel):
        pool: Pool | None = Field(default_factory=lambda: {"size": 20, "timeout": 8})

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    (tmp_path / "config.yaml").write_text("app:\n  pool: null\n")
    result = loader.load(environ={"APP__POOL__TIMEOUT": "1"})
    assert result.get("app", App).pool.size == 10
    assert result.get("app", App).pool.timeout == 1
    assert "schema-fallback" in result.explain("app.pool.size").steps
    assert "null-or-scalar-barrier" in result.explain("app.pool.size").steps
    same_source = loader.load(
        environ={"APP__POOL": "null", "APP__POOL__TIMEOUT": "2"}
    )
    assert same_source.get("app", App).pool.size == 10


def test_nullable_complex_vs_scalar_null(tmp_path):
    class App(ConfigModel):
        hosts: list[str] | None = None
        number: int | None = None

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    assert loader.load(environ={"APP__HOSTS": '"null"'}).get("app", App).hosts is None
    with pytest.raises(ConfigValidationError):
        loader.load(environ={"APP__NUMBER": "null"})


def test_noncanonical_names_and_default_prefix(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("feature", Feature)
    result = loader.load(environ={"UNRELATED": "x", "feature__enabled": "true"})
    assert result.get("feature", Feature).enabled is (os.name == "nt")
    assert bool(result.source_report().noncanonical_variables) is (os.name != "nt")


def test_default_prefix_ignores_unrelated_and_prefixed_variables(loader):
    result = loader.load(environ={
        "DATABASE__HOST": "bare.internal",
        "PYDCONFIG_DATABASE__HOST": "prefixed.internal",
        "PATH": "unrelated",
        "UNRELATED__FIELD": "unused",
    })
    assert result.get("database", Database).host == "bare.internal"
    assert result.explain("database.host").defined_at.name == "DATABASE__HOST"
    with pytest.raises(ConfigValidationError, match="unknown-field"):
        loader.load(environ={"DATABASE__TYPO": "unknown"})


def test_explicit_legacy_prefix(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, env_prefix="PYDCONFIG_")
    loader.register("database", Database)
    result = loader.load(environ={
        "DATABASE__HOST": "bare.internal",
        "PYDCONFIG_DATABASE__HOST": "prefixed.internal",
    })
    assert result.get("database", Database).host == "prefixed.internal"


def test_double_underscore_separates_nested_fields(tmp_path):
    class App(ConfigModel):
        pool_size: int = 10
        pool: Pool = Field(default_factory=Pool)

    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app_settings", App)
    result = loader.load(environ={
        "APP_SETTINGS__POOL_SIZE": "20",
        "APP_SETTINGS__POOL__SIZE": "30",
        "APP_SETTINGS_POOL_SIZE": "99",
    }).get("app_settings", App)
    assert result.pool_size == 20
    assert result.pool.size == 30
    assert result.pool.timeout == 5.0


def test_binding_uses_pydantic_settings_delimiter(loader, tmp_path, monkeypatch):
    from pydconfig.settings import AggregateBase

    monkeypatch.setitem(AggregateBase.model_config, "env_nested_delimiter", "::")
    (tmp_path / ".env").write_text("DATABASE::POOL::SIZE=24\n")
    result = loader.load(environ={"DATABASE::HOST": "configured.internal"})
    database = result.get("database", Database)
    assert database.host == "configured.internal"
    assert database.pool.size == 24
    assert result.with_overrides({"database": {"port": 6000}}).get(
        "database", Database
    ).host == "configured.internal"
