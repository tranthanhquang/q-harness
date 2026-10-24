# Phase 0 Research: Q-Harness Platform MVP

**Date**: 2026-10-24

All Technical Context unknowns are resolved below. Exact dependency versions will be frozen in one committed lock/constraints file during bootstrap and changed only with contract-test evidence.

## 1. Application Shape and Python Baseline

**Decision**: Use one Python 3.12 installable package with synchronous application services. CLI, HTTP, MCP and worker are thin entrypoints over the same core.

**Rationale**: Python 3.12 satisfies the source direction and is supported by the selected libraries. Synchronous database transactions are sufficient for a single local operator and avoid async session/cancellation complexity. [Python 3.12 documentation](https://docs.python.org/3.12/)

**Alternatives considered**:

- Multiple deployable services: rejected because the MVP has one host/operator and shared state.
- Async-first application stack: rejected because no acceptance target requires it.
- Forking an existing coding agent: rejected by product scope and would import unrelated architecture.

## 2. HTTP, Validation and CLI

**Decision**: FastAPI with Pydantic v2 for the loopback service and Typer for the native CLI. Both call application services directly; FastAPI owns its compatible Starlette version.

**Rationale**: These libraries provide typed boundaries, generated OpenAPI and command help without requiring a second business layer. FastAPI recommends pinning FastAPI rather than independently pinning Starlette. [FastAPI features](https://fastapi.tiangolo.com/features/), [FastAPI version guidance](https://fastapi.tiangolo.com/deployment/versions/), [Typer documentation](https://typer.tiangolo.com/)

**Alternatives considered**:

- Django: rejected as broader than the local API/CLI need.
- Click directly: viable, but Typer matches the typed validation model with less command boilerplate.
- CLI calling HTTP for every command: rejected; in-process application-service calls allow project bootstrap without a running daemon.

## 3. PostgreSQL, Transactions and Worker Claiming

**Decision**: PostgreSQL 18 with SQLAlchemy 2.1, Psycopg 3.3 and Alembic. Use PostgreSQL full-text search with GIN indexes and claim local worker jobs from persisted execution rows using row locking.

**Rationale**: PostgreSQL is required by the product direction and can hold operational state, append-only events, lexical search and a small queue without Redis or Elasticsearch. `SKIP LOCKED` is explicitly suitable for queue-like consumers, while GIN is the preferred recurring full-text index. [PostgreSQL version policy](https://www.postgresql.org/support/versioning/), [full-text search](https://www.postgresql.org/docs/current/textsearch.html), [text-search indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html), [`SKIP LOCKED`](https://www.postgresql.org/docs/current/sql-select.html)

**Alternatives considered**:

- SQLite: simpler startup but fails to prove the selected concurrency/search/migration behavior.
- Redis/Celery: rejected because one local worker and persisted executions are enough.
- Elasticsearch/vector database: rejected; lexical/symbol retrieval is the MVP requirement.
- Raw SQL only: fewer dependencies, but explicit aggregate transactions and reversible schema evolution make SQLAlchemy/Alembic smaller over the full domain.

## 4. Model Provider and Agent Runtime

**Decision**: Define a narrow `ModelProvider` boundary and ship one OpenAI adapter using the Responses API. The configured model name is required at runtime and is not hardcoded. Implement the Standard workflow as an explicit deterministic state machine behind `AgentRuntime`; defer LangGraph.

**Rationale**: Official OpenAI documentation identifies Responses as the primary Python API and supports function/tool calling. The product needs provider separation but only one proven provider in MVP. LangGraph is aimed at long-running stateful workflows and durable persistence; automatic checkpoint resume is explicitly deferred and interrupted executions must block instead. [OpenAI Python SDK](https://developers.openai.com/api/reference/python), [OpenAI tools guide](https://developers.openai.com/api/docs/guides/tools), [LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)

**Alternatives considered**:

- LiteLLM: optional provider breadth without an MVP acceptance need; defer until a second provider is required.
- LangGraph now: rejected because it adds checkpoint/persistence concepts that contradict the deliberately manual MVP recovery flow.
- Provider-specific logic throughout workflow code: rejected because it would couple tool/state policy to one API.

## 5. MCP Transport and Local Authentication

**Decision**: MCP Python SDK 2.x over Streamable HTTP at `http://127.0.0.1:<port>/mcp`, mounted into the same ASGI service. Require an opaque bearer token from environment/config, validate Origin/host, and enforce Project scope server-side.

**Rationale**: The official SDK supports mounting MCP into an existing Starlette-compatible application. HTTP supports the clarified token boundary; stdio relies on launcher-process isolation and cannot satisfy the same bearer-token contract. OpenAI documents MCP as the way to expose server-backed capabilities to Codex. [MCP Python SDK installation](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/get-started/installation.md), [MCP authorization](https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/run/authorization.md), [MCP transport security](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports), [OpenAI MCP quickstart](https://developers.openai.com/plugins/build/app-quickstart)

**Alternatives considered**:

- MCP over stdio: rejected for MVP because the approved design requires a local token and shared loopback service.
- Separate MCP process/business implementation: rejected; it risks rule drift from CLI/HTTP.
- Remote OAuth/TLS: required if scope expands beyond loopback, but out of scope for the single-user MVP.

## 6. Source Discovery, Symbols and Search

**Decision**: Use `ripgrep` for safe file discovery/fast working-tree scans, Tree-sitter for Python and TypeScript/JavaScript symbols in MVP fixtures, and PostgreSQL full-text search for persisted chunks and symbols. Unsupported text languages still receive lexical path/line results.

**Rationale**: ripgrep respects Git ignore rules, skips hidden/binary files and does not follow symlinks by default; Q-Harness adds its own security denylist. Tree-sitter provides syntax trees and queries without language-specific compiler frontends. Per-file rows can be replaced transactionally after verifying the content hash. [ripgrep guide](https://github.com/BurntSushi/ripgrep/blob/master/GUIDE.md), [Tree-sitter documentation](https://tree-sitter.github.io/tree-sitter/), [Tree-sitter Python binding](https://github.com/tree-sitter/py-tree-sitter)

**Alternatives considered**:

- Persisted incremental syntax trees: deferred; reparse one changed file for simpler correctness.
- Every available Tree-sitter grammar: rejected due ABI/license/test surface; add languages only with fixtures and license review.
- `pg_trgm` and embeddings: deferred until retrieval evaluation demonstrates a gap.

## 7. Isolated Execution

**Decision**: A host worker launches one Docker container per execution using an image pinned by digest. Use a non-root user, default seccomp, all capabilities dropped, `no-new-privileges`, read-only root, explicit tmpfs, only approved repository mounts, disabled network by default, and CPU/memory/PID/wall-time limits.

**Rationale**: Docker documents that containers have no resource limits unless configured and that control of the daemon is highly privileged. Keeping the worker on the host avoids mounting the Docker socket into another container. Rootless Docker is preferred where supported. [Docker Engine security](https://docs.docker.com/engine/security/), [rootless mode](https://docs.docker.com/engine/security/rootless/), [seccomp](https://docs.docker.com/engine/security/seccomp/), [resource constraints](https://docs.docker.com/engine/containers/resource_constraints/)

**Alternatives considered**:

- Direct host shell: rejected because it cannot enforce file/network/resource boundaries.
- Worker container with host Docker socket: rejected because the socket grants excessive host control.
- Kubernetes/distributed workers: rejected for local MVP.
- Custom seccomp profile initially: defer; default profile plus dropped capabilities is smaller and less brittle.

## 8. Reports and Artifact Validation

**Decision**: Use `docxtpl` to render the single curated DOCX template, `python-docx` to reopen and validate it, and `openpyxl` with `defusedxml` for XLSX rendering/validation. Templates are registered, checksum-pinned and operator-reviewed; rendering runs without network.

**Rationale**: `docxtpl` is designed to populate an existing Word template, while `python-docx` can verify document structure. `openpyxl` handles OOXML workbooks and explicitly recommends `defusedxml` for XML-bomb protection. Formula strings are validated, but Q-Harness does not claim to recalculate them. [docxtpl documentation](https://docxtpl.readthedocs.io/en/latest/), [python-docx documentation](https://python-docx.readthedocs.io/en/stable/), [openpyxl documentation](https://openpyxl.readthedocs.io/en/stable/)

**Alternatives considered**:

- Arbitrary uploaded templates: rejected as an injection and compatibility risk.
- `python-docx` only: fallback if `docxtpl` license/security review fails, but it requires more custom template manipulation.
- Spreadsheet calculation engine at runtime: rejected; template formulas remain fixed and expected totals are independently validated.
- PDF rendering: deferred by the approved MVP scope.

## 9. Artifacts, Configuration and Secrets

**Decision**: Keep project-shareable configuration and report contracts/templates under `.qharness/`; store large artifacts outside repositories under `QH_DATA_DIR`; store only artifact metadata/checksums in PostgreSQL. Load model credentials and the local service token from environment/secret storage and redact them from events.

**Rationale**: This keeps reproducible rules under version control without committing index/cache/secrets or generated reports. Atomic temporary-write → validate → rename prevents partially generated artifacts from being published.

**Alternatives considered**:

- Binary artifacts in PostgreSQL: rejected because local files are simpler and avoid database bloat.
- S3-compatible storage: deferred until remote/distributed operation.
- Tokens in project config: rejected because project files may be committed.

## 10. Testing and Compatibility Policy

**Decision**: Use pytest with separate unit, integration, contract, sandbox-security, end-to-end and performance suites. Integration uses the repository Compose PostgreSQL service and real migrations; no Testcontainers dependency. Support macOS and Linux hosts with Docker; defer native Windows.

**Rationale**: Real PostgreSQL, Git repositories, parsers and rendered documents are necessary to prove the risky boundaries. Contract suites protect CLI/HTTP/MCP and dependency upgrades. Docker Desktop differs from native Linux, so both host classes require acceptance coverage.

**Alternatives considered**:

- Mock-only database/filesystem tests: rejected because they cannot prove isolation, migration or artifact behavior.
- Testcontainers: useful but redundant when Compose is already required for local setup.
- Native Windows in MVP: deferred to avoid path, permission and container parity work before core behavior is proven.

## License and Upgrade Gates

- FastAPI, Pydantic, SQLAlchemy, Alembic, Typer, pytest, Tree-sitter, `python-docx`, MCP Python SDK and `openpyxl` use permissive licenses according to their official repositories.
- Psycopg is LGPL-3.0 and `docxtpl` is LGPL-2.1-only; distribution notices and modification rules require review before release.
- `docxtpl` templates are treated as trusted reviewed code-like inputs; use strict undefined variables, sandboxed Jinja, XML autoescaping and no application objects/custom filters.
- Tree-sitter runtime and grammars are version-locked together and must parse one fixture per supported grammar during startup/contract tests.
- Dependency upgrades require license review plus CLI/HTTP/MCP, parser, database migration and report round-trip contract tests.

