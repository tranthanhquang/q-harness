from pathlib import Path

import pytest

from qharness.security.paths import PathViolation, contained_path


@pytest.mark.security
def test_project_root_does_not_authorize_sibling(tmp_path: Path) -> None:
    project_a = tmp_path / "a"
    project_b = tmp_path / "b"
    project_a.mkdir()
    project_b.mkdir()
    secret = project_b / "secret.txt"
    secret.write_text("never expose", encoding="utf-8")
    with pytest.raises(PathViolation) as error:
        contained_path(project_a, secret)
    assert "never expose" not in str(error.value)
