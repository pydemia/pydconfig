# User guide

This guide covers pydconfig 1.0.1. It starts with a complete application,
then explains how nested models, YAML, dotenv files, and environment
variables produce a validated configuration snapshot. The
[configuration reference](configuration-reference.md) specifies the exact
API and input restrictions in Korean.

## Installation

Use standard CPython 3.10–3.14:

```bash
python -m pip install pydconfig==1.0.1
```

`ConfigModel` represents configuration data such as hosts, ports, timeouts,
and feature flags. Create database clients, loggers, and other resources
after configuration has loaded successfully.

## Quickstart

Create a directory with this layout:

```text
my-app/
  app.py
  config/
    config.yaml
```

Save the following as `app.py`:

```python
import json
from pathlib import Path

from pydantic import Field
from pydconfig import ConfigLoader, ConfigModel


class PoolConfig(ConfigModel):
    size: int = Field(default=10, ge=1, le=100)
    timeout: float = Field(default=5.0, gt=0)


class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    pool: PoolConfig = Field(default_factory=PoolConfig)


class FeatureConfig(ConfigModel):
    enabled: bool = False
    hosts: list[str] = Field(default_factory=list)


loader = ConfigLoader(root_dir=Path(__file__).resolve().parent / "config")
loader.register("database", DatabaseConfig)
loader.register("feature", FeatureConfig)
snapshot = loader.load()

database = snapshot.get("database", DatabaseConfig)
feature = snapshot.get("feature", FeatureConfig)
print(json.dumps({
    "host": database.host,
    "port": database.port,
    "pool_size": database.pool.size,
    "pool_timeout": database.pool.timeout,
    "feature_enabled": feature.enabled,
    "feature_hosts": feature.hosts,
}))
```

Save this as `config/config.yaml`:

```yaml
database:
  host: localhost
  port: 5432
  pool:
    size: 16
feature:
  enabled: false
  hosts: [primary, replica]
```

From `my-app`, run `python app.py`. With no matching OS variables or dotenv
files, the output is:

```json
{"host": "localhost", "port": 5432, "pool_size": 16, "pool_timeout": 5.0, "feature_enabled": false, "feature_hosts": ["primary", "replica"]}
```

`pool.size` comes from YAML, while `pool.timeout` retains its default of
`5.0`. `load()` validates all registered sections before returning a
snapshot. For example, `port: 70000` fails the `le=65535` constraint and
raises `ConfigValidationError` before settings can be retrieved.

To ignore the process environment, use `loader.load(environ={})`. This
still reads YAML and dotenv files. To exclude dotenv as well, construct
the loader with `dotenv=False`.

## Nested models and defaults

Every nested configuration model must inherit from `ConfigModel`:

```python
class DatabaseConfig(ConfigModel):
    host: str = "localhost"
    port: int = Field(default=5432, ge=1, le=65535)
    pool: PoolConfig = Field(default_factory=PoolConfig)
```

The YAML and environment paths are `database.pool.size` and
`PYDCONFIG_DATABASE__POOL__SIZE`. Supplying only the nested `size` preserves
the other child defaults:

```yaml
database:
  pool:
    size: 20
```

Use the child class as the default factory. The loader expands its raw
defaults before merging sources and validates the resulting input
afterward. Do not use an already validated `PoolConfig()` instance as a
field default.

To customize part of the default input, return a raw mapping:

```python
class DatabaseConfig(ConfigModel):
    pool: PoolConfig = Field(default_factory=lambda: {"size": 20})
```

This defaults `size` to `20` and retains the child schema's `timeout`.
Factories must take no arguments. Raw scalar or container factories run
once per load, even if later sources override their results. Factories
returning validated model instances or depending on earlier validated
fields are unsupported. Keep file reading and resource creation outside
factories and validators.

| Declaration | Result when all sources omit `pool` |
| --- | --- |
| `pool: PoolConfig` | Required section; loading fails |
| `pool: PoolConfig = Field(default_factory=PoolConfig)` | Creates the section from child defaults |
| `pool: PoolConfig \| None = None` | Leaves the section as `None` |

Supplying `pool: {}` creates a required section and allows child defaults
to apply; any missing required child fields still fail validation. Actual
YAML `null` does not mean "use defaults". The field must permit `None` to
accept it.

Mappings merge recursively. Lists and tuples are replaced as whole
values. A scalar or `null` replaces an earlier subtree; if a later mapping
recreates it, deleted YAML values and custom parent defaults do not
reappear. Child schema defaults may fill missing fields.

