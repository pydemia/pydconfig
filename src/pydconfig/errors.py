"""Value-free errors exposed by the configuration boundary."""

from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar, cast

from .provenance import SourceRef


@dataclass(frozen=True)
class ConfigIssue:
    code: str
    path: str = ""
    source: SourceRef | None = None
    expected: str | None = None


class ConfigError(ValueError):
    """A sanitized configuration failure, without original input or exception chain."""

    def __init__(
        self,
        code: str,
        *,
        path: str = "",
        source: SourceRef | None = None,
        expected: str | None = None,
        issues: tuple[ConfigIssue, ...] | None = None,
    ) -> None:
        self.issues = issues or (ConfigIssue(code, path, source, expected),)
        self.code = code
        self.path = path
        self.source = source
        super().__init__(
            "; ".join(
                f"{issue.code} at {issue.path or '<root>'}"
                + (f" ({issue.source.kind}: {issue.source.name})" if issue.source else "")
                for issue in self.issues
            )
        )


class ConfigRegistrationError(ConfigError):
    pass


class ConfigSourceError(ConfigError):
    pass


class ConfigProfileError(ConfigError):
    pass


class ConfigInterpolationError(ConfigError):
    pass


class ConfigValidationError(ConfigError):
    pass


class ConfigLookupError(ConfigError):
    pass


F = TypeVar("F", bound=Callable[..., Any])


def sanitized(function: F) -> F:
    """Reconstruct failures outside the handler so __context__ cannot retain input."""

    @wraps(function)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        failure: ConfigError
        try:
            return function(*args, **kwargs)
        except ConfigError as error:
            failure = type(error)(
                error.code, path=error.path, source=error.source, issues=error.issues
            )
        except Exception:
            failure = ConfigSourceError("configuration-operation-failed")
        raise failure

    return cast(F, wrapped)
