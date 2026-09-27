"""Bind each environment source independently before applying source precedence."""

from __future__ import annotations

import os
from collections.abc import Mapping

from .errors import ConfigSourceError
from .lexical import decode_complex
from .nodes import MAX_FILE, History, Node, insert
from .provenance import SourceRef
from .schema import SEGMENT, Plan


def copy_environment(environ: Mapping[str, str] | None) -> dict[str, str]:
    values = dict(os.environ if environ is None else environ)
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in values.items()):
        raise ConfigSourceError("invalid-environment")
    if os.name != "nt":
        return values
    result: dict[str, str] = {}
    for key, value in values.items():
        canonical = key.upper()
        if canonical in result:
            raise ConfigSourceError("environment-name-collision")
        result[canonical] = value
    return result


def bind(
    values: Mapping[str, str],
    refs: Mapping[str, SourceRef],
    *,
    prefix: str,
    delimiter: str,
    plans: Mapping[tuple[str, ...], Plan],
    root: Plan,
    policies: Mapping[str, str],
    history: History,
    noncanonical: list[SourceRef],
    kind: str,
    budget: list[int],
) -> Node:
    candidates: list[tuple[tuple[str, ...], Node, Plan | None]] = []
    for name, value in values.items():
        if name == "PYDCONFIG_PROFILE":
            continue
        canonical = name.upper()
        if prefix and not canonical.startswith(prefix):
            continue
        remainder = canonical[len(prefix) :]
        parts = tuple(part.lower() for part in remainder.split(delimiter))
        if not prefix and (not parts or parts[0] not in root.fields):
            continue
        ref = refs.get(name, SourceRef(kind, name))
        if name != canonical:
            noncanonical.append(ref)
            continue
        if len(name) + len(value) > MAX_FILE:
            raise ConfigSourceError("environment-limit", source=ref)
        budget[0] += len(name.encode("utf-8")) + len(value.encode("utf-8"))
        if budget[0] > MAX_FILE:
            raise ConfigSourceError("environment-limit", source=ref)
        if len(".".join(parts)) > 128 or any(not SEGMENT.fullmatch(part) for part in parts):
            raise ConfigSourceError("invalid-environment-path", source=ref)
        for depth in range(1, len(parts)):
            ancestor = plans.get(parts[:depth])
            if ancestor and ancestor.kind not in ("model", "group"):
                raise ConfigSourceError("invalid-descendant", path=".".join(parts), source=ref)
        plan = plans.get(parts)
        if plan and plan.kind == "group":
            raise ConfigSourceError("virtual-ancestor-value", path=".".join(parts), source=ref)
        node = Node(value, ref, environment=True)
        if plan and plan.complex:
            node = decode_complex(node, plan, policies)
        candidates.append((parts, node, plan))
    # Model/container JSON structures are expanded before scalar leaf bindings.
    candidates.sort(
        key=lambda candidate: (
            0 if candidate[2] and candidate[2].complex else 1,
            len(candidate[0]),
            candidate[0],
        )
    )
    result = Node({}, SourceRef(kind, "<source>"))
    for path, node, _ in candidates:
        result = insert(result, path, node, history)
    return result
