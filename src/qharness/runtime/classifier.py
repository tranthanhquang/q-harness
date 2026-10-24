from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Classification:
    intent: str
    work_item_type: str
    risk: str
    workflow: str
    document_mode: str
    needs_confirmation: bool


def classify(request: str) -> Classification:
    normalized = request.lower()
    architectural = any(
        word in normalized for word in ("architecture", "across services", "migration")
    )
    feature = "feature" in normalized or "add " in normalized or "new " in normalized
    bug = any(word in normalized for word in ("fix", "bug", "error", "broken"))
    intent = "bugfix" if bug else "feature" if feature else "chore"
    high_risk = architectural or any(
        word in normalized for word in ("credential", "payment", "production")
    )
    return Classification(
        intent=intent,
        work_item_type=intent,
        risk="high" if high_risk else "low",
        workflow="standard",
        document_mode="full_sdd" if architectural else "none",
        needs_confirmation=high_risk,
    )