Supported containers include `list[str]`, `tuple[int, ...]`, and
`dict[str, float]`, with supported scalar or nullable scalar elements.
Fixed nested `ConfigModel` levels are supported. Recursive schemas,
containers of models or other containers, arbitrary objects, general
`BaseModel` children, and field aliases are rejected at registration.

## Registration names and configuration paths

A registration name identifies a model in application code. Its path
identifies its section in YAML, environment variables, overrides, and
diagnostics. Omitting `path` makes it equal to the name.

Register the same type under separate paths:

```python
loader = ConfigLoader(root_dir="config")
loader.register("primary_db", DatabaseConfig, path="database.primary")
loader.register("replica_db", DatabaseConfig, path="database.replica")
snapshot = loader.load()
primary = snapshot.get("primary_db", DatabaseConfig)
replica = snapshot.get("replica_db", DatabaseConfig)
```

These registrations use this YAML:

```yaml
database:
  primary:
    host: primary.internal
  replica:
    host: replica.internal
```

Their environment variables are `PYDCONFIG_DATABASE__PRIMARY__HOST` and
`PYDCONFIG_DATABASE__REPLICA__HOST`. `PYDCONFIG_PRIMARY_DB__HOST` does not
refer to either path. Overrides and `explain()` use paths; `get()` uses
names and requires the exact registered model type.

Names and path segments start with a lowercase letter and use lowercase
letters, digits, and underscores. A segment cannot contain `__`.
Duplicate names, duplicate or overlapping paths, and registration under
the reserved top-level `profile` key are rejected.

When only `database.primary` is registered, `database` is a structural
ancestor, not a model section. Whole-model environment JSON can target
`PYDCONFIG_DATABASE__PRIMARY`; targeting `PYDCONFIG_DATABASE` is a
structural error.

## YAML files

By default, the loader reads `root_dir/config.yaml`. If `root_dir` is
omitted, it fixes the current working directory when constructed. Later
working-directory changes do not move its root. Using a path based on
`__file__`, as in the quickstart, makes file discovery independent of the
application's launch directory.

To require another file:

```python
loader = ConfigLoader(root_dir="config", yaml_file="settings.yml")
```

Relative `yaml_file` paths are resolved under `root_dir`; absolute paths
are used directly. The extension must be `.yaml` or `.yml`.

| File | Missing-file behavior |
| --- | --- |
| Default `config.yaml` | Optional; skipped if absent |
| Explicit `yaml_file` | Required; absence raises `ConfigSourceError` |
| Selected profile YAML | Optional unless `require_profile_yaml=True` |
| `.env` and selected `.env.<profile>` | Optional |

Automatic discovery does not also check `config.yml`. An existing optional
file still fails if unreadable, malformed, or empty. Use `{}` for an
intentionally empty YAML mapping. UTF-8 and UTF-8 with a BOM are accepted.

YAML accepts one document with a root mapping, string keys, nested
mappings, and lists of supported scalar values:

```yaml
database:
  host: db.internal
  port: 5432
  pool:
    size: 16
    timeout: 2.5
feature:
  enabled: true
  hosts:
    - primary
    - replica
```

Duplicate keys, anchors, aliases, explicit tags such as `!!str`, merge
keys such as `<<`, multiple documents, and non-string keys are rejected.
Unknown final configuration paths also fail by default: a typo such as
`database.hots` does not silently disappear.

`unknown="ignore"` removes unregistered final paths and reports them. It
does not suppress parsing errors or permit unsupported structure. Use it
when intentionally sharing a file with unregistered sections.

Implicit YAML values follow a restricted schema: lowercase `true` and
`false` are booleans; `null`, `~`, and empty values are `None`. Decimal
integers and finite floats are numeric. Values such as `0012`, `0x10`,
`on`, `yes`, and dates remain strings. Quote text when necessary. A bool
field still applies boolean parsing to a YAML string such as `TRUE`.

Relative model fields of type `Path` are not automatically resolved under
`root_dir`.

## Environment variables

Direct binding does not require YAML placeholders. Names are derived from
registered configuration paths, using the prefix `PYDCONFIG_`, uppercase
segments, and `__` separators:

