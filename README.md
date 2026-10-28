# Q-Harness

A local engineering harness for working across repositories, finding source evidence,
running approved coding tasks, and producing traceable DOCX/XLSX reports.

**Status:** early MVP, version 0.1.0. Interfaces: CLI, loopback HTTP and MCP.
There is no web dashboard. Install from a source checkout; these instructions do
not assume a published PyPI package.

**Tiếng Việt:** [Cài đặt](docs/installation.md) · [Sử dụng và test](docs/usage.md) ·
[Chuẩn bị public GitHub](docs/publishing.md)

## What It Does

- Groups independent Git repositories into an isolated Project.
- Indexes source files and returns search results with repository/path/line evidence.
- Runs coding tasks through explicit scope approval, a host worker and Docker tests.
- Requires real passing test gates before marking a coding task complete.
- Generates DOCX/XLSX reports from verified, versioned templates.
- Records task events, approvals, report provenance and recovery state.

`qh ask` currently returns indexed excerpts and citations; it does not generate a
conversational model answer. Registration, indexing, search, ask and reports need
no model API key. Coding execution uses the device's Codex CLI login by default;
the direct Responses API provider remains available with explicit configuration.

## Requirements

| Component | Requirement |
|-----------|-------------|
| Host | macOS or Linux; macOS tested, native Linux walkthrough pending |
| Python | 3.12 (the package requires `>=3.12,<3.13`) |
| Tools | Git, ripgrep, Docker with Compose v2 |
| Database | PostgreSQL 18; Compose supplies a local instance |
| Backup/test clients | PostgreSQL 18 `pg_dump` and `pg_restore` on `PATH` |
| Coding execution | Codex CLI installed and signed in, plus built sandbox image; direct API is optional |

Node runs inside the sandbox; it is not required on the host for the bundled demo.
The optional million-file benchmark needs at least 10 GB free in addition to images
and normal development storage. See [measured results and limits](docs/verification.md).

## Install From Source

