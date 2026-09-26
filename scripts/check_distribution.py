"""Verify the installed wheel, metadata and complete bundled file example."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from importlib import metadata
from pathlib import Path

import pydconfig


def main() -> None:
    checkout = Path(__file__).resolve().parents[1]
    installed = Path(pydconfig.__file__).resolve()
    if installed.is_relative_to(checkout / "src"):
        raise AssertionError("verification requires an installed wheel, not an editable checkout")
    assert metadata.version("pydconfig") == pydconfig.__version__ == "1.0.0"
    assert installed.with_name("py.typed").is_file()
    expected = {
        "profile": "local",
        "database_host": "local-db.internal",
        "database_port": 5432,
        "pool_size": 32,
        "pool_timeout": 2.5,
        "feature_enabled": False,
        "feature_hosts": ["primary", "replica"],
    }
    with tempfile.TemporaryDirectory(prefix="pydconfig-example-") as directory:
        target = Path(directory) / "basic"
        shutil.copytree(
            checkout / "examples" / "basic",
            target,
            ignore=shutil.ignore_patterns("__pycache__", ".env", ".env.local"),
        )
        for name in (".env", ".env.local"):
            shutil.copyfile(target / (name + ".example"), target / name)
        result = subprocess.run(
            [sys.executable, str(target / "app.py")],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(result.stdout) == expected
    artifacts = {}
    for path in sorted((checkout / "dist").glob("*")):
        if path.suffix in (".whl", ".gz"):
            artifacts[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "result": "passed",
                "version": pydconfig.__version__,
                "installed_from": str(installed),
                "file_example": expected,
                "artifacts_sha256": artifacts,
            }
        )
    )


if __name__ == "__main__":
    main()
