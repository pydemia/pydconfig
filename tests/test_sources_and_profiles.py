from __future__ import annotations

import pytest
import yaml
from conftest import Database, Feature

from pydconfig import (
    ConfigInterpolationError,
    ConfigLoader,
    ConfigModel,
    ConfigProfileError,
    ConfigSourceError,
)


@pytest.mark.parametrize(
    "stage, expected", [(0, 10), (1, 11), (2, 12), (3, 13), (4, 14), (5, 15), (6, 16)]
)
def test_source_precedence(loader, tmp_path, stage, expected):
    files = [
        ("config.yaml", "database:\n  pool:\n    size: 11\n"),
        ("config.test.yaml", "database:\n  pool:\n    size: 12\n"),
        (".env", "PYDCONFIG_DATABASE__POOL__SIZE=13\n"),
        (".env.test", "PYDCONFIG_DATABASE__POOL__SIZE=14\n"),
    ]
    for name, content in files[:stage]:
        (tmp_path / name).write_text(content)
    env = {"PYDCONFIG_DATABASE__POOL__SIZE": "15"} if stage >= 5 else {}
    overrides = {"database": {"pool": {"size": 16}}} if stage == 6 else None
    result = loader.load(profile="test", environ=env, overrides=overrides)
    assert result.get("database", Database).pool.size == expected
    assert result.profile == "test"


@pytest.mark.parametrize(
    "explicit, env, dot, yaml_profile, expected",
    [
        ("prd", "stg", "test", "local", "prd"),
        (None, "stg", "test", "local", "stg"),
        (None, None, "test", "local", "test"),
        (None, None, None, "local", "local"),
        (None, None, None, None, None),
    ],
)
def test_profile_precedence(loader, tmp_path, explicit, env, dot, yaml_profile, expected):
    if dot is not None:
        (tmp_path / ".env").write_text(f"PYDCONFIG_PROFILE={dot}\n")
    if yaml_profile is not None:
        (tmp_path / "config.yaml").write_text(f"profile: {yaml_profile}\n")
    environ = {"PYDCONFIG_PROFILE": env} if env is not None else {}
    assert loader.load(profile=explicit, environ=environ).profile == expected


@pytest.mark.parametrize("value", ["", "Local", "../prd", "${PROFILE}", "a/b", "x" * 129])
def test_invalid_profile_is_not_fallback(loader, value):
    with pytest.raises(ConfigProfileError):
        loader.load(environ={"PYDCONFIG_PROFILE": value})


def test_invalid_lower_profile_still_fails(loader, tmp_path):
    (tmp_path / "config.yaml").write_text("profile: true\n")
    with pytest.raises(ConfigProfileError):
        loader.load(profile="test", environ={})


@pytest.mark.parametrize(
    "filename, text",
    [
        ("config.test.yaml", "profile: test\n"),
        (".env.test", "PYDCONFIG_PROFILE=test\n"),
    ],
)
def test_profile_redeclaration(loader, tmp_path, filename, text):
    (tmp_path / filename).write_text(text)
    with pytest.raises(ConfigProfileError, match="profile-redeclaration"):
        loader.load(profile="test", environ={})


def test_custom_prefix_does_not_change_profile_control(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, env_prefix="MYAPP_", allowed_profiles=["test"])
    loader.register("database", Database)
    result = loader.load(environ={"PYDCONFIG_PROFILE": "test", "MYAPP_DATABASE__PORT": "5000"})
    assert result.profile == "test"
    assert result.get("database", Database).port == 5000
    with pytest.raises(ConfigProfileError):
        loader.load(profile="typo", environ={})


def test_dotenv_disable_skips_profile_candidate(tmp_path):
    (tmp_path / ".env").write_text("PYDCONFIG_PROFILE=INVALID\nBAD\n")
    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("feature", Feature)
    result = loader.load(environ={})
    assert result.profile is None
    assert any(item.status == "disabled" for item in result.source_report().sources)


def test_require_profile_yaml_and_explicit_file(tmp_path):
    loader = ConfigLoader(root_dir=tmp_path, require_profile_yaml=True)
    loader.register("feature", Feature)
    with pytest.raises(ConfigProfileError, match="profile-required"):
        loader.load(environ={})
    with pytest.raises(ConfigSourceError, match="missing-file"):
        loader.load(profile="test", environ={})
    (tmp_path / "config.test.yaml").write_text("{}\n")
    assert loader.load(profile="test", environ={}).profile == "test"
    explicit = ConfigLoader(root_dir=tmp_path, yaml_file="service.yml")
    explicit.register("feature", Feature)
    with pytest.raises(ConfigSourceError):
        explicit.load(environ={})
    (tmp_path / "service.yml").write_text("{}\n")
    (tmp_path / "service.test.yml").write_text("feature:\n  enabled: true\n")
    assert explicit.load(profile="test", environ={}).get("feature", Feature).enabled


