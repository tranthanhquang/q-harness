import os
from pathlib import Path

import pytest

from qharness.knowledge.discovery import discover_files


def test_discovery_respects_denylist_binary_size_and_gitignore(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "keep.py").write_text("print('ok')\n", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=value\n", encoding="utf-8")
    (tmp_path / "binary.bin").write_bytes(b"\x00\x01")
    (tmp_path / "large.txt").write_text("x" * 200, encoding="utf-8")
    (tmp_path / "ignored.txt").write_text("ignored", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    assert discover_files(tmp_path, max_bytes=100) == [Path("src/keep.py")]


def test_discovery_does_not_follow_symlinks(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "secret.py").write_text("secret = True", encoding="utf-8")
    (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    assert discover_files(tmp_path) == []


def test_metadata_discovery_reuses_unchanged_text_and_checks_new_or_changed_files(
    tmp_path: Path, monkeypatch
) -> None:
    from qharness.knowledge.discovery import discover_file_metadata

    source = tmp_path / "source.txt"
    source.write_text("trusted text")
    previous = discover_file_metadata(tmp_path)
    opened = []
    original = Path.open

    def tracked(path, *args, **kwargs):
        opened.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", tracked)
    assert discover_file_metadata(tmp_path, known_files=previous) == previous
    assert opened == []
    (tmp_path / "new.txt").write_text("new text")
    source.write_bytes(b"\x00changed")
    opened.clear()
    current = discover_file_metadata(tmp_path, known_files=previous)
    assert set(current) == {"new.txt"}
    assert source in opened and tmp_path / "new.txt" in opened


def test_metadata_discovery_rejects_a_replaced_parent_directory(tmp_path: Path) -> None:
    from qharness.knowledge.discovery import discover_file_metadata

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "value.txt").write_text("inside")
    known = discover_file_metadata(tmp_path)
    nested.rename(tmp_path / "original")
    nested.symlink_to(tmp_path / "original", target_is_directory=True)
    assert "nested/value.txt" not in discover_file_metadata(tmp_path, known_files=known)


def test_metadata_discovery_rejects_parent_swap_before_open(tmp_path: Path, monkeypatch) -> None:
    from qharness.knowledge.discovery import discover_file_metadata

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "value.txt").write_text("inside")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir()
    (outside / "value.txt").write_text("secret")
    known = discover_file_metadata(tmp_path)
    original_open = os.open

    def swap(path, flags, *args, **kwargs):
        if Path(path) == nested:
            nested.rename(tmp_path / "preserved")
            nested.symlink_to(outside, target_is_directory=True)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", swap)
    with pytest.raises(OSError):
        discover_file_metadata(tmp_path, known_files=known)
