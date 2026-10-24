# Contributing to Q-Harness

Thanks for helping improve Q-Harness. It is an early MVP; keep changes focused
and describe observable behavior and evidence.

## Development Setup

Use Python 3.12, Git, ripgrep, Docker/Compose v2 and PostgreSQL 18 clients.
Follow [installation](docs/installation.md), then install development dependencies:

```bash
source .venv/bin/activate
python -m pip install --constraint constraints.txt -e '.[dev]'
```

For a fresh deployment, start Compose PostgreSQL and build `Dockerfile.sandbox`.
Existing deployments must follow the [storage migration warning](docs/backup-restore.md#postgresql-18-storage).
Never use production credentials for tests. Even unit tests require PostgreSQL
and a role with `CREATEDB`; the suite creates disposable databases.

## Making A Change

1. Describe the problem in an issue or PR. For substantial scope changes, discuss
   the proposal before implementation.
2. Keep the change small and match existing code conventions. Add regression
   coverage for behavior changes, especially Project/path/approval boundaries.
3. Update affected documentation and public contracts under `specs/`.
4. Run the checks below and report anything not run with its reason.

```bash
ruff format --check .
ruff check .
mypy
python -m pip check
pytest -q --ignore=tests/performance
```

The normal suite uses Docker and PostgreSQL 18 `pg_dump`/`pg_restore`; it does not
call a live model provider. The opt-in scale benchmark is only needed for changes
to indexing/search/freshness performance or explicit acceptance work. See
[verification](docs/verification.md) for existing evidence and missing gates.

## Dependencies And Database Changes

Pins are intentional. Change `pyproject.toml` and `constraints.txt` together,
review licenses/notices and document upgrades in [dependency review](docs/dependency-review.md).
Dependencies imported directly at runtime should be declared directly. Do not
commit a machine-specific `pip freeze` containing editable paths or credentials.

Database changes need an Alembic migration and an upgrade/downgrade test. Never
rewrite an already deployed revision to change its meaning. Explain data impacts
and rollback limits in the PR. Back up local data before testing upgrades.

## Build Packages

From a development environment:

```bash
python -m pip install --constraint constraints.txt hatchling==1.28.0
python -m hatchling build
```

Artifacts appear in ignored `dist/`. Inspect wheel and source archive contents
before distribution: no `.env`, private session notes, caches or local tool
configuration. Source archives include migrations, scripts and docs; a wheel alone
does not provide the complete checkout-based operating environment.
Publishing packages/containers also requires the review in
[dependency review](docs/dependency-review.md).

## Pull Requests

Use the PR template. Explain what changed, why, checks run and material limits.
Do not include credentials, private repository content, local absolute paths or
large generated artifacts. Contributions are made under the project's
[MIT License](LICENSE); retain third-party attribution and licenses.

For security issues, use [SECURITY.md](SECURITY.md) instead of a public issue.
