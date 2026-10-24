# Q-Harness MVP Validation Quickstart

Run from the Q-Harness source directory. Expected results are acceptance assertions;
actual host coverage and remaining gates are recorded in `docs/verification.md`.

For prerequisite installation and a Vietnamese usage guide, start with
[installation](../../docs/installation.md) and [usage](../../docs/usage.md).

Related design:

- [Implementation plan](./plan.md)
- [Data model](./data-model.md)
- [CLI contract](./contracts/cli.md)
- [HTTP contract](./contracts/openapi.yaml)
- [MCP tools](./contracts/mcp-tools.md)
- [Report contract](./contracts/report-contract.md)
- [Report contract schema](./contracts/report-contract.schema.json)

## Prerequisites

- macOS or Linux host
- Python 3.12
- Git and ripgrep
- Docker with enough resources for PostgreSQL and one sandbox container
- An OpenAI API key and an explicit accessible model only for the coding step
- Two independent fixture repositories created by the test fixture setup

The worker runs on the host and controls sandbox containers. Do not mount the Docker socket into the Q-Harness service or an execution container.

## 1. Install and Start Dependencies

These commands assume a fresh deployment. For an existing PostgreSQL container,
follow `docs/backup-restore.md` before applying the corrected PostgreSQL 18 volume
mount; do not recreate it before verifying a backup and restore.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --constraint constraints.txt -e '.[dev]'
docker compose up -d --wait postgres
docker build -f Dockerfile.sandbox -t q-harness-sandbox:dev .
```

Set local-only configuration in the current shell:

```bash
export QH_DATABASE_URL='postgresql+psycopg://qharness:qharness@127.0.0.1:55432/qharness'
export QH_DATA_DIR="$PWD/.tmp/qharness-data"
export QH_LOCAL_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OPENAI_API_KEY='<operator-provided-secret>'
export QH_MODEL='<operator-selected-model>'
export QH_SANDBOX_IMAGE="$(docker image inspect q-harness-sandbox:dev --format '{{.Id}}')"
alembic upgrade head
```

Expected:

- Secrets are not written to `.qharness/project.yaml`, PostgreSQL events or logs.
- The service refuses to start when `QH_LOCAL_TOKEN` is absent or the bind host is not loopback.

## 2. Create a Multi-Repository Project

Create fresh demo fixtures outside your source repositories; the builder also
creates real Python/Node tests and an approval scope with absolute paths:

```bash
export QH_DEMO_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/qh-demo.XXXXXX")"
python - <<'PY'
import os
from pathlib import Path
from tests.fixtures.build import build
build(Path(os.environ['QH_DEMO_ROOT']).resolve())
PY
```

Register them:

```bash
export QH_PROJECT_ID="$(qh init --name 'Q-Harness Demo' --workspace "$QH_DEMO_ROOT/workspaces/demo" --json | python -c 'import json,sys; print(json.load(sys.stdin)["data"]["id"])')"
qh project add "$QH_DEMO_ROOT/repositories/api" --role api --name api --json
qh project add "$QH_DEMO_ROOT/repositories/web" --role web --name web --json
qh project status --json
```

Expected:

- One stable Project ID is returned.
- `api` and `web` have independent repository IDs, branches and HEAD SHAs.
- Re-registering either canonical path under another Project exits with code `5` and `STATE_CONFLICT` or the more specific duplicate-path code.
- A path traversal or symlink escape is denied without exposing target content.

## 3. Index, Search and Refresh

```bash
qh project index --full --json
qh knowledge search 'health check' --json
qh ask 'health check' --json
```

Expected:

- Results cite repository, relative path, line/symbol, content hash and branch/commit where available.
- Python and TypeScript/JavaScript fixtures return symbol results.
- Excluded secrets, `.git`, binaries and build outputs do not appear.
- `/ask` creates no task, report, file write or command execution.

Modify one non-secret fixture file outside Q-Harness, then run:

```bash
qh project refresh --json
qh ask 'health check' --json
```

Expected:

- Only affected file rows are replaced.
- The new content is visible within 30 seconds or the response explicitly reports `STALE`.
- No full reindex is required.

## 4. Verify Local HTTP and MCP Authentication

Start the service and worker in separate terminals with the same environment,
including `QH_PROJECT_ID` and the sandbox image. Model credentials are needed
only when the worker executes coding tasks:

```bash
qh serve --host 127.0.0.1 --port 8765
qh worker
```

Check authenticated health:

```bash
curl -sS -H "Authorization: Bearer $QH_LOCAL_TOKEN" http://127.0.0.1:8765/healthz
```

Expected: `database: ok`. The current health endpoint conservatively reports
`worker: unavailable` / `status: degraded`; it does not prove idle worker liveness.
Inspect execution heartbeat/status when running a task.

Without a token, the service must reject the request before Project lookup:

```bash
curl -i http://127.0.0.1:8765/v1/projects
```

With the token:

```bash
curl -sS \
  -H "Authorization: Bearer $QH_LOCAL_TOKEN" \
  http://127.0.0.1:8765/v1/projects
