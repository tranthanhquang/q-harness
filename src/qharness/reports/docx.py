from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring
from docxtpl import DocxTemplate
from jinja2 import StrictUndefined
from jinja2.sandbox import SandboxedEnvironment


class ReportValidationError(ValueError):
    pass


def _document_text(path: Path) -> str:
    parts: list[str] = []
    with ZipFile(path) as archive:
        for name in archive.namelist():
            if name == "word/document.xml" or (
                name.startswith(("word/header", "word/footer")) and name.endswith(".xml")
            ):
                root = fromstring(archive.read(name))
                parts.extend(
                    "".join(node.itertext())
                    for node in root.iter(
                        "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                    )
                )
    return "\n".join(parts)


def render_docx(
    template: Path, output: Path, context: dict[str, object], required_text: list[str]
) -> None:
    environment = SandboxedEnvironment(undefined=StrictUndefined, autoescape=True)
    document = DocxTemplate(template)
    try:
        document.render(context, jinja_env=environment, autoescape=True)
        document.save(output)
    except Exception as exc:
        raise ReportValidationError("DOCX rendering failed") from exc
    try:
        text = _document_text(output)
    except Exception as exc:
        raise ReportValidationError("DOCX cannot be reopened") from exc
    if "{{" in text or "{%" in text or any(required not in text for required in required_text):
        raise ReportValidationError("DOCX validation failed")
