from pathlib import Path
from zipfile import ZipFile

from defusedxml.ElementTree import fromstring


def inspect_ooxml(path: Path) -> None:
    with ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > 10_000 or sum(entry.file_size for entry in entries) > 64 * 1024 * 1024:
            raise ValueError("OOXML archive exceeds size limits")
        for entry in entries:
            name = entry.filename.lower()
            if any(
                part in name
                for part in (
                    "vbaproject",
                    "externallinks/",
                    "embeddings/",
                    "pivottable",
                    "slicer",
                    "connections.xml",
                )
            ):
                raise ValueError("unsupported active or external OOXML feature")
            if name.endswith((".xml", ".rels")):
                root = fromstring(archive.read(entry))
                if name.endswith(".rels") and any(
                    node.get("TargetMode") == "External" for node in root
                ):
                    raise ValueError("external OOXML relationships are not allowed")
