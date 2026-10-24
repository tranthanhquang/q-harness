from pathlib import Path

import pytest

from qharness.security.paths import (
    PathViolation,
    canonical_directory,
    contained_path,
    find_project_file,
)


def test_canonical_directory_and_nearest_project_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    nested = workspace / "a" / "b"
    nested.mkdir(parents=True)
    config = workspace / ".qharness" / "project.yaml"
    config.parent.mkdir()
    config.write_text("project_id: test\n", encoding="utf-8")
    assert canonical_directory(workspace) == workspace.resolve()
    assert find_project_file(nested) == config


def test_containment_rejects_traversal_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises(PathViolation):
        contained_path(root, root / ".." / "outside")
    with pytest.raises(PathViolation):
        contained_path(root, root / "link")
