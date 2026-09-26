"""Materialize raw defaults once per load, without constructing nested models."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import replace
from typing import Any, cast

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from .errors import ConfigValidationError
from .nodes import Node, make_node
from .provenance import SourceRef
from .schema import Plan

Catalog = dict[tuple[str, ...], Node]


def materialize(root: Plan) -> Catalog:
    catalog: Catalog = {}

    def visit(plan: Plan) -> None:
        for child in plan.fields.values():
            visit(child)
        info = plan.info
        if info is None:
            return
        ref = SourceRef("default", ".".join(plan.path))
        if info.default_factory is not None:
            if plan.kind == "model" and info.default_factory is plan.annotation:
                catalog[plan.path] = Node(
                    {
                        name: deepcopy(catalog[child.path])
                        for name, child in plan.fields.items()
                        if child.path in catalog
                    },
                    ref,
                )
                return
            value: Any = None
            failed = False
            try:
                value = cast(Callable[[], Any], info.default_factory)()
            except Exception:
                failed = True
            if failed:
                raise ConfigValidationError(
                    "default-factory-failed", path=".".join(plan.path), source=ref
                )
            if isinstance(value, BaseModel):
                raise ConfigValidationError(
                    "model-instance-default", path=".".join(plan.path), source=ref
                )
            catalog[plan.path] = make_node(value, ref)
        elif info.default is not PydanticUndefined:
            catalog[plan.path] = make_node(info.default, ref)

    visit(root)
    return catalog


def initial_defaults(root: Plan, catalog: Catalog) -> Node:
    def body(plan: Plan) -> Node:
        values = {}
        for name, child in plan.fields.items():
            if child.kind == "group":
                values[name] = body(child)
            elif child.info is None and child.kind == "model":
                values[name] = body(child)
            elif child.path in catalog:
                values[name] = deepcopy(catalog[child.path])
        return Node(values, SourceRef("default", ".".join(plan.path)))

    return body(root)


def fill_defaults(node: Node, plan: Plan, catalog: Catalog) -> Node:
    if plan.kind not in ("model", "group") or not isinstance(node.value, dict):
        return node
    values = dict(node.value)
    for name, child in plan.fields.items():
        if name not in values and child.path in catalog:
            fallback = deepcopy(catalog[child.path])
            values[name] = replace(fallback, steps=(*fallback.steps, "schema-fallback"))
        if name in values:
            values[name] = fill_defaults(values[name], child, catalog)
    return replace(node, value=values)