| Configuration path | Environment name |
| --- | --- |
| `database.host` | `PYDCONFIG_DATABASE__HOST` |
| `database.port` | `PYDCONFIG_DATABASE__PORT` |
| `database.pool.size` | `PYDCONFIG_DATABASE__POOL__SIZE` |
| `feature.enabled` | `PYDCONFIG_FEATURE__ENABLED` |
| `feature.hosts` | `PYDCONFIG_FEATURE__HOSTS` |

Override the quickstart's nested integer and boolean in Bash:

```bash
export PYDCONFIG_DATABASE__POOL__SIZE=40
export PYDCONFIG_FEATURE__ENABLED=TRUE
python app.py
```

Or in PowerShell:

```powershell
$env:PYDCONFIG_DATABASE__POOL__SIZE = '40'
$env:PYDCONFIG_FEATURE__ENABLED = 'TRUE'
python app.py
```

The output now includes `"pool_size": 40` and `"feature_enabled": true`.
Other YAML values and defaults remain active. Remove these variables with
`unset` in Bash or `Remove-Item Env:<name>` in PowerShell before running
examples that assume no OS overrides.

Tests can supply an environment mapping without changing process state:

```python
snapshot = loader.load(environ={
    "PYDCONFIG_DATABASE__POOL__SIZE": "40",
    "PYDCONFIG_FEATURE__ENABLED": "TRUE",
})
assert snapshot.get("database", DatabaseConfig).pool.size == 40
assert snapshot.get("feature", FeatureConfig).enabled is True
```

`environ=None`, the default, reads a copy of `os.environ`. A supplied
mapping replaces that OS source completely; it is not merged with process
variables. `environ={}` excludes OS input but still reads YAML and dotenv.
Values must be strings. The loader does not mutate the supplied mapping
or `os.environ`.

`env_prefix="MYAPP_"` changes the host name to `MYAPP_DATABASE__HOST`.
`PYDCONFIG_PROFILE` remains the profile-control name regardless of prefix.

On POSIX, only canonical uppercase names bind automatically. Windows OS
names are handled without case sensitivity and conflicting names are
rejected. Dotenv keys preserve their written case even on Windows; use
uppercase names consistently.

### JSON values and nested binding

Use JSON for a list, dictionary, or complete model section:

```dotenv
PYDCONFIG_DATABASE={"host":"db.internal","port":5432}
PYDCONFIG_DATABASE__POOL={"size":20,"timeout":1.5}
PYDCONFIG_FEATURE__HOSTS=["primary","replica"]
```

Within one source, deeper model JSON overrides parent JSON and scalar
leaves apply last:

```python
snapshot = loader.load(environ={
    "PYDCONFIG_DATABASE": '{"host":"db.internal","pool":{"size":20}}',
    "PYDCONFIG_DATABASE__POOL": '{"size":24,"timeout":1.5}',
    "PYDCONFIG_DATABASE__POOL__SIZE": "32",
})
database = snapshot.get("database", DatabaseConfig)
assert database.host == "db.internal"
assert database.pool.size == 32
assert database.pool.timeout == 1.5
```

Across sources, source precedence applies first: OS parent JSON can
override a dotenv leaf. Lists are replaced as a whole;
`PYDCONFIG_FEATURE__HOSTS__0` cannot update one item. Dynamic dictionary
keys also belong inside JSON, not extra `__` segments.

Python literal syntax, duplicate keys, and NaN/Infinity are rejected.
Container fields need a JSON array or object; nullable containers can
accept JSON `null`.

## Dotenv files

The loader reads `.env` and the selected `.env.<profile>` under `root_dir`.
It does not search parent directories or load `.env.example` automatically.
For the quickstart, add `config/.env`:

```dotenv
PYDCONFIG_DATABASE__POOL__SIZE=24
PYDCONFIG_FEATURE__ENABLED=TRUE
PYDCONFIG_FEATURE__HOSTS=["primary","replica"]
```

Without OS overrides, the pool size becomes `24` and the flag becomes
`true`. Dotenv direct binding outranks both base and profile YAML; OS
variables outrank dotenv.

Files follow python-dotenv syntax with internal variable expansion
disabled. `A=${B}` stores literal `${B}`. Duplicate keys, malformed lines,
and a bare `FLAG` fail loading. `FLAG=` is a defined empty string, which
a boolean field rejects.

`dotenv=False` skips both dotenv files and the base dotenv profile
candidate. OS binding and YAML profile selection still work. Calling
`load_dotenv()` separately would make its loaded values part of the OS
source, changing how their priority and origin are represented.

## Profiles

