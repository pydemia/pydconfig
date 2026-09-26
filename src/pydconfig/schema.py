"""Compile the explicitly supported schema using public Pydantic metadata."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path, PosixPath, WindowsPath
from types import UnionType
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from pydantic import AnyUrl, BaseModel, CockroachDsn, MongoDsn, NatsDsn, PostgresDsn, SecretStr
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined
from pydantic_settings import BaseSettings

from .errors import ConfigRegistrationError
from .model import ConfigModel

SEGMENT = re.compile(r"[a-z][a-z0-9_]*\Z")
URL_TYPES = (AnyUrl, PostgresDsn, CockroachDsn, MongoDsn, NatsDsn)


@dataclass(repr=False)
class Plan:
    path: tuple[str, ...]
    kind: str
    annotation: Any = None
    nullable: bool = False
    fields: dict[str, Plan] = field(default_factory=dict)
    element: Plan | None = None
    info: FieldInfo | None = None
    scalar_kind: str = ""

    @property
    def complex(self) -> bool:
        return self.kind in {"model", "list", "tuple", "dict"}

    def __repr__(self) -> str:
        return f"<FieldPlan {'.'.join(self.path)}: {self.kind}>"


@dataclass(frozen=True, repr=False)
class Registration:
    name: str
    path: tuple[str, ...]
    model: type[ConfigModel]
    plan: Plan

    def __repr__(self) -> str:
        return f"<Registration {self.name}: {'.'.join(self.path)}>"


def parse_path(value: str) -> tuple[str, ...]:
    if not isinstance(value, str) or len(value) > 128:
        raise ConfigRegistrationError("invalid-path")
    parts = tuple(value.split("."))
    if not parts or any(not SEGMENT.fullmatch(part) or "__" in part for part in parts):
        raise ConfigRegistrationError("invalid-path")
    return parts


def compile_model(model: type[ConfigModel], path: tuple[str, ...]) -> Plan:
    def compile_type(
        annotation: Any,
        location: tuple[str, ...],
        stack: tuple[type, ...],
        info: FieldInfo | None = None,
    ) -> Plan:
        if len(location) > 32 or len(".".join(location)) > 128:
            raise ConfigRegistrationError("schema-limit", path=".".join(location))
        if get_origin(annotation) is Annotated:
            annotation = get_args(annotation)[0]
        nullable = False
        if get_origin(annotation) in (Union, UnionType):
            args = get_args(annotation)
            alternatives = [item for item in args if item is not type(None)]
            if len(alternatives) != 1 or type(None) not in args:
                raise ConfigRegistrationError("unsupported-union", path=".".join(location))
            nullable = True
            annotation = alternatives[0]
            if get_origin(annotation) is Annotated:
                annotation = get_args(annotation)[0]
        plan = Plan(location, "", annotation, nullable, info=info)
        origin, args = get_origin(annotation), get_args(annotation)
        scalar = {
            str: "str",
            bool: "bool",
            int: "int",
            float: "float",
            SecretStr: "str",
            Path: "str",
            PosixPath: "str",
            WindowsPath: "str",
        }
        if annotation in scalar:
            plan.kind = scalar[annotation]
        elif (
            isinstance(annotation, type)
            and issubclass(annotation, URL_TYPES)
            and (annotation.__module__ == "pydantic.networks")
        ):
            plan.kind = "str"
        elif isinstance(annotation, type) and issubclass(annotation, Enum):
            if any("__get_pydantic_core_schema__" in base.__dict__ for base in annotation.__mro__):
                raise ConfigRegistrationError("custom-core-schema", path=".".join(location))
            if not all(isinstance(member.value, str) for member in annotation):
                raise ConfigRegistrationError("unsupported-enum", path=".".join(location))
            plan.kind = "str"
        elif (
            origin is Literal
            and args
            and all(type(item) in (str, bool, int, float) for item in args)
        ):
            plan.kind = "literal"
            kinds = {type(item) for item in args}
            plan.scalar_kind = scalar[next(iter(kinds))] if len(kinds) == 1 else "str"
        elif origin in (list, tuple, dict):
            if origin is dict and len(args) == 2 and args[0] is str:
                element = args[1]
                plan.kind = "dict"
            elif origin is list and len(args) == 1:
                element = args[0]
                plan.kind = "list"
            elif origin is tuple and len(args) == 2 and args[1] is Ellipsis:
                element = args[0]
                plan.kind = "tuple"
            else:
                raise ConfigRegistrationError("unsupported-container", path=".".join(location))
            plan.element = compile_type(element, (*location, "[]"), stack)
            if plan.element.complex:
                raise ConfigRegistrationError("nested-container", path=".".join(location))
        elif isinstance(annotation, type) and issubclass(annotation, ConfigModel):
            if annotation in stack:
                raise ConfigRegistrationError("recursive-model", path=".".join(location))
            config = annotation.model_config
            if (
                config.get("arbitrary_types_allowed")
                or config.get("extra") != "forbid"
                or config.get("frozen") is not True
                or config.get("validate_default") is not True
                or config.get("alias_generator")
            ):
                raise ConfigRegistrationError("model-policy", path=".".join(location))
            if "__get_pydantic_core_schema__" in annotation.__dict__:
                raise ConfigRegistrationError("custom-core-schema", path=".".join(location))
            failed = False
            try:
                annotation.model_rebuild()
            except Exception:
                failed = True
            if failed:
                raise ConfigRegistrationError("model-rebuild", path=".".join(location))
            plan.kind = "model"
            for name, model_field in annotation.model_fields.items():
                parse_path(name)
                if hasattr(BaseModel, name) or hasattr(BaseSettings, name):
                    raise ConfigRegistrationError(
                        "protected-field", path=".".join((*location, name))
                    )
                if model_field.alias is not None or model_field.validation_alias is not None:
                    raise ConfigRegistrationError("field-alias", path=".".join((*location, name)))
                if model_field.default_factory_takes_validated_data:
                    raise ConfigRegistrationError(
                        "data-aware-factory", path=".".join((*location, name))
                    )
                if isinstance(model_field.default, BaseModel):
                    raise ConfigRegistrationError(
                        "model-instance-default", path=".".join((*location, name))
                    )
                if any(
                    type(item).__module__ == "pydantic.functional_validators"
                    or (
                        type(item).__module__ != "annotated_types"
                        and not type(item).__module__.startswith("pydantic.")
                    )
                    for item in model_field.metadata
                ):
                    raise ConfigRegistrationError(
                        "unsupported-metadata", path=".".join((*location, name))
                    )
                plan.fields[name] = compile_type(
                    model_field.annotation, (*location, name), (*stack, annotation), model_field
                )
        else:
            raise ConfigRegistrationError("unsupported-type", path=".".join(location))
        return plan

    if not isinstance(model, type) or not issubclass(model, ConfigModel):
        raise ConfigRegistrationError("expected-config-model", path=".".join(path))
    return compile_type(model, path, ())


def registry_plan(registrations: tuple[Registration, ...]) -> Plan:
    root = Plan((), "group")
    for registration in registrations:
        node = root
        for part in registration.path[:-1]:
            node = node.fields.setdefault(part, Plan((*node.path, part), "group"))
        node.fields[registration.path[-1]] = registration.plan
    return root


def index_plans(root: Plan) -> dict[tuple[str, ...], Plan]:
    result = {root.path: root}
    for child in root.fields.values():
        result.update(index_plans(child))
    return result


def has_default(plan: Plan) -> bool:
    return plan.info is not None and (
        plan.info.default is not PydanticUndefined or plan.info.default_factory is not None
    )
