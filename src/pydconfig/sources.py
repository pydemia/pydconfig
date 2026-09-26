"""Bounded, strict file readers. No reader modifies the process environment."""

from __future__ import annotations

import json
import math
import re
from dataclasses import replace
from io import StringIO
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values
from dotenv.parser import parse_stream
from yaml.nodes import MappingNode, ScalarNode, SequenceNode
from yaml.tokens import AliasToken, AnchorToken, TagToken

from .errors import ConfigSourceError
from .nodes import MAX_DEPTH, MAX_FILE, MAX_JSON, MAX_NODES, Node, make_node
from .provenance import SourceRef, SourceStatus


class ConfigYamlLoader(yaml.SafeLoader):
    yaml_implicit_resolvers: dict[Any, Any] = {}


ConfigYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(true|false)$"), list("tf")
)
ConfigYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:null", re.compile(r"^(null|~|)$"), ["n", "~", ""]
)
ConfigYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:int", re.compile(r"^-?(0|[1-9][0-9]*)$"), list("-0123456789")
)
ConfigYamlLoader.add_implicit_resolver(
    "tag:yaml.org,2002:float",
    re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+(?:[eE][+-]?[0-9]+)?|[eE][+-]?[0-9]+)$"),
    list("-0123456789"),
)


def read_text(path: Path, kind: str, required: bool, statuses: list[SourceStatus]) -> str | None:
    ref = SourceRef(kind, str(path))
    failure: ConfigSourceError | None = None
    content: bytes | None = None
    try:
        with path.open("rb") as stream:
            content = stream.read(MAX_FILE + 1)
    except FileNotFoundError:
        if required:
            failure = ConfigSourceError("missing-file", source=ref)
        else:
            statuses.append(SourceStatus(kind, str(path), "skipped-missing"))
    except OSError:
        failure = ConfigSourceError("file-read", source=ref)
    if failure:
        raise failure
    if content is None:
        return None
    if len(content) > MAX_FILE:
        raise ConfigSourceError("file-limit", source=ref)
    text: str | None = None
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError:
        failure = ConfigSourceError("file-encoding", source=ref)
    if failure:
        raise failure
    statuses.append(SourceStatus(kind, str(path), "loaded"))
    return text


def read_yaml(path: Path, required: bool, statuses: list[SourceStatus]) -> Node | None:
    text = read_text(path, "yaml", required, statuses)
    if text is None:
        return None
    ref = SourceRef("yaml", str(path))
    failure: ConfigSourceError | None = None
    document = None
    try:
        for token in yaml.scan(text, Loader=ConfigYamlLoader):
            if isinstance(token, (AliasToken, AnchorToken, TagToken)):
                raise ConfigSourceError("unsupported-yaml-feature", source=ref)
        document = yaml.compose(text, Loader=ConfigYamlLoader)
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        location = replace(ref, line=mark.line + 1, column=mark.column + 1) if mark else ref
        failure = ConfigSourceError("yaml-syntax", source=location)
    except RecursionError:
        failure = ConfigSourceError("input-limit", source=ref)
    if failure:
        raise failure
    if not isinstance(document, MappingNode):
        raise ConfigSourceError("yaml-root-mapping", source=ref)
    count = 0

    def convert(item: Any, depth: int) -> Node:
        nonlocal count
        count += 1
        location = replace(ref, line=item.start_mark.line + 1, column=item.start_mark.column + 1)
        if count > MAX_NODES or depth > MAX_DEPTH:
            raise ConfigSourceError("input-limit", source=location)
        value: Any
        if isinstance(item, MappingNode):
            value = {}
            for key, child in item.value:
                count += 1
                if count > MAX_NODES:
                    raise ConfigSourceError("input-limit", source=location)
                if not isinstance(key, ScalarNode) or key.tag != "tag:yaml.org,2002:str":
                    raise ConfigSourceError("non-string-key", source=location)
                if key.value == "<<":
                    raise ConfigSourceError("yaml-merge-key", source=location)
                if key.value in value:
                    raise ConfigSourceError(
                        "duplicate-key",
                        source=replace(
                            ref, line=key.start_mark.line + 1, column=key.start_mark.column + 1
                        ),
                    )
                value[key.value] = convert(child, depth + 1)
        elif isinstance(item, SequenceNode):
            value = [convert(child, depth + 1) for child in item.value]
        elif isinstance(item, ScalarNode):
            suffix = item.tag.rsplit(":", 1)[-1]
            if suffix == "str":
                value = item.value
            elif suffix == "bool":
                value = item.value == "true"
            elif suffix == "null":
                value = None
            elif suffix == "int":
                value = int(item.value)
            elif suffix == "float":
                value = float(item.value)
                if not math.isfinite(value):
                    raise ConfigSourceError("nonfinite-number", source=location)
            else:
                raise ConfigSourceError("unsupported-yaml-tag", source=location)
        else:
            raise ConfigSourceError("unsupported-yaml-node", source=location)
        return Node(value, location, yaml=True)

    return convert(document, 0)


def read_dotenv(
    path: Path, statuses: list[SourceStatus]
) -> tuple[dict[str, str], dict[str, SourceRef]]:
    text = read_text(path, "dotenv", False, statuses)
    if text is None:
        return {}, {}
    refs: dict[str, SourceRef] = {}
    for binding in parse_stream(StringIO(text)):
        ref = SourceRef("dotenv", str(path), line=binding.original.line)
        if binding.error:
            raise ConfigSourceError("dotenv-syntax", source=ref)
        if binding.key is None:
            continue
        if binding.key in refs:
            raise ConfigSourceError("duplicate-key", source=ref)
        if binding.value is None:
            raise ConfigSourceError("dotenv-missing-value", source=ref)
        refs[binding.key] = ref
    values = dotenv_values(stream=StringIO(text), interpolate=False)
    return {key: value for key, value in values.items() if value is not None}, refs


def strict_json(text: str, ref: SourceRef) -> Node:
    if len(text.encode("utf-8")) > MAX_JSON:
        raise ConfigSourceError("json-limit", source=ref)

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate")
            result[key] = value
        return result

    def constant(_: str) -> Any:
        raise ValueError("nonfinite")

    def finite_float(text: str) -> float:
        number = float(text)
        if not math.isfinite(number):
            raise ValueError("nonfinite")
        return number

    failed = False
    value: Any = None
    try:
        value = json.loads(
            text, object_pairs_hook=pairs, parse_constant=constant, parse_float=finite_float
        )
    except (ValueError, RecursionError):
        failed = True
    if failed:
        raise ConfigSourceError("json-syntax", source=ref)
    return make_node(value, ref)
