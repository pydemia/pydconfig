"""Typed configuration data; application resources belong in application bootstrap."""

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict


class ConfigModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
        arbitrary_types_allowed=False,
        allow_inf_nan=False,
        hide_input_in_errors=True,
    )

    def __repr__(self) -> str:
        return f"{type(self).__name__}(<configuration values redacted>)"

    def __str__(self) -> str:
        return repr(self)

    def __repr_args__(self) -> Iterable[tuple[str | None, Any]]:
        # Pydantic's pretty-print adapters also use this protocol.
        return ()
