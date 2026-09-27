"""A per-load bound BaseSettings executes one project source and validates once."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from .errors import ConfigIssue, ConfigValidationError
from .model import ConfigModel
from .nodes import find_node, raw
from .pipeline import Resolution
from .schema import Plan, Registration, index_plans


class RedactedInput(dict[str, Any]):
    def __repr__(self) -> str:
        return "<configuration input redacted>"

    def __str__(self) -> str:
        return repr(self)


@dataclass(repr=False)
class LoadContext:
    resolve: Callable[[str], Resolution]
    resolution: Resolution | None = None

    def __repr__(self) -> str:
        return "<LoadContext redacted>"


class PydConfigSource(PydanticBaseSettingsSource):
    def __init__(self, settings_cls: type[BaseSettings], context: LoadContext) -> None:
        super().__init__(settings_cls)
        self.context = context

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        # This adapter returns the complete aggregate in __call__, not field-by-field.
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        # Keep source precedence and provenance while using the settings delimiter.
        delimiter = self.config.get("env_nested_delimiter")
        assert delimiter is not None
        self.context.resolution = self.context.resolve(delimiter)
        return RedactedInput(deepcopy(raw(self.context.resolution.node)))

    def __repr__(self) -> str:
        return "<PydConfigSource input redacted>"


class AggregateBase(BaseSettings):
    model_config = SettingsConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        arbitrary_types_allowed=False,
        env_nested_delimiter="__",
        env_file=None,
        secrets_dir=None,
        cli_parse_args=None,
        hide_input_in_errors=True,
    )


class GroupBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=False)


def validate_settings(
    root: Plan, registrations: tuple[Registration, ...], resolve: Callable[[str], Resolution]
) -> tuple[dict[str, ConfigModel], Resolution]:
    def group_type(plan: Plan, aggregate: bool = False) -> type[BaseModel]:
        fields: dict[str, Any] = {
            name: (child.annotation if child.kind == "model" else group_type(child), ...)
            for name, child in plan.fields.items()
        }
        base: type[BaseModel] = AggregateBase if aggregate else GroupBase
        return create_model(
            "AggregateSettings" if aggregate else "ConfigGroup", __base__=base, **fields
        )

    aggregate = group_type(root, True)
    context = LoadContext(resolve)

    def customise(
        cls: Any,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (PydConfigSource(settings_cls, context),)

    bound = type(
        "BoundAggregateSettings",
        (aggregate,),
        {
            "settings_customise_sources": classmethod(customise),
        },
    )
    failure: ConfigValidationError | None = None
    output: Any = None
    try:
        output = bound(_cli_parse_args=None, _cli_settings_source=None)
    except ValidationError as error:
        plans = index_plans(root)
        issues = []
        for detail in error.errors(include_input=False, include_context=False, include_url=False):
            path: tuple[str, ...] = ()
            for part in detail["loc"]:
                candidate = (*path, str(part))
                if candidate not in plans:
                    break
                path = candidate
            node = find_node(context.resolution.node, path) if context.resolution else None
            issues.append(
                ConfigIssue(
                    "missing-field" if detail["type"] == "missing" else "validation-failed",
                    ".".join(path),
                    node.ref if node else None,
                    plans[path].kind if path in plans else None,
                )
            )
        failure = ConfigValidationError("validation-failed", issues=tuple(issues))
    if failure:
        raise failure
    assert context.resolution is not None
    models: dict[str, ConfigModel] = {}
    for registration in registrations:
        current = output
        for part in registration.path:
            current = getattr(current, part)
        models[registration.name] = current
    return models, context.resolution
