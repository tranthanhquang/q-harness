from pathlib import Path

import pytest

from qharness.infrastructure.database import Database
from qharness.projects.service import ProjectService
from qharness.skills.registry import InvalidSkill, SkillRegistry


def make_skill(root: Path) -> Path:
    root.mkdir(parents=True)
    (root / "SKILL.md").write_text(
        "---\nname: inspect\nversion: 1.0.0\nlicense: MIT\n"
        "source: local\npermissions: [read]\n---\n"
        "# Inspect\nRead [reference](assets/reference.txt).\n",
        encoding="utf-8",
    )
    (root / "assets").mkdir()
    (root / "assets/reference.txt").write_text("reference", encoding="utf-8")
    (root / "scripts").mkdir()
    (root / "scripts/unsafe.sh").write_text("exit 99\n", encoding="utf-8")
    return root


def test_skill_provenance_drift_and_project_isolation(database: Database, tmp_path: Path) -> None:
    projects = ProjectService(database)
    project = projects.create("Skills", tmp_path)
    other = projects.create("Other", tmp_path / "other")
    allowed = tmp_path / ".agents/skills"
    skill = make_skill(allowed / "inspect")
    registry = SkillRegistry(database, [allowed])
    assert registry.discover() == [skill]
    record = registry.verify(skill, project.id)
    assert record.status == "VERIFIED"
    assert record.license == "MIT"
    assert set(record.file_checksums) == {"SKILL.md", "assets/reference.txt", "scripts/unsafe.sh"}
    assert registry.list(other.id) == []
    assert registry.list(project.id)[0].status == "VERIFIED"
    (skill / "assets/reference.txt").write_text("changed", encoding="utf-8")
    assert registry.list(project.id)[0].status == "STALE"
    with pytest.raises(InvalidSkill, match="version"):
        registry.verify(skill, project.id)


@pytest.mark.parametrize("field", ["version", "license", "source", "permissions"])
def test_skill_requires_provenance(database: Database, tmp_path: Path, field: str) -> None:
    skill = make_skill(tmp_path / "inspect")
    manifest = skill / "SKILL.md"
    manifest.write_text(
        "\n".join(
            line for line in manifest.read_text().splitlines() if not line.startswith(field + ":")
        )
    )
    with pytest.raises(InvalidSkill):
        SkillRegistry(database, [tmp_path]).verify(skill)


def test_skill_never_executes_scripts_and_rejects_escape(
    database: Database,
    tmp_path: Path,
) -> None:
    skill = make_skill(tmp_path / "inspect")
    marker = tmp_path / "executed"
    (skill / "scripts/unsafe.sh").write_text(f"touch '{marker}'\n")
    registry = SkillRegistry(database, [tmp_path])
    registry.verify(skill)
    assert not marker.exists()
    outside = tmp_path.parent / "outside-skill"
    with pytest.raises(InvalidSkill, match="root"):
        registry.verify(outside)
    (skill / "assets/escape").symlink_to(tmp_path)
    with pytest.raises(InvalidSkill, match="symlink"):
        registry.verify(skill)


def test_skill_rejects_executable_permissions(database: Database, tmp_path: Path) -> None:
    skill = make_skill(tmp_path / "inspect")
    manifest = skill / "SKILL.md"
    manifest.write_text(manifest.read_text().replace("[read]", "[shell, network]"))
    with pytest.raises(InvalidSkill, match="permission"):
        SkillRegistry(database, [tmp_path]).verify(skill)
