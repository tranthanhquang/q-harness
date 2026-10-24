---
template_id: test-results
version: 1.0.0
scope: platform
output_format: xlsx
template_file: template.xlsx
language: vi
required_permission: report:generate
data_sources: [project, test_runs]
required_sections:
  - id: tests
    title: Tests
    required_fields: [project_name, test_passed, test_failed, test_not_run]
missing_data_policy: mark_missing
validation:
  openable: true
  no_unresolved_placeholders: true
  preserve_template_checksum: true
  required_sheets: [Tests]
---
# Purpose

Báo cáo kết quả kiểm thử.

# Data Rules

Chỉ dùng Project và TestRun được cấp quyền.

# Rendering Rules

Không sửa hoặc tự tính lại công thức template.

# Validation Rules

Workbook phải mở được và giữ nguyên công thức.

