"""Choose a single profile before reading any profile-specific sources."""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from .errors import ConfigProfileError
from .nodes import Node
from .provenance import SourceRef

PROFILE = re.compile(r"[a-z][a-z0-9_-]*\Z")


def validate_profile(value: Any, source: SourceRef | None = None) -> str:
    if not isinstance(value, str) or len(value) > 128 or not PROFILE.fullmatch(value):
        raise ConfigProfileError("invalid-profile", source=source)
    return value


def choose_profile(
    explicit: str | None,
    environment: dict[str, str],
    dotenv: dict[str, str],
    dotenv_refs: dict[str, SourceRef],
    yaml: Node | None,
    allowed: Sequence[str] | None,
) -> str | None:
    candidates: list[str] = []
    if explicit is not None:
        candidates.append(validate_profile(explicit, SourceRef("profile-argument", "profile")))
    if "PYDCONFIG_PROFILE" in environment:
        candidates.append(
            validate_profile(environment["PYDCONFIG_PROFILE"], SourceRef("os", "PYDCONFIG_PROFILE"))
        )
    if "PYDCONFIG_PROFILE" in dotenv:
        candidates.append(
            validate_profile(dotenv["PYDCONFIG_PROFILE"], dotenv_refs["PYDCONFIG_PROFILE"])
        )
    if yaml is not None and "profile" in yaml.value:
        candidate = yaml.value["profile"]
        candidates.append(validate_profile(candidate.value, candidate.ref))
    chosen = candidates[0] if candidates else None
    if chosen is not None and allowed is not None and chosen not in allowed:
        raise ConfigProfileError("profile-not-allowed")
    return chosen