@pytest.mark.parametrize(
    "text",
    [
        "database: {}\ndatabase: {}\n",
        "database: {host: a, host: b}\n",
        "database: &anchor {}\n",
        "database: *anchor\n",
        "database: !!str value\n",
        "database: {<<: {host: a}}\n",
        "{}\n---\n{}\n",
        "[]\n",
        "1: value\n",
        "database: [\n",
        "",
    ],
)
def test_strict_yaml(loader, tmp_path, text):
    (tmp_path / "config.yaml").write_text(text)
    with pytest.raises(ConfigSourceError):
        loader.load(environ={}, overrides={"database": {"host": "shadow"}})


@pytest.mark.parametrize("text", ["A=1\nA=2\n", "A\n", 'A="unterminated\n', 'A="ok" trailing\n'])
def test_strict_dotenv(loader, tmp_path, text):
    (tmp_path / ".env").write_text(text)
    with pytest.raises(ConfigSourceError):
        loader.load(environ={})


def test_yaml_subset_and_global_loader_isolation(tmp_path):
    class Values(ConfigModel):
        leading: str
        hex: str
        yes: str
        date: str
        upper: str
        empty: str | None
        scientific: float

    (tmp_path / "config.yaml").write_text(
        "values:\n  leading: 0012\n  hex: 0x10\n  yes: on\n  date: 2026-09-26\n"
        "  upper: TRUE\n  empty:\n  scientific: 1e3\n"
    )
    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("values", Values)
    result = loader.load(environ={}).get("values", Values)
    assert (result.leading, result.hex, result.yes, result.date, result.upper) == (
        "0012",
        "0x10",
        "on",
        "2026-09-26",
        "TRUE",
    )
    assert result.empty is None and result.scientific == 1000.0
    assert yaml.safe_load("flag: on")["flag"] is True


@pytest.mark.parametrize(
    "value, expected", [(None, "fallback"), ("", "fallback"), ("present", "present")]
)
def test_interpolation_fallback(loader, tmp_path, value, expected):
    (tmp_path / "config.yaml").write_text('database:\n  host: "${HOST:-fallback}"\n')
    env = {} if value is None else {"HOST": value}
    result = loader.load(environ=env)
    assert result.get("database", Database).host == expected


def test_interpolation_is_single_pass_and_preserves_structure(loader, tmp_path):
    (tmp_path / ".env").write_text("A=${B}\nB=expanded\n")
    (tmp_path / "config.yaml").write_text(
        'database:\n  host: "${A}"\nfeature:\n  hosts: ["$${B}", "prefix-${TEXT}"]\n'
    )
    result = loader.load(environ={"TEXT": 'a:\nb"c'})
    assert result.get("database", Database).host == "${B}"
    assert result.get("feature", Feature).hosts == ["${B}", 'prefix-a:\nb"c']
    assert result.explain("feature.hosts").references[0].name == "TEXT"


@pytest.mark.parametrize(
    "placeholder", ["${MISSING}", "${A-default}", "${A:default}", "${A:-${B}}", "${A"]
)
def test_interpolation_errors(loader, tmp_path, placeholder):
    (tmp_path / "config.yaml").write_text(f"database:\n  host: {placeholder!r}\n")
    with pytest.raises(ConfigInterpolationError):
        loader.load(environ={})


def test_shadowed_missing_and_ignored_subtree(tmp_path):
    (tmp_path / "config.yaml").write_text(
        'database:\n  host: "${MISSING}"\nunused:\n  field: "${ALSO_MISSING}"\n'
    )
    loader = ConfigLoader(root_dir=tmp_path, unknown="ignore")
    loader.register("database", Database)
    result = loader.load(environ={"PYDCONFIG_DATABASE__HOST": "winner"})
    assert result.get("database", Database).host == "winner"
    assert result.source_report().ignored_paths == ("unused",)


def test_reference_environment_precedence_and_empty_os(loader, tmp_path):
    (tmp_path / ".env").write_text("HOST=base\n")
    (tmp_path / ".env.test").write_text("HOST=profile\n")
    (tmp_path / "config.yaml").write_text('database:\n  host: "${HOST}"\n')
    assert loader.load(profile="test", environ={}).get("database", Database).host == "profile"
    assert loader.load(profile="test", environ={"HOST": ""}).get("database", Database).host == ""


def test_root_frozen_at_construction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    loader = ConfigLoader()
    loader.register("feature", Feature)
    (tmp_path / "config.yaml").write_text("feature:\n  enabled: true\n")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert loader.load(environ={}).get("feature", Feature).enabled


@pytest.mark.parametrize(
    "filename, content",
    [
        ("config.yaml", b"x" * (1024 * 1024 + 1)),
        (".env", b"x" * (1024 * 1024 + 1)),
        ("config.yaml", b"\xff\xfe"),
    ],
)
def test_file_limits_encoding(loader, tmp_path, filename, content):
    (tmp_path / filename).write_bytes(content)
    with pytest.raises(ConfigSourceError):
        loader.load(environ={})


def test_utf8_bom(loader, tmp_path):
    (tmp_path / "config.yaml").write_bytes(b"\xef\xbb\xbffeature:\n  enabled: true\n")
    (tmp_path / ".env").write_bytes(b"\xef\xbb\xbfPYDCONFIG_DATABASE__PORT=5000\n")
    result = loader.load(environ={})
    assert result.get("feature", Feature).enabled
    assert result.get("database", Database).port == 5000
