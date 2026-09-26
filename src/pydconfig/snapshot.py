"""Independent validated snapshots and replay from the original resolved input."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeVar, cast

from .errors import ConfigLookupError, ConfigRegistrationError, sanitized
from .model import ConfigModel
from .nodes import all_references, find_node
from .pipeline import Options, Resolution, replay_input
from .provenance import FieldExplanation, SourceReport
from .schema import Plan, Registration, index_plans, parse_path
from .settings import validate_settings

T = TypeVar("T", bound=ConfigModel)


class ConfigSnapshot:
    __slots__ = ("_registrations", "_root", "_options", "_resolution", "_models")

    def __init__(
        self,
        registrations: tuple[Registration, ...],
        root: Plan,
        options: Options,
        resolution: Resolution,
        models: dict[str, ConfigModel],
    ) -> None:
        self._registrations = registrations
        self._root = root
        self._options = options
        self._resolution = resolution
        self._models = models

    @property
    def profile(self) -> str | None:
        return self._resolution.profile

    @sanitized
    def get(self, name: str, model: type[T]) -> T:
        registration = next((item for item in self._registrations if item.name == name), None)
        if registration is None:
            raise ConfigLookupError("unknown-name")
        if model is not registration.model:
            raise ConfigLookupError("lookup-type", path=".".join(registration.path))
        return cast(T, self._models[name].model_copy(deep=True))

    @sanitized
    def explain(self, path: str) -> FieldExplanation:
        parts: tuple[str, ...] = ()
        try:
            parts = parse_path(path)
        except ConfigRegistrationError:
            pass
        if not parts:
            raise ConfigLookupError("invalid-path")
        plan = index_plans(self._root).get(parts)
        if plan is None or plan.kind == "group":
            raise ConfigLookupError("unknown-path")
        node = find_node(self._resolution.node, parts)
        if node is None:
            raise ConfigLookupError("absent-path", path=path)
        steps = node.steps
        if any(parts[: len(barrier)] == barrier for barrier in self._resolution.history.barriers):
            steps = (*steps, "null-or-scalar-barrier")
        shadowed = tuple(
            dict.fromkeys(
                ref for ref in self._resolution.history.shadowed.get(parts, ()) if ref != node.ref
            )
        )
        return FieldExplanation(path, node.ref, all_references(node), shadowed, steps)

    def source_report(self) -> SourceReport:
        return self._resolution.report

    @sanitized
    def with_overrides(self, values: Mapping[str, Any]) -> ConfigSnapshot:
        models, resolution = validate_settings(
            self._root,
            self._registrations,
            lambda: replay_input(self._resolution, self._options, self._root, values),
        )
        return ConfigSnapshot(self._registrations, self._root, self._options, resolution, models)

    def __repr__(self) -> str:
        return "<ConfigSnapshot values redacted>"
