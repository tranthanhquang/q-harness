---
template_id: weekly-progress
version: 1.0.0
scope: platform
output_format: docx
template_file: template.docx
language: vi
required_permission: report:generate
data_sources: [project, tasks]
required_sections:
  - id: overview
    title: Tổng quan
    required_fields: [project_name, task_count]
missing_data_policy: mark_missing
validation:
  openable: true
  no_unresolved_placeholders: true
  preserve_template_checksum: true
---
# Purpose

Báo cáo tiến độ dự án dành cho người vận hành.

# Data Rules

Chỉ dùng dữ liệu Project và Task đã được cấp quyền.

# Rendering Rules

Giữ bố cục DOCX và hiển thị Missing thay vì suy đoán.

# Validation Rules

File phải mở được và không còn placeholder.