Clone the repository using its GitHub **Code** URL, then open the checkout root.
The commands below assume a **fresh deployment**. Existing installations must first
follow the [PostgreSQL 18 storage migration](docs/backup-restore.md#postgresql-18-storage);
recreating an older container before backup can hide its existing data.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --constraint constraints.txt -e '.[dev]'
docker compose up -d --wait postgres
docker build -f Dockerfile.sandbox -t q-harness-sandbox:dev .
alembic upgrade head
python -m pip check
qh --help
```

These commands use the local development database defaults from
[.env.example](.env.example), bound to `127.0.0.1:55432`. The example credentials
are for local development. Q-Harness does **not** automatically load `.env`.
For OS setup, configuration, restarting and troubleshooting, follow the
[Vietnamese installation guide](docs/installation.md).

For coding tasks, run `codex login status` on the worker host. If needed, run
`codex login` once with your normal device account. Q-Harness reuses that login
without a separate `--profile` or API key. Codex runs in a read-only temporary
directory and returns actions; Q-Harness still applies approval and test gates.
The worker uses the model name from `~/.codex/config.toml` when present, while
skipping personal hooks and plugins.

For coding execution through OpenAI-compatible gateways such as OpenRouter, set
`QH_MODEL_PROVIDER=openai` and `OPENAI_BASE_URL` to the provider's API root (for example,
`https://openrouter.ai/api/v1`). The gateway must support the OpenAI Responses API;
see [provider configuration](docs/usage.md#cấu-hình-provider). Q-Harness does not
load `.env` automatically, so load the file into the worker's environment.

## First Project

Replace the absolute paths below with existing local directories. `qh init`
returns the Project UUID; substitute it for `PROJECT_UUID`.

```bash
qh init --name 'My Project' --workspace /absolute/path/to/workspace --json
export QH_PROJECT_ID='PROJECT_UUID'
qh project add /absolute/path/to/api --role api --name api
qh project add /absolute/path/to/web --role web --name web
qh project index --full --json
qh knowledge search 'health check' --json
qh ask 'health check' --json
```

Use terms present in your source. For a ready-made two-repository fixture, expected
results, coding approvals and report examples, follow the [usage guide](docs/usage.md).
Project selection also works through `qh --project UUID COMMAND`, or automatically
inside a workspace containing `.qharness/project.yaml`.

## Common Commands

| Work | Commands |
|------|----------|
| Projects | `qh init`, `qh project add`, `qh project list`, `qh project status` |
| Knowledge | `qh project index --full`, `qh project refresh`, `qh knowledge search QUERY`, `qh ask QUERY` |
| Tasks | `qh run REQUEST`, `qh task list`, `qh task status UUID` |
| Approval | `qh task approve UUID --scope-file FILE` |
| Execution | `qh task execute UUID --idempotency-key KEY`, `qh worker --once` |
| Control | `qh task cancel UUID`, `qh task continue UUID` |
| Reports | `qh report template verify PATH`, `qh report template register PATH --license NAME` |
| Report output | `qh report generate TEMPLATE --idempotency-key KEY`, `qh report status UUID` |
| Other | `qh notification list`, `qh skill list`, `qh skill verify PATH` |
| Services | `qh serve --host 127.0.0.1 --port 8765`, `qh worker` |

Use `--help` on a command for its arguments. Data commands support `--json`.
Task commands take UUIDs, not human display IDs. Queueing a task does not execute it:
a worker must be running. HTTP mutations require a 16–128 character `Idempotency-Key`.

## Operation And Boundaries

- Bind HTTP/MCP to loopback and supply `QH_LOCAL_TOKEN` with at least 32 characters.
  One service is bound to one `QH_PROJECT_ID`.
- Run the worker on the host. Sandbox containers receive sanitized repository
  copies, no network and no host credentials. Do not expose the Docker socket.
- Approved coding tasks write to the selected source repositories. Review scope
  and Git diffs. Cancellation/interruption does not roll back source edits.
- PostgreSQL stores metadata; `QH_DATA_DIR/artifacts` stores report output.
  Back up both, plus repository/workspace files separately.
- MCP exposes knowledge, task inspection and reporting; coding execution is not
  advertised through MCP in this MVP.
- Health currently reports idle worker liveness as unavailable and overall health
  as degraded. Restoring artifacts to a new absolute path needs metadata migration.

## Development Checks

Start PostgreSQL, build the sandbox and install PostgreSQL 18 clients first:

```bash
ruff format --check .
ruff check .
mypy
python -m pip check
pytest -q --ignore=tests/performance
```

Every pytest session, including unit tests, creates a disposable PostgreSQL database.
The database role must have `CREATEDB`; set `QH_TEST_DATABASE_URL` to override its
connection. Backup tests also invoke `pg_dump`/`pg_restore`. No live API key is
needed for the automated suite. CI runs these gates on Ubuntu; the expensive
benchmark is opt-in and excluded from normal CI:

```bash
QH_RUN_SCALE=1 pytest -q tests/performance
```

Recorded measurements describe the tested host, not a performance guarantee.
See [CONTRIBUTING.md](CONTRIBUTING.md) for changes and local package builds.

## Repository Layout

```text
src/qharness/       Domain, services, CLI, HTTP/MCP and worker
migrations/         Alembic database migrations
tests/              Unit, integration, contract, e2e, security and scale tests
scripts/            Backup/restore and dependency inventory helpers
docs/               Installation, usage, operations and verification evidence
specs/              MVP specification, plan and public interface contracts
.github/            CI workflow and contribution templates
```

## Documentation

| Guide | Purpose |
|-------|---------|
| [Installation (VI)](docs/installation.md) | Prerequisites, local setup and restart |
| [Usage and testing (VI)](docs/usage.md) | Two-repository demo, coding, reports, HTTP and tests |
| [Publishing (VI)](docs/publishing.md) | Prepare the initial public GitHub repository |
| [Validation quickstart](specs/001-q-harness-platform/quickstart.md) | Detailed acceptance walkthrough |
| [Verification](docs/verification.md) | Actual results and outstanding acceptance gates |
| [Backup and restore](docs/backup-restore.md) | Snapshot, restore and PostgreSQL storage migration |
| [Troubleshooting](docs/troubleshooting.md) | Common failure diagnosis |
| [Codex MCP](docs/codex-mcp.md) | Local client configuration |
| [Dependency review](docs/dependency-review.md) | Dependency licenses and distribution obligations |
| [Specification](specs/001-q-harness-platform/spec.md) | Scope and acceptance criteria |

## Contributing And Security

Read [CONTRIBUTING.md](CONTRIBUTING.md). Use the issue/PR templates for reproducible
reports and small changes. Report vulnerabilities privately as described in
[SECURITY.md](SECURITY.md); do not post tokens or private source in public issues.
See [CHANGELOG.md](CHANGELOG.md) for the unreleased version.

## License

Project-authored code, documentation and bundled demo templates are available under
the [MIT License](LICENSE). Dependencies retain their own licenses. Redistributing
third-party binaries or container images requires their applicable notices and
obligations; see the [dependency review](docs/dependency-review.md).
