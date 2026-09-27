# pydconfig

pydconfig loads named, typed application settings from YAML files, dotenv
files, and environment variables. Declare settings as Pydantic models,
register them with a loader, and retrieve a validated snapshot before
creating application resources such as database clients.

It builds on **pydantic**, **pydantic-settings**, **python-dotenv**, and
**PyYAML**. The package and import name are both `pydconfig`. Supported
interpreters are standard CPython **3.10–3.14**.

## Installation

```bash
python -m pip install pydconfig==1.0.2
```

## Quickstart

Create these files:

```text
my-app/
  app.py
  config/
    config.yaml
```

`app.py` defines a nested database model and a separate feature model:

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

`config/config.yaml` uses the registration names as its top-level keys:

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

Run `python app.py`. With no matching environment variables or dotenv files,
the output is:

```json
{"host": "localhost", "port": 5432, "pool_size": 16, "pool_timeout": 5.0, "feature_enabled": false, "feature_hosts": ["primary", "replica"]}
```

`pool.timeout` comes from its model default. YAML supplies `pool.size`
without replacing the remaining nested defaults. `load()` validates every
registered model before returning a snapshot; a missing required field,
unknown field, or invalid port raises a configuration error.

## Nested configuration

Nested models must also inherit from `ConfigModel`. Use
`Field(default_factory=ChildModel)` to make a nested section available even
when no source supplies it. A required declaration such as
`pool: PoolConfig` must receive a section from a source.

Names used by application code can differ from paths used by configuration:

```python
loader = ConfigLoader(root_dir="config")
loader.register("primary_db", DatabaseConfig, path="database.primary")
loader.register("replica_db", DatabaseConfig, path="database.replica")
snapshot = loader.load()
primary = snapshot.get("primary_db", DatabaseConfig)
```

For these registrations, YAML contains `database.primary` and
`database.replica`. The environment variable for the primary host is
`DATABASE__PRIMARY__HOST`; `get()` still uses `primary_db`.
Overrides and `explain()` also use configuration paths.

Models support scalar settings, nullable fields, nested `ConfigModel`
fields, and scalar containers such as `list[str]` and `dict[str, int]`.
Containers of models, recursive models, arbitrary Python objects, and
field aliases are unsupported. Keep clients and loggers outside your
configuration models.

## YAML files and profiles

The default YAML file is `config.yaml` under `root_dir`. To use a different
name or a `.yml` extension, specify it explicitly:

```python
loader = ConfigLoader(root_dir="config", yaml_file="settings.yml")
```

The default file is optional. An explicitly supplied `yaml_file` must
exist. Existing files must contain one YAML document with a mapping at the
root and string keys. Duplicate keys, anchors, aliases, explicit tags, and
YAML merge keys are rejected. Ordinary nested mappings and scalar lists
are supported.

Add `profile: local` to the base `config.yaml` to load
`config.local.yaml` as well. For a custom `settings.yml`, the corresponding
file is `settings.local.yml`. Profile files contain only the values they
override:

```yaml
database:
  host: local-db.internal
  pool:
    timeout: 2.5
```