```

Expected: the first request is unauthorized; the second returns only the bound Project. Binding to `0.0.0.0` must fail startup validation.

Configure Codex locally without storing the token value in its config:

```toml
[mcp_servers.qharness]
url = "http://127.0.0.1:8765/mcp"
bearer_token_env_var = "QH_LOCAL_TOKEN"
enabled_tools = [
  "qh_project_get",
  "qh_knowledge_search",
  "qh_task_get",
  "qh_report_list",
  "qh_report_generate"
]
```

Expected MCP checks:

- `qh_project_get` and `qh_knowledge_search` match native results for the same Project.
- Supplying another Project ID returns `PROJECT_SCOPE_DENIED` or `NOT_FOUND` without leaking existence/details.
- No coding-execution MCP tool is advertised in MVP.

## 5. Execute One Bounded Coding Task

Create a natural-language task:

```bash
qh run 'Change health_check and healthCheck from ok to ready in API and web, and update their tests.py and tests.mjs expectations' --json
qh task status <TASK_ID> --json
qh notification list --json
```

Expected: Q-Harness shows intent/type/risk/workflow and waits in
`WAITING_APPROVAL`. The operator supplies the exact paths, commands and required
tests in the scope below. Use the task UUID from the JSON `id` field as `<TASK_ID>`.

Approve the exact fixture scope and execute with an idempotency key:

```bash
qh task approve <TASK_ID> --scope-file "$QH_DEMO_ROOT/scopes/two-repo-task.json" --json
qh task execute <TASK_ID> --idempotency-key demo-two-repo-0001 --json
qh task status <TASK_ID> --json
```

Expected:

- One approval covers actions inside the approved scope without repeated prompts.
- Network is off; test containers receive sanitized copies of approved repository files.
- API and web tests run separately and combined contract evidence is recorded.
- A failed or `NOT_RUN` required test prevents `COMPLETED`.
- Reusing the same idempotency key and request returns the existing execution; a different request with that key is rejected.

## 6. Verify Conflict and Interruption Safety

Run the targeted acceptance tests:

```bash
pytest -q tests/integration/test_file_conflict.py
pytest -q tests/integration/test_interrupted_execution.py
```

Expected file-conflict behavior:

- The fixture changes after tool read but before write.
- Q-Harness returns `FILE_CONFLICT`, preserves the external content, blocks the task and does not auto-merge/overwrite.

Expected interruption behavior:

- A worker is terminated after a controlled source change.
- On restart, the execution becomes `INTERRUPTED`, the task becomes `BLOCKED`, evidence remains, and knowledge is refreshed or marked stale.
- No container or task automatically resumes or rolls back; `qh task continue` requires an explicit operator decision.

## 7. Generate Governed Reports

Verify and register the bundled trusted templates, then generate both reports.
Registration records operator trust and the declared license; review third-party
templates before registering them.

```bash
qh report template verify src/qharness/reports/templates/weekly-progress
qh report template register src/qharness/reports/templates/weekly-progress --platform --license MIT --json
qh report template verify src/qharness/reports/templates/test-results
qh report template register src/qharness/reports/templates/test-results --platform --license MIT --json
qh report list --json
qh report generate weekly-progress --idempotency-key report-weekly-0001 --json
qh report generate test-results --idempotency-key report-tests-0001 --json
qh report status <REPORT_ID> --json
```

Expected:

- The registry resolves `report.md` and checksum-pinned template before reading data.
- Weekly progress produces a valid DOCX; test results produces a valid XLSX.
- Generated files reopen successfully, contain required sections/sheets/fields, contain no unresolved placeholders and retain template/data provenance.
- Missing data follows the contract policy and is never invented.
- XLSX formulas remain template-controlled; validation does not falsely claim recalculation.
- Artifact paths appear only when report state is `READY`.

## 8. Run Quality Gates

```bash
ruff format --check .
ruff check .
mypy
pytest -q tests/unit
pytest -q tests/integration
pytest -q tests/contract
pytest -q tests/e2e
pytest -q tests/security
QH_RUN_SCALE=1 pytest -q tests/performance -m acceptance_scale
```

Tests require PostgreSQL permission to create/drop disposable databases and a
local `q-harness-sandbox:dev` image. Backup tests also require PostgreSQL 18
`pg_dump`/`pg_restore` on `PATH`. The scale test creates one million real files and
database rows; reserve at least 10 GB of free space. Its measurements are written
to `.tmp/scale-evidence.json` (override with `QH_SCALE_EVIDENCE`). Initial indexing
throughput is outside this query/refresh latency test.

Expected acceptance evidence:

- CLI, OpenAPI and MCP contracts pass.
- Cross-Project search/path/tool leakage tests all pass.
- The scale fixture covers 10 Projects, 20 repositories per Project and 100,000 eligible files per Project.
- At least 95% of status/search requests meet 3 seconds in the declared acceptance environment.
- One-file refresh completes or reports stale within 30 seconds.
- The complete clean-machine walkthrough finishes without undocumented steps or obsolete commands.

## Failure Interpretation

- `BLOCKED` means operator input, approval, conflict resolution or environment repair is required.
- `FAILED` means the attempted workflow finished unsuccessfully with evidence.
- `INTERRUPTED` is an execution outcome; its Task is `BLOCKED`.
- `NOT_RUN` is not a passing test result.
- Missing Docker/database/provider support is `DEPENDENCY_UNAVAILABLE`, never a verified completion.

