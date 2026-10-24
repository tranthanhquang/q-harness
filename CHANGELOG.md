# Changelog

Changes are recorded here before a release. No published release is asserted by
this file. Version 0.1.0 is currently an unreleased MVP.

## [Unreleased]

### Added

- Project registration across independent Git repositories and scoped source indexing.
- CLI, loopback HTTP/MCP, source search and cited excerpts through `ask`.
- Coding task approval, worker execution, Docker test gates, audit and recovery.
- Verified DOCX/XLSX report templates and artifact provenance.
- Local PostgreSQL/artifact backup and restore scripts.
- Installation and usage guides, contribution/security policies and GitHub CI.

### Distribution Preparation

- MIT license for project-authored code, documentation and bundled demo templates.
- Explicit source-package contents and exclusion of local secrets/session notes.
- Direct declaration of existing Jinja2 and Uvicorn runtime dependencies.

### Known Limits

- Native Linux clean-host and live-model walkthroughs remain unverified.
- Idle worker health, artifact path relocation and human acceptance checks remain
  limited as described in [verification](docs/verification.md).
- Third-party binary/container distribution review remains open.
