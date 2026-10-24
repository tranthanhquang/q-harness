from qharness.runtime.classifier import classify


def test_classifier_uses_full_sdd_only_for_large_or_architectural_work() -> None:
    small = classify("fix typo in README")
    large = classify("design architecture for a new payment feature across services")
    assert small.document_mode == "none" and not small.needs_confirmation
    assert large.document_mode == "full_sdd" and large.needs_confirmation
