from qharness.security.redaction import REDACTED, redact


def test_redacts_nested_secret_values_without_mutating_input() -> None:
    value = {
        "authorization": "Bearer secret",
        "nested": [{"api_key": "sk-secret", "safe": "visible"}],
    }
    result = redact(value)
    assert result == {
        "authorization": REDACTED,
        "nested": [{"api_key": REDACTED, "safe": "visible"}],
    }
    assert value["authorization"] == "Bearer secret"


def test_redacts_secret_patterns_inside_strings() -> None:
    assert "sk-live" not in redact("failed with OPENAI_API_KEY=sk-live")
