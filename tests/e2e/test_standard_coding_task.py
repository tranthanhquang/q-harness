import hashlib
from pathlib import Path

import pytest

from qharness.runtime.standard import Change, StandardWorkflow
from qharness.security.policy import ApprovalScope


@pytest.mark.e2e
def test_standard_workflow_requires_real_passing_tests(tmp_path: Path) -> None:
    source = tmp_path / "value.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    scope = ApprovalScope((tmp_path,), ("python",), False)
    workflow = StandardWorkflow(scope)
    success = workflow.execute(
        [Change(source, "VALUE = 2\n", hashlib.sha256(b"VALUE = 1\n").hexdigest())],
        [("python", "-c", "from value import VALUE; assert VALUE == 2")],
        cwd=tmp_path,
    )
    assert success.completed and success.tests[0].outcome == "PASSED"
    failed = workflow.execute([], [("python", "-c", "raise SystemExit(1)")], cwd=tmp_path)
    assert not failed.completed and failed.tests[0].outcome == "FAILED"
