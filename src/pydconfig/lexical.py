"""One-pass environment quoting, interpolation and fixed scalar lexical rules."""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Mapping
from dataclasses import replace

from pydantic import TypeAdapter, ValidationError

from .errors import ConfigInterpolationError, ConfigSourceError, ConfigValidationError
from .nodes import MAX_FILE, Node
from .provenance import SourceRef
from .schema import Plan
from .sources import strict_json

ASCII_SPACE = " \t\r\n\v\f"
VARIABLE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


def unwrap(value: str, *, trim: bool) -> tuple[str, bool]:
    candidate = value.strip(ASCII_SPACE) if trim else value
    if len(candidate) >= 2 and candidate[0] == candidate[-1] and candidate[0] in "\"'":
        return candidate[1:-1], True
    return (candidate if trim else value), False


def environment_quote(value: str, plan: Plan, policies: Mapping[str, str]) -> tuple[str, bool]:
    policy = policies.get(".".join(plan.path))
    if policy == "preserve":
        return value, False
    kind = plan.scalar_kind if plan.kind == "literal" else plan.kind
    if policy == "unwrap" or plan.complex or kind in ("bool", "int", "float"):
        return unwrap(value, trim=plan.complex or kind in ("bool", "int", "float"))
    return value, False


def decode_complex(node: Node, plan: Plan, policies: Mapping[str, str]) -> Node:
    if not isinstance(node.value, str):
        return node
    text = node.value
    changed = False
    if node.environment and not node.normalized:
        text, changed = environment_quote(text, plan, policies)
    decoded = strict_json(text, node.ref)
    if not isinstance(decoded.value, (dict, list)) and not (
        decoded.value is None and plan.nullable
    ):
        raise ConfigSourceError("json-root", path=".".join(plan.path), source=node.ref)
    result = replace(
        decoded,
        references=node.references,
        normalized=True,
        steps=(*node.steps, *(("env-quote-unwrapped",) if changed else ())),
    )

    def inherit(child: Node) -> Node:
        value = child.value
        if isinstance(value, dict):
            value = {key: inherit(item) for key, item in value.items()}
        elif isinstance(value, list):
            value = [inherit(item) for item in value]
        return replace(child, value=value, references=result.references, steps=result.steps)

    # A YAML whole-model placeholder is also the dependency of each decoded leaf.
    value = result.value
    if isinstance(value, dict):
        value = {key: inherit(item) for key, item in value.items()}
    elif isinstance(value, list):
        value = [inherit(item) for item in value]
    return replace(result, value=value)


Resolver = Callable[[str], tuple[str, SourceRef] | None]