A profile selects one YAML variant and one dotenv variant:

```text
config/
  config.yaml
  config.local.yaml
  .env
  .env.local
```

Add `profile: local` as a top-level key in the quickstart's base YAML.
Create `config.local.yaml` with partial overrides:

```yaml
database:
  host: local-db.internal
  pool:
    timeout: 2.5
```

Keep `.env` from the previous section and add `.env.local`:

```dotenv
PYDCONFIG_DATABASE__POOL__SIZE=32
PYDCONFIG_FEATURE__ENABLED='"False"'
```

With no matching OS variables, the result is:

| Field | Value | Source |
| --- | --- | --- |
| `snapshot.profile` | `local` | Base YAML profile declaration |
| `database.host` | `local-db.internal` | Profile YAML |
| `database.port` | `5432` | Base YAML |
| `database.pool.size` | `32` | Profile dotenv |
| `database.pool.timeout` | `2.5` | Profile YAML |
| `feature.enabled` | `False` | Profile dotenv, after one quote pair is removed |
| `feature.hosts` | `["primary", "replica"]` | Base dotenv |

OS `PYDCONFIG_DATABASE__POOL__SIZE=40` overrides `32`. Explicit
`overrides={"database": {"pool": {"size": 48}}}` overrides even that OS
value. The [bundled example](../examples/basic/README.md) includes a
complete file set and runs with an explicitly empty OS environment.

Profile selection follows this order:

```text
load(profile=...) > OS PYDCONFIG_PROFILE > .env PYDCONFIG_PROFILE
                  > base YAML profile > no profile
```

Limit accepted profiles and select one explicitly:

```python
loader = ConfigLoader(
    root_dir="config",
    allowed_profiles=["local", "test", "stg", "prd"],
)
loader.register("database", DatabaseConfig)
loader.register("feature", FeatureConfig)
snapshot = loader.load(profile="test")
assert snapshot.profile == "test"
```

Selecting `test` reads the base files plus `config.test.yaml` and
`.env.test`, without reading `local` variants. Other values in the base
dotenv remain active even if its profile declaration is overridden.

Profile names start with a lowercase letter and allow lowercase letters,
digits, underscores, and hyphens. Empty or invalid declarations are
errors, including lower-priority declarations. Profile YAML and profile
dotenv cannot redeclare the profile. Profiles are literal names, not
`${VAR}` expressions.

`require_profile_yaml=True` requires a selected profile and its YAML
variant. For `yaml_file="settings.yml"`, that variant is
`settings.<profile>.yml`; dotenv files remain under `root_dir`.

## Environment references in YAML

YAML can reference ordinary environment names without the binding prefix:

```yaml
database:
  host: "${DB_HOST:-localhost}"
  port: "${DB_PORT:-5432}"
feature:
  hosts: '${APP_HOSTS:-["primary"]}'
```

| Expression | Behavior |
| --- | --- |
| `${VAR}` | Error if undefined; a defined empty value stays empty |
| `${VAR:-fallback}` | Literal fallback if undefined or empty |
| `$${VAR}` | Produces literal `${VAR}` |
| `prefix-${VAR}-suffix` | Replaces part of a string |

Reference lookup uses base dotenv, profile dotenv, then the OS or supplied
environment mapping; later sources win. Numeric fields validate resulting
strings, and container fields can parse resulting JSON. Inserted text is
never reparsed as YAML structure.

Interpolation runs after merging and unknown-field pruning, only on final
YAML strings still in use. An OS direct override can hide `${MISSING}` so
it is never evaluated. YAML syntax and duplicate-key errors still fail
even if later values would hide them.

There is one interpolation pass. If dotenv defines `A=${B}`, YAML `${A}`
produces literal `${B}`. YAML keys, Python overrides, and dotenv values are
not independently interpolated. Fallbacks cannot contain `}` or nested
placeholders. `${VAR-default}` and `${VAR:default}` are unsupported.

## Booleans and quotes

Bool fields accept actual booleans, integer `0` or `1`, and strings
`true`, `false`, `1`, or `0`, ignoring case and surrounding ASCII
whitespace. `yes`, `no`, `on`, `off`, empty strings, and unknown tokens
are rejected.

One matching pair of outer ASCII quotes is removed from boolean, numeric,
and JSON environment input. Literal quotes in strings, `SecretStr`, paths,
URLs, string enums, and string literals are preserved by default.

Shell syntax quotes and characters inside a value differ. In Bash:

