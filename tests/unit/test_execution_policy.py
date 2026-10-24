from pathlib import Path

import pytest

from qharness.runtime.tools import FileConflict, read_file, write_file
from qharness.security.policy import ApprovalScope, ScopeEscalation


def test_approval_scope_rejects_path_command_and_network_escalation(tmp_path: Path) -> None:
    scope = ApprovalScope((tmp_path,), ("pytest",), network=False)
    scope.require_path(tmp_path / "inside.py")
    scope.require_command(("pytest", "-q"))
    with pytest.raises(ScopeEscalation):
        scope.require_path(tmp_path.parent / "outside.py")
    with pytest.raises(ScopeEscalation):
        scope.require_command(("rm", "-rf", "x"))
    with pytest.raises(ScopeEscalation):
        scope.require_network()


def test_compare_before_write_preserves_external_change(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("first", encoding="utf-8")
    scope = ApprovalScope((tmp_path,), (), network=False)
    snapshot = read_file(scope, target)
    target.write_text("external", encoding="utf-8")
    with pytest.raises(FileConflict):
        write_file(scope, target, "ours", snapshot.sha256)
    assert target.read_text(encoding="utf-8") == "external"
