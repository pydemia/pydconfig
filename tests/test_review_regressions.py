from __future__ import annotations

import pytest
from conftest import Database, Feature
from pydantic import computed_field

from pydconfig import ConfigLoader, ConfigModel, ConfigSourceError


def test_complete_merged_tree_limit_and_override_replay(loader, monkeypatch):
    monkeypatch.setattr("pydconfig.nodes.MAX_NODES", 20)
    # Each source fits, but their union exceeds the total tree budget.
    first = {f"a{i}": "value" for i in range(5)}
    second = {f"b{i}": "value" for i in range(5)}
    original = loader.load(environ={}, overrides={"feature": {"labels": first}})
    with pytest.raises(ConfigSourceError, match="input-limit"):
        original.with_overrides({"feature": {"labels": second}})
    assert original.get("feature", Feature).labels == first


def test_environment_budget_counts_all_sources(tmp_path, monkeypatch):
    class App(ConfigModel):
        a: str = ""
        b: str = ""

    (tmp_path / ".env").write_text("APP__A=" + "a" * 20)
    (tmp_path / ".env.test").write_text("APP__B=" + "b" * 20)
    monkeypatch.setattr("pydconfig.binding.MAX_FILE", 75)
    loader = ConfigLoader(root_dir=tmp_path)
    loader.register("app", App)
    with pytest.raises(ConfigSourceError, match="environment-limit"):
        loader.load(profile="test", environ={"APP__A": "c" * 20})


@pytest.mark.parametrize("template,value", [("${RAW}", "v" * 101), ("${RAW}${RAW}", "v" * 60)])
def test_interpolation_limits_unprefixed_and_repeated_values(
    loader, tmp_path, monkeypatch, template, value
):
    (tmp_path / "config.yaml").write_text('database:\n  host: "' + template + '"\n')
    monkeypatch.setattr("pydconfig.lexical.MAX_FILE", 100)
    with pytest.raises(ConfigSourceError, match="input-limit"):
        loader.load(environ={"RAW": value})


def test_whole_model_placeholder_dependencies_reach_leaf(loader, tmp_path):
    (tmp_path / "config.yaml").write_text('database: "${DB}"\n')
    result = loader.load(environ={"DB": '{"host":"remote","port":6000}'})
    assert result.get("database", Database).port == 6000
    explanation = result.explain("database.host")
    assert [(ref.kind, ref.name) for ref in explanation.references] == [("os", "DB")]
    assert explanation.defined_at.kind == "yaml"


def test_pretty_repr_does_not_evaluate_computed_fields(tmp_path):
    calls = []

    class App(ConfigModel):
        value: str = "example-secret"

        @computed_field
        @property
        def derived(self) -> str:
            calls.append("computed")
            return self.value

    loader = ConfigLoader(root_dir=tmp_path, dotenv=False)
    loader.register("app", App)
    result = loader.load(environ={}).get("app", App)
    assert "example-secret" not in repr(result)
    assert list(result.__repr_args__()) == []
    assert calls == []


def test_windows_environment_case_collision(loader, monkeypatch):
    monkeypatch.setattr("pydconfig.binding.os.name", "nt")
    with pytest.raises(ConfigSourceError, match="environment-name-collision"):
        loader.load(environ={"DATABASE__HOST": "one", "database__host": "two"})
