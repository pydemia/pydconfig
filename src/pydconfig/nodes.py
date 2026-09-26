"""Private input trees and merge history. Reprs never include stored data."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import AnyUrl, BaseModel, CockroachDsn, MongoDsn, NatsDsn, PostgresDsn, SecretStr

from .errors import ConfigSourceError
from .provenance import SourceRef

MAX_FILE = 1024 * 1024
MAX_NODES = 10_000
MAX_DEPTH = 32
MAX_JSON = 64 * 1024


@dataclass(frozen=True, repr=False)
class Node:
    value: Any
    ref: SourceRef
    yaml: bool = False
    environment: bool = False
    normalized: bool = False
    barrier: bool = False
    references: tuple[SourceRef, ...] = ()
    steps: tuple[str, ...] = ()

    def __repr__(self) -> str:
        return "<configuration node redacted>"


@dataclass(repr=False)
class History:
    shadowed: dict[tuple[str, ...], list[SourceRef]] = field(default_factory=dict)
    barriers: set[tuple[str, ...]] = field(default_factory=set)

    def __repr__(self) -> str:
        return "<configuration history redacted>"


def make_node(value: Any, ref: SourceRef, *, yaml: bool = False, environment: bool = False) -> Node:
    count = 0

    def visit(item: Any, depth: int) -> Node:
        nonlocal count
        count += 1
        if depth > MAX_DEPTH or count > MAX_NODES:
            raise ConfigSourceError("input-limit", source=ref)
        if isinstance(item, BaseModel):
            raise ConfigSourceError("model-instance-input", source=ref)
        if isinstance(item, Mapping):
            if any(not isinstance(key, str) for key in item):
                raise ConfigSourceError("non-string-key", source=ref)
            result: Any = {key: visit(child, depth + 1) for key, child in item.items()}
        elif isinstance(item, (list, tuple)):
            result = [visit(child, depth + 1) for child in item]
        elif item is None or isinstance(
            item,
            (
                str,
                bool,
                int,
                float,
                Path,
                Enum,
                SecretStr,
                AnyUrl,
                PostgresDsn,
                CockroachDsn,
                MongoDsn,
                NatsDsn,
            ),
        ):
            result = deepcopy(item)
        else:
            raise ConfigSourceError("unsupported-input", source=ref)
        return Node(result, ref, yaml=yaml, environment=environment)

    return visit(value, 0)


def raw(node: Node) -> Any:
    if isinstance(node.value, dict):
        return {key: raw(child) for key, child in node.value.items()}
    if isinstance(node.value, list):
        return [raw(child) for child in node.value]
    return deepcopy(node.value)


def check_limits(node: Node) -> None:
    """Limit the complete tree, including paths added around decoded JSON."""
    stack = [(node, 0)]
    count = 0
    while stack:
        item, depth = stack.pop()
        count += 1
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ConfigSourceError("input-limit", source=item.ref)
        children = (
            item.value.values()
            if isinstance(item.value, dict)
            else (item.value if isinstance(item.value, list) else ())
        )
        stack.extend((child, depth + 1) for child in children)


def remember(node: Node, path: tuple[str, ...], history: History) -> None:
    refs = history.shadowed.setdefault(path, [])
    if node.ref not in refs:
        refs.append(node.ref)
    if isinstance(node.value, dict):
        for key, child in node.value.items():
            remember(child, (*path, key), history)


def merge(lower: Node, higher: Node, history: History, path: tuple[str, ...] = ()) -> Node:
    if isinstance(lower.value, dict) and isinstance(higher.value, dict) and not higher.barrier:
        data = dict(lower.value)
        for key, child in higher.value.items():
            data[key] = merge(data[key], child, history, (*path, key)) if key in data else child
        if lower.ref != higher.ref:
            history.shadowed.setdefault(path, []).append(lower.ref)
        return replace(higher, value=data, barrier=lower.barrier)
    remember(lower, path, history)
    if isinstance(lower.value, dict) or higher.barrier:
        history.barriers.add(path)
    # Preserve a same-source scalar/null barrier when a descendant reconstructs a map.
    return replace(higher, barrier=higher.barrier or isinstance(higher.value, dict))


def insert(root: Node, path: tuple[str, ...], value: Node, history: History) -> Node:
    def descend(parent: Node, rest: tuple[str, ...], current: tuple[str, ...]) -> Node:
        if not rest:
            return merge(parent, value, history, current)
        if not isinstance(parent.value, dict):
            remember(parent, current, history)
            history.barriers.add(current)
            parent = Node({}, value.ref, barrier=True)
        data = dict(parent.value)
        key = rest[0]
        if key in data:
            data[key] = descend(data[key], rest[1:], (*current, key))
        elif len(rest) == 1:
            data[key] = value
        else:
            data[key] = descend(Node({}, value.ref), rest[1:], (*current, key))
        return replace(parent, value=data)

    return descend(root, path, ())


def find_node(root: Node, path: tuple[str, ...]) -> Node | None:
    node = root
    for key in path:
        if not isinstance(node.value, dict) or key not in node.value:
            return None
        node = node.value[key]
    return node


def all_references(node: Node) -> tuple[SourceRef, ...]:
    result = list(node.references)
    children = (
        node.value.values()
        if isinstance(node.value, dict)
        else (node.value if isinstance(node.value, list) else ())
    )
    for child in children:
        result.extend(all_references(child))
    return tuple(dict.fromkeys(result))
