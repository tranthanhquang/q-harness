# Verification Record

Recorded on 2026-10-24. This record distinguishes implemented/tested behavior
from acceptance work that still requires another host or a human reviewer.

## Environment

| Component | Actual environment |
|-----------|--------------------|
| Host | macOS 26.5, Apple M1, 8 CPU cores, 16 GiB RAM |
| Python | 3.12.13 |
| PostgreSQL | 18.1, Docker, loopback port 55432 |
| Docker server | 29.4.0, Linux arm64 containers |
| Sandbox image | `sha256:8baf9711d0883a9b49e57d7dc091a81874b08a132b6b35c554fae5e9f0f37cec` |
| Dependencies | Exact resolution in `constraints.txt`; review in `dependency-review.md` |

The workspace has no Git metadata, so no repository diff or commit was verified.
Tests use disposable PostgreSQL databases and temporary repository fixtures.

## Automated Gates

| Gate | Command | Result |
|------|---------|--------|
| Format | `.venv/bin/ruff format --check .` | PASS, 114 files |
| Lint | `.venv/bin/ruff check .` | PASS |
| Types | `.venv/bin/mypy` | PASS, 64 source files |
| Installed dependencies | `.venv/bin/python -m pip check` | PASS |
| Unit/integration/contract/e2e/security | `PATH="/Library/PostgreSQL/18/bin:$PATH" .venv/bin/pytest -q --ignore=tests/performance` | PASS, 110 tests in 24.17 seconds; no skips |

The suite exercises real PostgreSQL migrations up/down, Project ownership,
token/path/symlink isolation, read-only ask, approval and test completion gates,
file conflicts, actual Docker tool execution, report validation, append-only
audit/recovery, skill verification and backup/restore. MCP transport tests use the
actual SDK over Streamable HTTP, including authenticated tool calls.
[Raw suite output](evidence/test-suite.txt).

Additional deployment check: started an isolated Compose PostgreSQL instance,
wrote a sentinel row, recreated its container and read the same row. PASS with
the named volume mounted at `/var/lib/postgresql`. The existing deployment was
not recreated. [Raw storage evidence](evidence/compose-storage-evidence.json).
Upgrade guidance is in `backup-restore.md`.

## Scale Gate

The opt-in benchmark creates 10 Projects, 20 repositories per Project and 100,000
real eligible files per Project, with one million source rows and knowledge
chunks. It measures 20 status/search requests (two per Project), then a one-file
refresh. It bulk-seeds indexed rows; it does not measure full initial indexing
throughput, realistic mixed-language files or concurrent users.
Scale repositories are local source directories without Git metadata; separate
two-repository integration/e2e fixtures exercise real independent Git histories.

The final standard run passed in 285.63 seconds, including fixture setup:

| Measurement | Actual seconds | Acceptance limit | Result |
|-------------|----------------|------------------|--------|
| Search p95 | 2.062950 | 3 | PASS |
| Status p95 | 0.732991 | 3 | PASS |
| One-file refresh | 0.320528 | 30 | PASS |

Command: `QH_RUN_SCALE=1 QH_SCALE_EVIDENCE=.tmp/scale-evidence-concurrent.json .venv/bin/pytest -q tests/performance/test_acceptance_scale.py`.
[Raw measurements](evidence/scale-evidence.json) and
[pytest output](evidence/scale-run.txt) are preserved with this record.

The preceding sequential freshness check failed with search p95 3.739814 seconds.
Profiling identified filesystem metadata reads as the largest cost. Discovery now
uses descriptor-relative metadata reads and search overlaps freshness checks for
at most four repositories. Index writes remain sequential, and search waits for
every selected repository to pass freshness checks before returning results.

## Fresh Environment Smoke

Created a fresh Python 3.12 virtual environment and installed `.[dev]` using
`constraints.txt`. Installation and `pip check` passed. On a disposable database
and two independent Git repositories, the smoke run verified:

- Migrations, CLI Project creation/registration, status, index, search and ask.
- Template verification/registration and DOCX/XLSX reports reaching `READY`.
- Task creation, exact-scope approval, queueing and worker execution reaching
  `COMPLETED`, with Python and Node tests actually run inside Docker.
- A real `qh serve` process accepting authenticated health requests and rejecting
  missing-token requests.

Provider actions were deterministic; this did not call the live OpenAI API. Raw
smoke evidence is [preserved here](evidence/quickstart-evidence.json). This validates the documented
macOS workflow mechanics, rather than a new-user timing or usability result.

## Documentation And Packaging Preparation

On 2026-10-24, the installation/usage guides and GitHub repository preparation
were checked without changing runtime behavior:

- Format: 114 files unchanged; lint/type/dependency checks passed (64 source files).
- Normal automated suite: 110 passed in 21.14 seconds, no skips.
- Wheel and source archive built successfully, including a second build from the
  extracted source archive. License metadata is MIT and bundled report assets exist.
- Source archive contents exclude private authoring/session files, secrets files,
  local environments and caches. Git ignore rules were checked in a separate
  temporary repository; this workspace was not initialized as a Git repository.
- Relative file links in 13 Markdown documents and the CI YAML structure passed
  local checks. This does not establish that GitHub-hosted CI has run.
- A fresh virtual environment installed the wheel and passed `qh --help` and
  `pip check`, then installed the extracted source archive in editable mode.
  On a disposable database, its documented commands passed migrations,
  two-repository registration, index/search/ask with citations, one-file refresh,
  and both MIT-registered demo reports reaching `READY` in Docker.

[Documentation smoke evidence](evidence/documentation-smoke.json).
The new CI workflow has not been run on GitHub. No live model call, public push,
release upload or additional scale benchmark was performed for this documentation change.

## Outstanding Acceptance And Limits

| Item | Status |
|------|--------|
| Native Linux clean-host walkthrough (T099) | NOT_RUN; no Linux acceptance host supplied |
| Live model provider coding task | NOT_RUN; model/API credentials not used |
| Codex inside the VS Code UI (SC-008) | NOT_RUN; automated real MCP transport passed |
| New-developer first-result timing (SC-002) | NOT_RUN; no independent user timing |
| At least 90% first-attempt usability (SC-010) | NOT_RUN; no human trial |
| Independent reviewer clean-machine walkthrough (SC-013) | NOT_RUN; macOS automated smoke only |
| Bundled binary/container distribution review | NOT_CLEARED; see dependency review |

The health endpoint currently reports idle worker liveness as `unavailable` and
overall health as `degraded`; execution heartbeats are available. Backup restores
preserve absolute artifact paths, so moving hosts/paths needs explicit metadata
migration. These limits must remain visible during acceptance.

T099 and overall product acceptance remain open until their missing evidence is
recorded. Passing automated checks is not evidence for a human or unrun host gate.
