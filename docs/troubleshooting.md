# Troubleshooting

Run commands from the source root with the Python 3.12 virtual environment active.
Use the JSON error `code` and `correlation_id` when diagnosing a failed request.
Do not paste tokens, provider keys or credential-bearing connection URLs into logs.

| Symptom | Check and recovery |
|---------|--------------------|
| `DEPENDENCY_UNAVAILABLE`, database connection failure | Check `docker compose ps postgres`, `QH_DATABASE_URL` and `alembic current`. Start PostgreSQL and run `alembic upgrade head`. |
| `qh` missing or wrong Python | Activate `.venv`; run `python --version` and reinstall with `python -m pip install --constraint constraints.txt -e '.[dev]'`. |
| No active Project | Set `QH_PROJECT_ID`, pass `qh --project UUID ...`, or run from the workspace containing `.qharness/project.yaml`. Use `qh project list --json` to find the UUID. |
| Duplicate repository | A canonical path can belong to only one Project. Use the existing registration or register a separate checkout. |
| Workspace/repository unavailable | Restore its original path and permissions. Registration is not deleted automatically. |
| `KNOWLEDGE_STALE` or missing new search result | Restore access and run `qh project refresh --json`. Check `.gitignore`, the denylist, UTF-8 encoding and the 1 MB file limit. Secrets, symlinks and build outputs are excluded. |
| HTTP 401 | Supply `Authorization: Bearer TOKEN` with the same local token as the service. Tokens must contain at least 32 characters. |
| HTTP 403 / Project scope denied | Check `QH_PROJECT_ID`, URL Project ID, host and Origin. Use `127.0.0.1`; restarting with the intended Project is required to change service scope. |
| Health shows `degraded` | Check `database`. Idle worker liveness is not currently tracked by the health endpoint; inspect task execution heartbeats and the worker terminal. |
| Task stays `WAITING_APPROVAL` | Supply a scope file with registered repository paths, tools, executable names and explicit required gates. Then approve and queue it. |
| Queued execution never starts | Run `qh worker` with the same database and sandbox image as the CLI. |
| Codex CLI unavailable or signed out | Install Codex CLI on the worker host, run `codex login`, then check `codex login status`. The default worker uses the device login. |
| Missing model/key with `QH_MODEL_PROVIDER=openai` | Set `QH_MODEL` and `OPENAI_API_KEY` in the worker environment. |
| Sandbox/render failure | Check `docker info` and `docker image inspect q-harness-sandbox:dev`. Build `Dockerfile.sandbox`; use `QH_SANDBOX_IMAGE` to select the immutable image ID. |
| Required tests failed or `NOT_RUN` | Inspect `qh task status UUID --json`. Verify every gate's exact command and working directory; rerun after the last write. Missing gates cannot satisfy completion. |
| `FILE_CONFLICT` | Inspect the externally changed file and resolve the conflict yourself. Refresh knowledge, then explicitly continue/reapprove. Q-Harness does not overwrite, merge or roll back the external change. |
| `INTERRUPTED` execution / `BLOCKED` task | Startup reconciliation detects stale claimed/running executions. Inspect retained changes and evidence; use `qh task continue UUID`, then approve and execute a new attempt. No automatic resume occurs. |
| Idempotency conflict | Reuse a key only for the identical request. Choose a new key for a changed request; inspect the original result before retrying. |
| Report blocked/invalid | Inspect `qh report status UUID --json`, missing data and validation evidence. Register the contract/template, restore its exact checksum or publish a new version, and correct unsupported fields. |
| Formula totals look unevaluated | XLSX formulas are preserved and checked; Q-Harness independently validates supported totals and does not recalculate workbook formulas. |
| Skill is rejected/stale | Supply version/source/license/read permissions and contained referenced assets. A modified registered version must be versioned again. Verification never runs its scripts. |
| Backup client error | Put PostgreSQL 18 `pg_dump` and `pg_restore` on `PATH`; verify source/target access and use the [restore procedure](backup-restore.md). |

For a stuck sandbox after a host crash, inspect `docker ps --filter
label=q-harness.managed=true`. Compare container names with execution evidence
before removing a container; do not remove unrelated containers. Normal runner
completion, cancellation and timeout force cleanup of that runner's named container.

CLI exit meanings: `2` input, `3` authorization, `4` missing entity, `5` conflict,
`6` approval/scope, `7` validation, `8` blocked, `9` dependency, `10` internal error.
`NOT_RUN`, `BLOCKED` and `FAILED` are never evidence of verified completion.
