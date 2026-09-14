"""Run credential-free acceptance checks against disposable application state."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    with tempfile.TemporaryDirectory(prefix="campus-verify-") as temporary:
        project = Path(temporary) / "project"
        # CLI-managed eval storage follows pyproject.toml, independently of the
        # application's data setting. A source snapshot isolates both stores.
        shutil.copytree(
            ROOT, project,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", ".cayu", "data", "validation", "node_modules",
                "__pycache__", ".pytest_cache", ".ruff_cache", "*.whl", "*.egg-info",
                ".env", ".env.*", "*.pem", "*.key", "*.webm",
            ),
        )
        env = dict(os.environ)
        for name in ("CAMPUS_VIEWER_STATE", "OPENAI_API_KEY"):
            env.pop(name, None)
        env.update(
            CAMPUS_DATA_DIR=str(project / "data"),
            CAMPUS_CUSTOMER="north-campus",
            CAMPUS_BROWSER="0",
            UV_CACHE_DIR=str(ROOT / ".cayu/uv-cache"),
            UV_PROJECT_ENVIRONMENT=str(ROOT / ".venv"),
        )
        commands = [
            ["uv", "lock", "--check", "--offline"],
            ["uv", "export", "--frozen", "--extra", "viewer", "--no-dev",
             "--no-emit-project", "--no-emit-package", "cayu", "--no-emit-package",
             "campus-catalog-fixture", "--format", "requirements-txt",
             "--output-file", "viewer-host/requirements.lock"],
            ["uv", "run", "--no-sync", "python", "demo.py", "init"],
            ["uv", "run", "--no-sync", "cayu", "inspect", "--json"],
            ["uv", "run", "--no-sync", "cayu", "check", "--fail-on", "warning", "--json"],
            ["uv", "run", "--no-sync", "ruff", "check", "."],
            ["uv", "run", "--no-sync", "pytest", "-q"],
            ["uv", "run", "--no-sync", "cayu", "eval", "run"],
            ["uv", "run", "--no-sync", "python", "-m", "evals.run", "--output-dir",
             str(Path(temporary) / "evals")],
            ["npm", "run", "check:api:repo", "--prefix", "viewer-ui"],
            ["npm", "test", "--prefix", "viewer-ui"],
            ["npm", "run", "build", "--prefix", "viewer-ui"],
        ]
        for command in commands:
            print("+ " + " ".join(command), flush=True)
            subprocess.run(command, cwd=ROOT if command[0] == "npm" else project,
                           env=env, check=True)
            if command[:2] == ["uv", "export"]:
                expected = (ROOT / "viewer-host/requirements.lock").read_bytes()
                if (project / "viewer-host/requirements.lock").read_bytes() != expected:
                    raise SystemExit("Presenter requirements are stale; regenerate from uv.lock.")


if __name__ == "__main__":
    main()
