"""Immutable diagnostics deliberately contain no configuration values."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceRef:
    kind: str
    name: str
    line: int | None = None
    column: int | None = None


@dataclass(frozen=True)
class SourceStatus:
    kind: str
    name: str
    status: str


@dataclass(frozen=True)
class FieldExplanation:
    path: str
    defined_at: SourceRef
    references: tuple[SourceRef, ...] = ()
    shadowed: tuple[SourceRef, ...] = ()
    steps: tuple[str, ...] = ()
    output: str = "opaque-validation"


@dataclass(frozen=True)
class SourceReport:
    sources: tuple[SourceStatus, ...] = ()
    ignored_paths: tuple[str, ...] = ()
    noncanonical_variables: tuple[SourceRef, ...] = ()
