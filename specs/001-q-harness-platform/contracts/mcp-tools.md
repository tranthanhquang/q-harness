# MCP Tool Contract

**Transport**: Streamable HTTP at `http://127.0.0.1:<port>/mcp`  
**Authentication**: Bearer token required for every request  
**Authority**: Server-side Project scope, permission and approval checks are authoritative

The MVP intentionally exposes a small surface to Codex. Coding execution remains native CLI/HTTP until a dedicated MCP approval flow is proven.

## Common Rules

- Every tool input includes an explicit `project_id`; MCP session state is never the sole Project selector.
- IDs, error codes and state names match CLI/HTTP contracts.
- Read tools cannot reach the write-capable tool registry.
- Tool responses provide both concise text `content` and machine-readable `structuredContent`.
- Unknown fields are rejected. Strings and result counts have bounded lengths.
- No raw command output, secret, token or unrestricted file content is returned.

### Success Shape

```json
{
  "content": [{"type": "text", "text": "Short operator-readable summary"}],
  "structuredContent": {
    "ok": true,
    "data": {},
    "correlation_id": "corr_..."
  }
}
```

### Error Shape

```json
{
  "content": [{"type": "text", "text": "Request denied."}],
  "structuredContent": {
    "ok": false,
    "error": {
      "code": "PROJECT_SCOPE_DENIED",
      "message": "The requested Project is outside this token scope.",
      "retryable": false,
      "details": {}
    },
    "correlation_id": "corr_..."
  },
  "isError": true
}
```

## `qh_project_get`

Read Project identity, repositories and freshness summary.

Input:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["project_id"],
  "properties": {
    "project_id": {"type": "string", "format": "uuid"}
  }
}
```

Output data: `project`, `repositories[]`, `freshness`, `blocked_task_count`. Paths are returned only for repositories in the authorized Project.

Permission: read-only `project:read`.

## `qh_knowledge_search`

Search fresh lexical/symbol knowledge with provenance.

Input:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["project_id", "query"],
  "properties": {
    "project_id": {"type": "string", "format": "uuid"},
    "query": {"type": "string", "minLength": 1, "maxLength": 1000},
    "repository_ids": {
      "type": "array",
      "maxItems": 20,
      "uniqueItems": true,
      "items": {"type": "string", "format": "uuid"}
    },
    "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10}
  }
}
```

Output data: `freshness_checked_at`, `results[]`; each result contains `repository_id`, `relative_path`, line range, optional symbol, excerpt, content hash, branch/commit and index status.

Permission: read-only `knowledge:read`. A stale source triggers refresh or an actionable stale response; it never silently returns stale results.

## `qh_task_get`

Read one task and its execution/gate timeline.

Input fields: required `project_id`, required `task_id`; both UUID strings.

Output data: task display ID/status/version, repository links, current approval scope summary, executions, test gate outcomes and required notification events. Tool arguments/output remain redacted.

Permission: read-only `task:read`.

## `qh_report_list`

List effective Project and platform report templates.

Input fields: required `project_id`; optional `output_format` enum `DOCX|XLSX`.

Output data: template ID, version, scope, language, output format, checksum, required permission and registration status.

Permission: read-only `report:read`.

## `qh_report_generate`

Create a report generation request from a registered template.

Input:

```json
{
  "type": "object",
  "additionalProperties": false,
  "required": ["project_id", "template_id", "idempotency_key"],
  "properties": {
    "project_id": {"type": "string", "format": "uuid"},
    "template_id": {"type": "string", "pattern": "^[a-z][a-z0-9-]{1,63}$"},
    "version": {"type": "string"},
    "scope": {"type": "object", "maxProperties": 10},
    "idempotency_key": {"type": "string", "minLength": 16, "maxLength": 128}
  }
}
```

Output data: report ID, state, resolved template version/checksum and status URL/reference. Artifact path appears only when READY.

Permission: `report:generate`. The explicit MCP tool call is the requested action, but server policy still validates token scope, registered data sources and artifact destination.

## Error Codes

`AUTH_REQUIRED`, `PROJECT_SCOPE_DENIED`, `NOT_FOUND`, `INDEX_STALE`, `APPROVAL_REQUIRED`, `SCOPE_EXCEEDED`, `STATE_CONFLICT`, `IDEMPOTENCY_CONFLICT`, `TEMPLATE_INVALID`, `MISSING_DATA`, `VALIDATION_FAILED`, `DEPENDENCY_UNAVAILABLE`, `INTERNAL_ERROR`.

## Client Configuration Constraint

Codex should obtain the bearer token through an environment-variable reference, not plaintext committed configuration. Client tool enablement/approval settings are defense-in-depth and never replace Q-Harness authorization.

