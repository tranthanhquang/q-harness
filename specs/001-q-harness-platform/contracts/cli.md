# CLI Contract

Command name: `qh`

The CLI calls the same application services as HTTP/MCP. It may run without the loopback service, but requires PostgreSQL and other dependencies needed by the requested command.

## Global Rules

- Human-readable output is the default; `--json` returns the stable JSON envelope below.
- `--project <id>` overrides automatic Project discovery.
- Without `--project`, Q-Harness resolves the current directory against registered workspace/repository roots. Zero or multiple matches is an error; it never scans unregistered paths.
- Destructive, network, credential or expanded-path actions require approval even when invoked locally.
- Secrets never appear in output, command history suggestions or logs.
- Commands that create side effects accept `--idempotency-key` where noted.

### JSON Envelope

```json
{
  "ok": true,
  "data": {},
  "error": null,
  "correlation_id": "corr_..."
}
```

Errors use:

```json
{
  "ok": false,
  "data": null,
  "error": {
    "code": "FILE_CONFLICT",
    "message": "The file changed after it was read.",
    "details": {}
  },
  "correlation_id": "corr_..."
}
```

## Commands

| Command | Required input | Result | Side effect / gate |
|---------|----------------|--------|--------------------|
| `qh init --name NAME --workspace PATH` | Project name and existing workspace | Project ID and config path | Creates Project/config; path must be unowned |
| `qh project add PATH --role ROLE [--name NAME]` | Registered Project context and Git path | Repository record | Reject duplicate canonical path |
| `qh project list` | None | Projects and availability | Read-only |
| `qh project use PROJECT_ID` | Project ID | Active client context | Local client setting only |
| `qh project status` | Project context | Repositories, Git/index freshness and blocked work | Read-only |
| `qh project index [--full]` | Project context | Index job/result | Reads registered roots; `--full` explicit |
| `qh project refresh` | Project context | Incremental refresh result | Reads registered roots |
| `qh knowledge search QUERY [--repository ID] [--limit N]` | Project context and query | Fresh lexical/symbol results with provenance | Read-only; freshness check required |
| `qh ask QUESTION` | Project context and question | Concise sourced answer | Enforced read-only tool set |
| `qh run REQUEST` | Natural-language request | Classification, proposed task scope and task ID | No execution before scope approval |
| `qh task list` | Project context | Tasks and current status | Read-only |
| `qh task status TASK_ID` | Task ID | Task, executions, gates and events | Read-only |
| `qh task approve TASK_ID --scope-file FILE` | Exact proposed scope | Approval ID/scope hash | One bounded approval; expansion needs new approval |
| `qh task execute TASK_ID --idempotency-key KEY` | Approved task | Queued execution ID | Worker executes in sandbox |
| `qh task continue TASK_ID` | BLOCKED task and explicit decision | New/continued authorized attempt | Never automatic after interruption/conflict |
| `qh task cancel TASK_ID` | Active task | Updated status | Cooperative stop then forced timeout |
| `qh notification list [--since EVENT_ID]` | Project context | Required notification event projection | Read-only; no background push/unread state |
| `qh report list` | Project context | Effective template registry | Read-only |
| `qh report template verify PATH` | Template directory containing `report.md` | Contract, checksum and compatibility evidence | Reads only; does not register invalid input |
| `qh report template register PATH` | Previously verified template directory | Registered immutable template version | Local operator; stores checksums/evidence |
| `qh report generate TEMPLATE_ID [--scope FILE] --idempotency-key KEY` | Registered template and scope | Report ID/status | Writes artifact only under artifact root |
| `qh report status REPORT_ID` | Report ID | State, validation and artifact path if READY | Read-only |
| `qh skill list` | Project context | Discovered/verified skills | Read-only |
| `qh skill verify PATH` | Allowed skill path | Verification evidence | Reads only; does not execute scripts |
| `qh serve` | `QH_LOCAL_TOKEN`, database/config | Loopback HTTP+MCP service | Fails if host is not loopback or token absent |
| `qh worker` | Database/config and Docker | Worker identity/heartbeat | Host process; no Docker socket mount |

`qh run` is the execution entrypoint; users do not label the request as bug/feature/refactor. `qh ask` and `qh report` remain explicit because their safety/output semantics are distinct.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | Invalid command/input |
| `3` | Authentication or authorization denied |
| `4` | Project/entity not found |
| `5` | State, idempotency or file conflict |
| `6` | Approval required or scope exceeded |
| `7` | Contract/template/validation failure |
| `8` | Task/report blocked or required test not run |
| `9` | Dependency unavailable (database, Docker, provider) |
| `10` | Unexpected internal error; correlation ID printed |

## Output Safety

- Human output may summarize source and logs; JSON output never includes raw secrets.
- `qh task status` distinguishes `FAILED`, `BLOCKED`, `CANCELLED` and interrupted execution explicitly.
- Report commands print an artifact path only after state `READY`.
- Ask output includes repository/path/line or symbol/commit provenance and freshness.

