"""Application-facing registry and explicit source loading."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic_settings import BaseSettings

from .bootstrap import validate_profile
from .errors import ConfigRegistrationError, sanitized
from .model import ConfigModel
from .pipeline import Options, resolve_input
from .schema import Registration, compile_model, parse_path, registry_plan
from .settings import validate_settings
from .snapshot import ConfigSnapshot

T = TypeVar("T", bound=ConfigModel)


class ConfigLoader:
    @sanitized
    def __init__(
        self,
        *,
        root_dir: str | Path | None = None,
        yaml_file: str | Path | None = None,
        env_prefix: str = "PYDCONFIG_",
        dotenv: bool = True,
        allowed_profiles: Sequence[str] | None = None,
        require_profile_yaml: bool = False,
        unknown: str = "error",
        env_quote_policy: Mapping[str, Literal["preserve", "unwrap"]] | None = None,
    ) -> None:
        if not isinstance(env_prefix, str) or (
            env_prefix and not re.fullmatch("[A-Z][A-Z0-9_]*_", env_prefix)
        ):
            raise ConfigRegistrationError("invalid-prefix")
        if unknown not in ("error", "ignore"):
            raise ConfigRegistrationError("invalid-unknown-policy")
        if type(dotenv) is not bool or type(require_profile_yaml) is not bool:
            raise ConfigRegistrationError("invalid-loader-option")
        if isinstance(allowed_profiles, (str, bytes)):
            raise ConfigRegistrationError("invalid-profile-list")
        profiles = (
            tuple(validate_profile(item) for item in allowed_profiles)
            if allowed_profiles is not None
            else None
        )
        policies = dict(env_quote_policy or {})
        for path, policy in policies.items():
            parse_path(path)
            if policy not in ("preserve", "unwrap"):
                raise ConfigRegistrationError("invalid-quote-policy")
        root = Path.cwd().resolve() if root_dir is None else Path(root_dir).resolve()
        yaml = Path("config.yaml") if yaml_file is None else Path(yaml_file)
        if yaml.suffix not in (".yaml", ".yml"):
            raise ConfigRegistrationError("yaml-extension")
        if not yaml.is_absolute():
            yaml = root / yaml
        self._options = Options(
            root,
            yaml,
            yaml_file is not None,
            env_prefix,
            dotenv,
            profiles,
            require_profile_yaml,
            unknown,
            tuple(policies.items()),
        )
        self._registrations: list[Registration] = []

    @sanitized
    def register(self, name: str, model: type[T], *, path: str | None = None) -> None:
        if len(parse_path(name)) != 1:
            raise ConfigRegistrationError("invalid-name")
        parts = parse_path(name if path is None else path)
        if parts[0] == "profile":
            raise ConfigRegistrationError("reserved-profile")
        if any(hasattr(BaseSettings, part) for part in parts):
            raise ConfigRegistrationError("protected-field", path=".".join(parts))
        for item in self._registrations:
            if item.name == name:
                raise ConfigRegistrationError("duplicate-name")
            if parts[: len(item.path)] == item.path or item.path[: len(parts)] == parts:
                raise ConfigRegistrationError("overlapping-path", path=".".join(parts))
        plan = compile_model(model, parts)
        self._registrations.append(Registration(name, parts, model, plan))

    @sanitized
    def load(
        self,
        *,
        profile: str | None = None,
        environ: Mapping[str, str] | None = None,
        overrides: Mapping[str, Any] | None = None,
    ) -> ConfigSnapshot:
        registrations = tuple(self._registrations)
        if not registrations:
            raise ConfigRegistrationError("empty-registry")
        root = registry_plan(registrations)
        models, resolution = validate_settings(
            root,
            registrations,
            lambda: resolve_input(
                self._options, root, profile=profile, environ=environ, overrides=overrides
            ),
        )
        return ConfigSnapshot(registrations, root, self._options, resolution, models)

    def __repr__(self) -> str:
        return "<ConfigLoader>"
