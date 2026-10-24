from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ScopeEscalation(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class ApprovalScope:
    roots: tuple[Path, ...]
    commands: tuple[str, ...]
    network: bool = False
    tools: tuple[str, ...] = ("read", "write", "search", "test")

    def require_tool(self, tool: str) -> None:
        if tool not in self.tools:
            raise ScopeEscalation("tool exceeds approved scope")

    def require_path(self, path: Path) -> Path:
        candidate = path.expanduser().resolve(strict=False)
        for root in self.roots:
            if root.expanduser().absolute() != root.expanduser().resolve(strict=True):
                raise ScopeEscalation("approved root changed through a symlink")
            try:
                candidate.relative_to(root.expanduser().resolve(strict=True))
                from qharness.knowledge.discovery import DENIED_NAMES, DENIED_PARTS

                relative = candidate.relative_to(root)
                if (
                    DENIED_PARTS.intersection(relative.parts)
                    or candidate.name in DENIED_NAMES
                    or candidate.name.startswith(".env.")
                    or candidate.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}
                ):
                    raise ScopeEscalation("credential or generated path is denied")
                return candidate
            except ValueError:
                continue
        raise ScopeEscalation("path exceeds approved scope")

    def require_command(self, command: tuple[str, ...]) -> None:
        if not command or command[0] not in self.commands:
            raise ScopeEscalation("command exceeds approved scope")

    def require_network(self) -> None:
        if not self.network:
            raise ScopeEscalation("network access is not approved")
