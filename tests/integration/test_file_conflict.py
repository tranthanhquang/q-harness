from pathlib import Path

import pytest

from qharness.runtime.tools import FileConflict, read_file, write_file
from qharness.security.policy import ApprovalScope


@pytest.mark.integration
def test_external_file_change_is_never_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "source.py"
    target.write_text("before", encoding="utf-8")
    scope = ApprovalScope((tmp_path,), (), False)
    read = read_file(scope, target)
    target.write_text("new user content", encoding="utf-8")
    with pytest.raises(FileConflict):
        write_file(scope, target, "agent content", read.sha256)
    assert target.read_text(encoding="utf-8") == "new user content"