def interpolate(node: Node, plan: Plan, resolve: Resolver, policies: Mapping[str, str]) -> Node:
    if isinstance(node.value, dict):
        return replace(
            node,
            value={
                key: interpolate(
                    child,
                    plan.fields[key] if plan.kind in ("model", "group") else plan.element or plan,
                    resolve,
                    policies,
                )
                for key, child in node.value.items()
            },
        )
    if isinstance(node.value, list):
        return replace(
            node,
            value=[
                interpolate(child, plan.element or plan, resolve, policies) for child in node.value
            ],
        )
    if not node.yaml or not isinstance(node.value, str):
        return node
    text = node.value
    parts: list[str] = []
    output_size = 0

    def append(part: str) -> None:
        nonlocal output_size
        if len(part) > MAX_FILE:
            raise ConfigSourceError("input-limit", path=".".join(plan.path), source=node.ref)
        output_size += len(part.encode("utf-8"))
        if output_size > MAX_FILE:
            raise ConfigSourceError("input-limit", path=".".join(plan.path), source=node.ref)
        parts.append(part)

    references: list[SourceRef] = []
    position = 0
    whole_environment = False
    whole_placeholder = False
    unwrapped = False
    while position < len(text):
        if text.startswith("$${", position):
            end = text.find("}", position + 3)
            if end < 0:
                raise ConfigInterpolationError(
                    "placeholder-syntax", path=".".join(plan.path), source=node.ref
                )
            append(text[position + 1 : end + 1])
            position = end + 1
        elif text.startswith("${", position):
            end = text.find("}", position + 2)
            if end < 0:
                raise ConfigInterpolationError(
                    "placeholder-syntax", path=".".join(plan.path), source=node.ref
                )
            body = text[position + 2 : end]
            name, separator, fallback = body.partition(":-")
            if not VARIABLE.fullmatch(name) or "${" in fallback:
                raise ConfigInterpolationError(
                    "placeholder-syntax", path=".".join(plan.path), source=node.ref
                )
            found = resolve(name)
            if found is not None:
                references.append(found[1])
            used_environment = found is not None and (not separator or found[0] != "")
            if used_environment:
                value = found[0] if found is not None else ""
            elif separator:
                value = fallback
            else:
                raise ConfigInterpolationError(
                    "missing-variable",
                    path=".".join(plan.path),
                    source=SourceRef("environment-reference", name),
                )
            is_whole = position == 0 and end == len(text) - 1
            whole_placeholder = is_whole
            if used_environment and is_whole:
                whole_environment = True
            elif used_environment and policies.get(".".join(plan.path)) == "unwrap":
                value, changed = unwrap(value, trim=False)
                unwrapped = unwrapped or changed
            append(value)
            position = end + 1
        else:
            append(text[position])
            position += 1
    value = "".join(parts)
    if len(value.encode("utf-8")) > MAX_FILE:
        raise ConfigSourceError("input-limit", path=".".join(plan.path), source=node.ref)
    result = replace(
        node,
        value=value,
        yaml=False,
        environment=whole_environment,
        references=tuple(dict.fromkeys(references)),
        steps=(*node.steps, *(("env-quote-unwrapped",) if unwrapped else ())),
    )
    return decode_complex(result, plan, policies) if plan.complex and whole_placeholder else result


def normalize(node: Node, plan: Plan, policies: Mapping[str, str]) -> Node:
    if node.value is None:
        return node
    if plan.kind in ("group", "model") and isinstance(node.value, dict):
        return replace(
            node,
            value={
                key: normalize(child, plan.fields[key], policies)
                for key, child in node.value.items()
            },
        )
    if plan.kind in ("list", "tuple") and isinstance(node.value, list) and plan.element:
        return replace(
            node, value=[normalize(child, plan.element, policies) for child in node.value]
        )
    if plan.kind == "dict" and isinstance(node.value, dict) and plan.element:
        return replace(
            node,
            value={
                key: normalize(child, plan.element, policies) for key, child in node.value.items()
            },
        )
    if node.normalized:
        return node
    value = node.value
    steps = node.steps
    if node.environment and isinstance(value, str):
        value, changed = environment_quote(value, plan, policies)
        if changed:
            steps = (*steps, "env-quote-unwrapped")
    kind = plan.scalar_kind if plan.kind == "literal" else plan.kind
    if kind == "bool":
        if type(value) is bool:
            pass
        elif type(value) is int and value in (0, 1):
            value = value == 1
        elif isinstance(value, str) and value.strip(ASCII_SPACE).lower() in (
            "true",
            "false",
            "1",
            "0",
        ):
            value = value.strip(ASCII_SPACE).lower() in ("true", "1")
        else:
            raise ConfigValidationError(
                "invalid-boolean", path=".".join(plan.path), source=node.ref, expected="bool"
            )
        steps = (*steps, "boolean-parsed")
    elif kind in ("int", "float"):
        failed = False
        try:
            value = TypeAdapter(int if kind == "int" else float).validate_python(value)
        except ValidationError:
            failed = True
        if failed:
            raise ConfigValidationError(
                "invalid-number", path=".".join(plan.path), source=node.ref, expected=kind
            )
        if isinstance(value, float) and not math.isfinite(value):
            raise ConfigValidationError(
                "nonfinite-number", path=".".join(plan.path), source=node.ref
            )
    return replace(node, value=value, environment=False, normalized=True, steps=steps)
