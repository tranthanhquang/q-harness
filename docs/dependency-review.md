# Dependency Review

Reviewed installed distribution metadata on 2026-10-24. Versions below match
`pyproject.toml`. Runtime dependencies and parser grammars are exact pins;
`constraints.txt` constrains installation. Python is restricted to 3.12.

## Runtime Inventory

| Distribution | Version | Declared license |
|--------------|---------|------------------|
| alembic | 1.20.0 | MIT |
| defusedxml | 0.7.1 | PSF |
| docxtpl | 0.20.2 | LGPL-2.1-only |
| fastapi | 0.158.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| mcp | 2.0.0 | MIT |
| openai | 2.8.1 | Apache-2.0 |
| openpyxl | 3.1.5 | MIT |
| psycopg / psycopg-binary | 3.3.2 | LGPL-3.0-only; binary includes separate third-party notices |
| pydantic | 2.13.1 | MIT |
| pydantic-settings | 2.12.0 | MIT |
| python-docx | 1.2.0 | MIT |
| PyYAML | 6.0.3 | MIT |
| SQLAlchemy | 2.1.0 | MIT |
| tree-sitter | 0.25.2 | MIT |
| tree-sitter-python | 0.25.0 | MIT |
| tree-sitter-typescript | 0.23.2 | MIT |
| typer | 0.26.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |

The Tree-sitter runtime, Python grammar and TypeScript/TSX grammar are upgraded
together. JavaScript uses the TypeScript parser for the supported syntax subset;
contract fixtures define coverage. Unsupported files retain lexical search only.

## Development and Build

| Distribution | Version | Declared license |
|--------------|---------|------------------|
| hatchling | 1.28.0 | MIT |
| mypy | 1.18.2 | MIT |
| pytest | 9.0.2 | MIT |
| pytest-cov | 7.0.0 | MIT |
| ruff | 0.14.2 | MIT |
| types-PyYAML | 6.0.12.20260906 | Apache-2.0 |
| types-jsonschema | 4.26.0.20261006 | Apache-2.0 |
| types-openpyxl | 3.1.5.20261017 | Apache-2.0 |
| types-defusedxml | 0.7.0.20260504 | Apache-2.0 |

Development tools are not installed in the execution sandbox. The sandbox adds
Debian Git/ripgrep/Node/npm tooling and the four report libraries pinned in
`Dockerfile.sandbox`. Its Python base is digest-pinned; Debian package resolution
depends on the build date. PostgreSQL uses `postgres:18.1-alpine` for local tests.
Record the resolved image ID for an accepted build and reuse it via
`QH_SANDBOX_IMAGE`; rebuilding the tag is not proof of identical image contents.

## Decisions and Obligations

- Local development: retain the selected libraries. Parser, PostgreSQL migration,
  DOCX/XLSX round-trip and CLI/HTTP/MCP contract tests are required upgrade gates.
- Psycopg and docxtpl: retain their LGPL license text and copyright notices when
  redistributing. Preserve recipients' ability to replace the libraries; retain
  source/modifications and satisfy the applicable source and relinking obligations.
  The project currently uses unmodified installed libraries.
- `psycopg-binary` bundles native libraries, including libpq, OpenSSL and Kerberos
  components. Review and ship each bundled library's actual notices and source
  obligations with a redistributed wheel/image; the Python package license alone
  is not a complete binary license inventory.
- MIT/PSF/Apache/BSD dependencies and grammars: preserve the applicable license and
  copyright texts; preserve Apache NOTICE files when supplied. Do not infer a
  grammar's license from the Tree-sitter runtime's license.
- Project-authored code, documentation and bundled demo report contracts/templates
  use the root MIT license. External templates and skills require declared source, license,
  version and checksums before registration. Recording a license is not a legal
  grant for arbitrary third-party assets.
- Source publication does not relicense third-party dependencies. Bundled binary
  and container distribution review: **not cleared**. Before distributing such artifacts,
  capture the full resolved transitive inventory and image OS packages, collect
  notices, check vulnerability advisories and obtain the applicable license review.
  This implementation review does not claim a vulnerability scan or legal approval.

## Upgrade Procedure

1. Change explicit pins intentionally; resolve in a new Python 3.12 environment.
2. Inspect distribution metadata and bundled notices, including newly introduced
   transitive dependencies. Update this record and constraints from the resolution.
3. Build a new sandbox image and record its immutable ID/digest.
4. Run format/lint/type, parser, migration round-trip, report reopen, transport,
   sandbox security and affected acceptance tests. Keep the previous environment
   and image available until the new version passes.

Inspect local metadata with `python -m pip inspect` and `python -m pip freeze`.
These inventories describe the current environment; do not commit editable paths,
credentials or machine-specific URLs as dependency requirements.