```bash
export PYDCONFIG_FEATURE__ENABLED="False"
export PYDCONFIG_FEATURE__ENABLED='"False"'
```

The first command supplies `False`; the second supplies `"False"` with
actual quote characters. Both parse as false under the default policy.
Nested quote pairs are not repeatedly removed.

Set policies by configuration path:

```python
loader = ConfigLoader(
    root_dir="config",
    env_quote_policy={
        "database.host": "unwrap",
        "feature.enabled": "preserve",
    },
)
```

Actual `"False"` now fails for `feature.enabled`, because `preserve`
disables wrapper removal. Unmatched quotes, interior quotes, and
backslashes are not repaired or shell-parsed. Explicit string `unwrap`
removes matching first and last quotes without trimming the string.
Policies use paths, not registration names. A model or container policy
applies to its whole JSON wrapper, not recursively to its elements.

Fallback's undefined/empty check precedes quote removal. Actual `""`
characters are nonempty, whereas dotenv `FLAG=""` parses as an empty
string. A fallback is YAML literal input, not environment input subject
to wrapper removal.

## Source precedence and explicit overrides

Sources apply in increasing priority:

```text
model defaults < base YAML < profile YAML < .env < .env.<profile>
               < OS environment < explicit overrides
```

Overrides have the same mapping structure as the YAML root:

```python
snapshot = loader.load(
    environ={"PYDCONFIG_DATABASE__POOL__SIZE": "40"},
    overrides={"database": {"pool": {"size": 48}}},
)
assert snapshot.get("database", DatabaseConfig).pool.size == 48
```

Overrides are Python input: they are validated without environment quote
removal or YAML interpolation. They cannot change the selected profile.

## Snapshots and reloads

`get(name, model)` returns a deep copy of a validated model without rerunning
factories or validators. Model fields are frozen, but Python lists and
dictionaries on a retrieved copy remain mutable without changing the
snapshot or another `get()` result.

Create a new snapshot from saved input:

```python
original = loader.load(environ={}, overrides={
    "database": {"pool": {"size": 48}},
})
changed = original.with_overrides({"database": {"pool": {"size": 12}}})
assert original.get("database", DatabaseConfig).pool.size == 48
assert changed.get("database", DatabaseConfig).pool.size == 12
```

`with_overrides()` merges new Python input into saved pre-validation input
and validates again. It does not reread files or environment variables,
reinterpret old quoting, or interpolate new strings. Call `loader.load()`
again to read changed external configuration.

Applications decide when to switch snapshots and recreate clients. The
library does not watch files, switch service instances, or close existing
connections automatically.

## Diagnostics and errors

Inspect a field's origin without dumping its value:

```python
from dataclasses import asdict

explanation = asdict(snapshot.explain("database.pool.size"))
report = asdict(snapshot.source_report())
assert explanation["output"] == "opaque-validation"
```

`explain()` describes input sources, referenced environment sources,
shadowed input, and default fallback steps. It does not infer arbitrary
validators' output dependencies. `source_report()` lists loaded, missing,
or disabled files, ignored paths, and noncanonical variables. Both return
immutable dataclasses without configuration values.

| Symptom | Check |
| --- | --- |
| Environment override has no effect | Path, prefix, uppercase spelling, `__`, and whether `environ={}` excludes OS input |
| Profile file is not reflected | Selected profile, root directory, YAML variant name, and source report |
| Boolean parsing fails | Accepted token, actual quotes, and the path's policy |
| Quotes remain in a string | Default preservation and shell syntax versus literal characters |
| `${VAR}` raises an error | Whether the final YAML value uses it and the variable is defined |
| Unknown field raises an error | Registration path, field spelling, and unexpected prefixed variables |
| Source parsing fails | UTF-8, duplicate keys, YAML subset, JSON syntax, and input limits |
| `get()` fails | Registration name and exact model type |

Exceptions derive from `ConfigError`: `ConfigRegistrationError`,
`ConfigSourceError`, `ConfigProfileError`, `ConfigInterpolationError`,
`ConfigValidationError`, and `ConfigLookupError`. They provide reason
codes, paths, and available source locations instead of raw inputs or
arbitrary validator messages. See the
[error reference](configuration-reference.md#오류와-진단) for details.

Avoid printing complete environment mappings or models while diagnosing
failures. Applications can still expose values by explicitly serializing
retrieved models or revealing a `SecretStr` value.
