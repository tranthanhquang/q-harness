from pathlib import Path

import pytest

from qharness.infrastructure.artifacts import ArtifactStore


def test_artifacts_never_overwrite_or_follow_symlink_parents(tmp_path: Path) -> None:
    source = tmp_path / "rendered"
    source.write_bytes(b"verified report")
    root = tmp_path / "artifacts"
    store = ArtifactStore(root)
    published = store.publish(source, "project/report.docx")
    source.write_bytes(b"different")
    with pytest.raises(FileExistsError):
        store.publish(source, "project/report.docx")
    assert published.path.read_bytes() == b"verified report"
    with pytest.raises(ValueError):
        store.publish(source, "../escape")
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    with pytest.raises((ValueError, OSError)):
        store.publish(source, "link/escape")
    assert not (outside / "escape").exists()
