from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run(*args: str, cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True)


def build(root: Path) -> dict[str, Path]:
    """Build two independent deterministic Git repositories and one workspace."""
    repositories = root / "repositories"
    workspace = root / "workspaces" / "demo"
    workspace.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {"workspace": workspace}

    for name, source in {
        "api": "def health_check():\n    return {'status': 'ok'}\n",
        "web": "export function healthCheck() { return 'ok'; }\n",
    }.items():
        repository = repositories / name
        repository.mkdir(parents=True, exist_ok=True)
        extension = "py" if name == "api" else "ts"
        (repository / f"{name}.{extension}").write_text(source, encoding="utf-8")
        test_name, test_source = (
            (
                "tests.py",
                "from api import health_check\nassert health_check() == {'status': 'ok'}\n",
            )
            if name == "api"
            else (
                "tests.mjs",
                "import { readFileSync } from 'node:fs';\n"
                "import assert from 'node:assert/strict';\n"
                "const source = readFileSync('web.ts', 'utf8');\n"
                "const { healthCheck } = await import('data:text/javascript,' + "
                "encodeURIComponent(source));\n"
                "assert.equal(healthCheck(), 'ok');\n",
            )
        )
        (repository / test_name).write_text(test_source, encoding="utf-8")
        (repository / ".gitignore").write_text(".env\ndist/\n", encoding="utf-8")
        _run("git", "init", "-b", "main", cwd=repository)
        _run("git", "config", "user.name", "Q-Harness Tests", cwd=repository)
        _run("git", "config", "user.email", "tests@qharness.local", cwd=repository)
        _run("git", "add", ".", cwd=repository)
        _run("git", "commit", "-m", "fixture", cwd=repository)
        result[name] = repository
    scope = {
        "repository_paths": [str(result[name].resolve()) for name in ("api", "web")],
        "tools": ["read", "write", "search", "test"],
        "commands": ["python", "node"],
        "network": False,
        "credential_names": [],
        "risk_ceiling": "HIGH",
        "required_gates": [
            {"name": name, "cwd": str(result[name].resolve()), "command": command}
            for name, command in (("api", ["python", "tests.py"]), ("web", ["node", "tests.mjs"]))
        ],
    }
    scope_path = root / "scopes" / "two-repo-task.json"
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    scope_path.write_text(json.dumps(scope, indent=2), encoding="utf-8")
    result["scope"] = scope_path
    return result


if __name__ == "__main__":
    build(Path(__file__).resolve().parent)
