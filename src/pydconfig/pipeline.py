"""Profile, sources, merge, pruning, interpolation and lexical input resolution."""

from __future__ import annotations

import os
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from .binding import bind, copy_environment
from .bootstrap import choose_profile
from .defaults import Catalog, fill_defaults, initial_defaults, materialize
from .errors import ConfigProfileError, ConfigSourceError, ConfigValidationError
from .lexical import interpolate, normalize
from .nodes import History, Node, check_limits, make_node, merge
from .provenance import SourceRef, SourceReport, SourceStatus
from .schema import Plan, index_plans
from .sources import read_dotenv, read_yaml


@dataclass(frozen=True)
class Options:
    root_dir: Path
    yaml_file: Path
    explicit_yaml: bool
    env_prefix: str
    dotenv: bool
    allowed_profiles: tuple[str, ...] | None
    require_profile_yaml: bool
    unknown: str
    quote_policy: tuple[tuple[str, str], ...]


@dataclass(repr=False)
class Resolution:
    node: Node
    catalog: Catalog
    history: History
    report: SourceReport
    profile: str | None

    def __repr__(self) -> str:
        return "<ResolvedInput redacted>"


def prune(
    node: Node, plan: Plan, unknown: str, ignored: list[str], path: tuple[str, ...] = ()
) -> Node:
    if plan.kind not in ("group", "model") or not isinstance(node.value, dict):
        return node
    values = {}
    for name, child in node.value.items():
        location = (*path, name)
        if name not in plan.fields:
            if unknown == "error":
                raise ConfigValidationError(
                    "unknown-field", path=".".join(location), source=child.ref
                )
            ignored.append(".".join(location))
        else:
            values[name] = prune(child, plan.fields[name], unknown, ignored, location)
    return replace(node, value=values)


def override_node(values: Mapping[str, Any] | None) -> Node:
    if values is not None and not isinstance(values, Mapping):
        raise ConfigSourceError("override-mapping")
    node = make_node({} if values is None else values, SourceRef("override", "overrides"))
    if "profile" in node.value:
        raise ConfigProfileError("profile-override")
    return node


def resolve_input(
    options: Options,
    root: Plan,
    *,
    profile: str | None,
    environ: Mapping[str, str] | None,
    overrides: Mapping[str, Any] | None,
) -> Resolution:
    policies = dict(options.quote_policy)
    plans = index_plans(root)
    for path in policies:
        plan = plans.get(tuple(path.split(".")))
        if plan is None or plan.kind == "group":
            raise ConfigSourceError("invalid-quote-policy-path", path=path)
    environment = copy_environment(environ)
    statuses: list[SourceStatus] = []
    ignored: list[str] = []
    noncanonical: list[SourceRef] = []
    budget = [0]
    history = History()
    base_yaml = read_yaml(options.yaml_file, options.explicit_yaml, statuses)
    base_dotenv: dict[str, str] = {}
    base_refs: dict[str, SourceRef] = {}
    if options.dotenv:
        base_dotenv, base_refs = read_dotenv(options.root_dir / ".env", statuses)
    else:
        statuses.append(SourceStatus("dotenv", str(options.root_dir / ".env"), "disabled"))
    chosen = choose_profile(
        profile, environment, base_dotenv, base_refs, base_yaml, options.allowed_profiles
    )
    profile_yaml: Node | None = None
    profile_dotenv: dict[str, str] = {}
    profile_refs: dict[str, SourceRef] = {}
    if options.require_profile_yaml and chosen is None:
        raise ConfigProfileError("profile-required")
    if chosen:
        profile_path = options.yaml_file.with_name(
            f"{options.yaml_file.stem}.{chosen}{options.yaml_file.suffix}"
        )
        profile_yaml = read_yaml(profile_path, options.require_profile_yaml, statuses)
        if profile_yaml and "profile" in profile_yaml.value:
            raise ConfigProfileError(
                "profile-redeclaration", source=profile_yaml.value["profile"].ref
            )
        if options.dotenv:
            profile_dotenv, profile_refs = read_dotenv(
                options.root_dir / f".env.{chosen}", statuses
            )
            if "PYDCONFIG_PROFILE" in profile_dotenv:
                raise ConfigProfileError(
                    "profile-redeclaration", source=profile_refs["PYDCONFIG_PROFILE"]
                )
        else:
            statuses.append(
                SourceStatus("dotenv", str(options.root_dir / f".env.{chosen}"), "disabled")
            )
    catalog = materialize(root)
    node = initial_defaults(root, catalog)
    for yaml in (base_yaml, profile_yaml):
        if yaml:
            yaml = replace(
                yaml, value={key: child for key, child in yaml.value.items() if key != "profile"}
            )
            node = merge(node, yaml, history)
    for values, refs, kind in (
        (base_dotenv, base_refs, "dotenv"),
        (profile_dotenv, profile_refs, "dotenv"),
        (environment, {}, "os"),
    ):
        bound = bind(
            values,
            refs,
            prefix=options.env_prefix,
            plans=plans,
            root=root,
            policies=policies,
            history=history,
            noncanonical=noncanonical,
            kind=kind,
            budget=budget,
        )
        check_limits(bound)
        node = merge(node, bound, history)
    node = merge(node, override_node(overrides), history)
    check_limits(node)
    node = prune(node, root, options.unknown, ignored)
    dotenv_view = {**base_dotenv, **profile_dotenv}
    dotenv_ref_view = {**base_refs, **profile_refs}

    def lookup(name: str) -> tuple[str, SourceRef] | None:
        os_key = name.upper() if os.name == "nt" else name
        if os_key in environment:
            return environment[os_key], SourceRef("os", os_key)
        if name in dotenv_view:
            return dotenv_view[name], dotenv_ref_view[name]
        return None

    node = interpolate(node, root, lookup, policies)
    node = fill_defaults(node, root, catalog)
    node = prune(node, root, options.unknown, ignored)
    node = normalize(node, root, policies)
    check_limits(node)
    return Resolution(
        node,
        catalog,
        history,
        SourceReport(tuple(statuses), tuple(ignored), tuple(noncanonical)),
        chosen,
    )


def replay_input(
    previous: Resolution, options: Options, root: Plan, overrides: Mapping[str, Any]
) -> Resolution:
    result = deepcopy(previous)
    ignored = list(result.report.ignored_paths)
    result.node = merge(result.node, override_node(overrides), result.history)
    check_limits(result.node)
    result.node = prune(result.node, root, options.unknown, ignored)
    result.node = fill_defaults(result.node, root, result.catalog)
    result.node = prune(result.node, root, options.unknown, ignored)
    result.node = normalize(result.node, root, dict(options.quote_policy))
    check_limits(result.node)
    result.report = replace(result.report, ignored_paths=tuple(dict.fromkeys(ignored)))
    return result
