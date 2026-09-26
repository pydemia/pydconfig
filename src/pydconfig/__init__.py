"""Typed, named configuration for Python applications."""

from .errors import (
    ConfigError,
    ConfigInterpolationError,
    ConfigIssue,
    ConfigLookupError,
    ConfigProfileError,
    ConfigRegistrationError,
    ConfigSourceError,
    ConfigValidationError,
)
from .loader import ConfigLoader
from .model import ConfigModel
from .provenance import FieldExplanation, SourceRef, SourceReport, SourceStatus
from .snapshot import ConfigSnapshot

__version__ = "1.0.0"
__all__ = [
    "ConfigLoader",
    "ConfigModel",
    "ConfigSnapshot",
    "ConfigError",
    "ConfigIssue",
    "ConfigRegistrationError",
    "ConfigSourceError",
    "ConfigProfileError",
    "ConfigInterpolationError",
    "ConfigValidationError",
    "ConfigLookupError",
    "FieldExplanation",
    "SourceRef",
    "SourceReport",
    "SourceStatus",
]
