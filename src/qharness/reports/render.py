from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any


def render_isolated(template: Path, context: dict[str, Any], contract: dict[str, Any]) -> Path:
    from qharness.config import Settings
    from qharness.infrastructure.sandbox import DockerRunner, SandboxSpec

    staging = Path(tempfile.mkdtemp(prefix="qh-report-"))
    inputs, output = staging / "inputs", staging / "output"
    inputs.mkdir()
    output.mkdir(mode=0o777)
    output.chmod(0o777)
    shutil.copyfile(template, inputs / template.name)
    (inputs / "request.json").write_text(
        json.dumps({"context": context, "contract": contract, "template": template.name}),
        encoding="utf-8",
    )
    package = Path(__file__).resolve().parents[1]
    spec = SandboxSpec(read_only=(inputs, package), writable=(output,), timeout_seconds=60)
    try:
        result = DockerRunner(Settings().sandbox_image).run(
            spec,
            "PYTHONPATH=/workspace python -m qharness.reports.render "
            "/workspace/inputs/request.json /workspace/output",
        )
        if result.returncode:
            raise ValueError("isolated report rendering failed")
        rendered = staging / f"report.{contract['output_format']}"
        shutil.move(output / rendered.name, rendered)
        shutil.rmtree(inputs)
        shutil.rmtree(output)
        return rendered
    except BaseException:
        shutil.rmtree(staging)
        raise


def main(request_path: Path, output_dir: Path) -> None:
    from qharness.reports.docx import render_docx
    from qharness.reports.ooxml import inspect_ooxml
    from qharness.reports.xlsx import render_named_workbook

    request = json.loads(request_path.read_text(encoding="utf-8"))
    context, contract = request["context"], request["contract"]
    template = request_path.parent / request["template"]
    inspect_ooxml(template)
    output = output_dir / f"report.{contract['output_format']}"
    if contract["output_format"] == "docx":
        fields = [
            field
            for section in contract["required_sections"]
            for field in section.get("required_fields", [])
        ]
        render_docx(template, output, context, [str(context[field]) for field in fields])
    else:
        render_named_workbook(template, output, context, contract["validation"])
    inspect_ooxml(output)


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
