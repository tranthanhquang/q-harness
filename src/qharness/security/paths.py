from __future__ import annotations

from pathlib import Path


class PathViolation(ValueError):
    pass


def canonical_directory(path: Path) -> Path:
    try:
        result = path.expanduser().resolve(strict=True)
    except OSError as exc:
        raise PathViolation("directory is unavailable") from exc
    if not result.is_dir():
        raise PathViolation("path is not a directory")
    return result


def contained_path(root: Path, candidate: Path) -> Path:
    canonical_root = canonical_directory(root)
    try:
        canonical_candidate = candidate.expanduser().resolve(strict=True)
        canonical_candidate.relative_to(canonical_root)
    except (OSError, ValueError) as exc:
        raise PathViolation("path is outside the registered repository") from exc
    return canonical_candidate


def find_project_file(start: Path) -> Path | None:
    current = canonical_directory(start)
    for candidate_root in (current, *current.parents):
        candidate = candidate_root / ".qharness" / "project.yaml"
        if candidate.is_file():
            return candidate
    return None
