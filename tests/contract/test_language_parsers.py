from qharness.knowledge.parsers import extract_symbols


def test_python_and_typescript_symbols() -> None:
    python_symbols = extract_symbols(
        "service.py", "class Service:\n    def run(self):\n        pass\n"
    )
    type_symbols = extract_symbols("service.ts", "export function healthCheck() { return true; }\n")
    assert {symbol.name for symbol in python_symbols} >= {"Service", "run"}
    assert {symbol.name for symbol in type_symbols} >= {"healthCheck"}


def test_unknown_language_uses_lexical_only_fallback() -> None:
    assert extract_symbols("README.md", "# Heading") == []
