from pathlib import Path

import pytest

from qharness.reports.registry import InvalidReportContract, load_contract


def test_report_contract_requires_schema_and_declared_missing_policy(tmp_path: Path) -> None:
    contract = tmp_path / "report.md"
    contract.write_text("---\ntemplate_id: bad\n---\n# Purpose\n", encoding="utf-8")
    with pytest.raises(InvalidReportContract):
        load_contract(contract)


def test_valid_contract_keeps_security_precedence(tmp_path: Path) -> None:
    contract = tmp_path / "report.md"
    contract.write_text(
        """---
template_id: weekly-progress
version: 1.0.0
scope: project
output_format: docx
template_file: template.docx
language: vi
required_permission: report:generate
data_sources: [project, tasks]
required_sections:
  - id: overview
    title: Overview
    required_fields: [project_name]
missing_data_policy: mark_missing
validation:
  openable: true
  no_unresolved_placeholders: true
  preserve_template_checksum: true
---
# Purpose
Test.
# Data Rules
Declared only.
# Rendering Rules
Strict.
# Validation Rules
Openable.
""",
        encoding="utf-8",
    )
    assert load_contract(contract).front_matter["missing_data_policy"] == "mark_missing"
