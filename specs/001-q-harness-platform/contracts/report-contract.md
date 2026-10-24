# `report.md` Contract

Every registered report type contains a Markdown contract named `report.md` beside its checksum-pinned DOCX or XLSX template. Q-Harness reads and validates this file before collecting data.

## Precedence

1. Q-Harness security, Project scope and permission policy always win.
2. `report.md` controls content, allowed data sources, missing-data behavior and validation.
3. The DOCX/XLSX template controls presentation, layout, style and fixed formulas.
4. A user request may narrow scope but cannot remove required sections or broaden data permissions.

## Required Structure

`report.md` begins with YAML front matter conforming to [report-contract.schema.json](./report-contract.schema.json), followed by these headings:

```markdown
---
template_id: weekly-progress
version: 1.0.0
scope: project
output_format: docx
template_file: template.docx
language: vi
required_permission: report:generate
data_sources:
  - project
  - tasks
  - executions
  - test_runs
required_sections:
  - id: overview
    title: Tổng quan
    required_fields: [period, project_name]
  - id: completed_work
    title: Công việc hoàn thành
    required_fields: [tasks]
missing_data_policy: mark_missing
validation:
  openable: true
  no_unresolved_placeholders: true
  preserve_template_checksum: true
---

# Purpose

Why this report exists and who reads it.

# Data Rules

How allowed sources map to required fields; no unstated source may be queried.

# Rendering Rules

Language, ordering, labels, number/date formats and template-specific constraints.

# Validation Rules

Required headings/tables/sheets/cells, cross-field checks and acceptance conditions.
```

## Registration Rules

- The contract and template must be inside an allowed project/platform template root.
- `template_id` + semantic version is unique in its scope.
- Contract and template checksums are stored at registration and verified before every render.
- The declared extension must match `output_format`.
- All front-matter data sources must be known and allowed for the registering Project.
- DOCX undeclared template variables, XLSX missing sheets/ranges or unsupported template features fail registration.
- Templates are trusted, operator-reviewed inputs. Arbitrary uploaded templates are not accepted in MVP.

## Missing Data

| Policy | Behavior |
|--------|----------|
| `fail` | Stop generation and record required missing fields. |
| `ask` | Move request to a blocked state and request operator input. |
| `mark_missing` | Render the contract-defined “Missing” marker and provenance gap. |
| `mark_na` | Render the contract-defined “N/A” marker only where the contract permits it. |

No policy permits invented or statistically inferred values.

## Rendering Rules

- Build a primitive data context only; do not expose service/domain objects to templates.
- DOCX rendering uses strict undefined variables, sandboxed Jinja and XML autoescaping; custom template filters are not allowed in MVP.
- XLSX generation populates declared input cells/ranges and does not create or rewrite formulas.
- Rendering runs without network and writes to a temporary artifact path.

## Validation Rules

Before state `READY`, Q-Harness must:

1. Verify contract/template checksums still match registration.
2. Reopen the generated OOXML ZIP successfully.
3. Verify every required section/field or sheet/range.
4. Verify no unresolved placeholder remains.
5. Verify DOCX structural expectations or XLSX styles/data types/formula strings.
6. Independently check report totals/consistency from source data.
7. Record template version/checksum, generator version and source provenance.
8. Atomically publish the file and then commit READY metadata.

Failure at any step records validation evidence and prevents `READY`.