You can also select a profile with `load(profile="local")` or the
`PYDCONFIG_PROFILE` environment variable. The
[user guide](https://github.com/pydemia/pydconfig/blob/main/docs/user-guide.md#profiles)
explains selection order, allowed profiles, and required profile files.

YAML string values can reference any environment variable by its exact
name:

```yaml
database:
  host: "${DB_HOST:-localhost}"
  port: "${DB_PORT:-5432}"
```

`${VAR}` requires a defined variable. `${VAR:-fallback}` uses the literal
fallback if the variable is undefined or empty. `$${VAR}` produces the
literal text `${VAR}`. Interpolation runs once, after parsing and merging,
on YAML values that remain in use. It never rewrites YAML keys or reparses
injected text as YAML.

## Environment variables and dotenv

No prefix is required: `env_prefix` defaults to `""`. Write configuration
paths in uppercase and replace each dot with `__`:

| Configuration path | Environment variable |
| --- | --- |
| `database.host` | `DATABASE__HOST` |
| `database.pool.size` | `DATABASE__POOL__SIZE` |
| `feature.enabled` | `FEATURE__ENABLED` |
| `feature.hosts` | `FEATURE__HOSTS` |

The aggregate `BaseSettings` sets
`SettingsConfigDict(env_nested_delimiter="__")`. Its custom source reads
that setting to split nested paths in both OS variables and dotenv keys.
Two underscores separate levels; a single underscore stays within a name.
For example, `DATABASE__POOL_SIZE` addresses `database.pool_size`, while
`DATABASE__POOL__SIZE` addresses `database.pool.size`.

For the quickstart above, override nested values in Bash:

```bash
export DATABASE__POOL__SIZE=40
export FEATURE__ENABLED=TRUE
python app.py
```

Or in PowerShell:

```powershell
$env:DATABASE__POOL__SIZE = '40'
$env:FEATURE__ENABLED = 'TRUE'
python app.py
```

The result has `pool_size` equal to `40` and `feature_enabled` equal to
`true`. No YAML placeholder is needed for direct field binding.

Put the same keys in `config/.env` for local defaults. If `local` is the
selected profile, `config/.env.local` is loaded after that base file:

```dotenv
DATABASE__POOL__SIZE=24
FEATURE__ENABLED=false
FEATURE__HOSTS=["primary","replica"]
```

Lists, dictionaries, and whole model sections accept JSON environment
values. An environment variable such as
`FEATURE__HOSTS__0` cannot update a list element; supply the whole
list instead.

`env_prefix="MYAPP_"` changes field binding to names such as
`MYAPP_DATABASE__HOST`. Use `env_prefix="PYDCONFIG_"` to keep the prefixed
names used in 1.0.1 and earlier. With the default empty prefix, unrelated
variables are ignored unless their first segment is a registered root.
Profile selection always uses the reserved `PYDCONFIG_PROFILE` variable.
`dotenv=False` disables dotenv files while preserving OS environment
binding. `load(environ={...})` uses the supplied mapping instead of the
process environment, and `load(environ={})` excludes the OS environment.
The loader does not modify `os.environ`.

Boolean strings accept `true`, `false`, `1`, and `0`, ignoring case. Tokens
such as `yes`, `no`, `on`, and `off` are rejected. For numeric, boolean, and
JSON environment input, one matching pair of outer quotes is removed.
String and secret fields preserve literal quotes by default. See the
[quote rules](https://github.com/pydemia/pydconfig/blob/main/docs/user-guide.md#booleans-and-quotes)
for shell quoting and field-specific policies.

## Source precedence and snapshots

Later sources override earlier sources:

```text
model defaults < base YAML < profile YAML < .env < .env.<profile>
               < OS environment < explicit overrides
```

Mappings merge recursively. Lists and scalar values replace earlier
values. Explicit overrides use the same structure as the YAML root:

```python
snapshot = loader.load(
    overrides={"database": {"pool": {"size": 48}}},
)
database = snapshot.get("database", DatabaseConfig)
assert database.pool.size == 48

changed = snapshot.with_overrides({"database": {"pool": {"size": 12}}})
assert changed.get("database", DatabaseConfig).pool.size == 12
assert snapshot.get("database", DatabaseConfig).pool.size == 48
```

`get()` returns a deep copy. `with_overrides()` validates a new snapshot
without rereading files or the environment. Call `loader.load()` again to
read changed external settings. File watching and automatic client
reconfiguration are not provided.

Use `snapshot.explain("database.pool.size")` and
`snapshot.source_report()` to inspect source metadata without exposing
configuration values.

## Documentation

| Document | Contents |
| --- | --- |
| [User guide](https://github.com/pydemia/pydconfig/blob/main/docs/user-guide.md) | Runnable quickstart, nested models, YAML, environment variables, profiles, snapshots, and troubleshooting |
| [Configuration reference](https://github.com/pydemia/pydconfig/blob/main/docs/configuration-reference.md) | Exact API, supported types, parsing rules, limits, and errors; in Korean |
| [Application integration](https://github.com/pydemia/pydconfig/blob/main/docs/integration-guide.md) | Constructor injection, FastAPI, and test isolation; in Korean |
| [Development guide](https://github.com/pydemia/pydconfig/blob/main/docs/development.md) | Build, validation, and publishing instructions; in Korean |
| [Bundled file example](https://github.com/pydemia/pydconfig/tree/main/examples/basic) | Base and profile YAML, dotenv templates, and a runnable application |

## Development and compatibility

```bash
git clone https://github.com/pydemia/pydconfig.git
cd pydconfig
python -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m mypy
```

On Windows, use `.venv\Scripts\python.exe`. The compatibility workflow
builds a wheel from an sdist, installs it, and runs tests, the bundled file
example, upstream API probes, mypy, Ruff, and package checks. Its matrix
covers Ubuntu CPython 3.10–3.14 and macOS/Windows CPython 3.14.

PyPy, free-threaded Python, Python 3.15 and later, merging multiple
profiles, and arbitrary object settings are outside the supported scope.
