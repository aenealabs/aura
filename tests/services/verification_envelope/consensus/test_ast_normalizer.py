"""Tests for ASTNormalizer (ADR-085 Phase 1)."""

from __future__ import annotations

from src.services.verification_envelope.consensus.ast_normalizer import ASTNormalizer


def test_identical_source_yields_identical_canonical_hash() -> None:
    src = "def add(a, b):\n    return a + b\n"
    a = ASTNormalizer().normalize(src)
    b = ASTNormalizer().normalize(src)
    assert a.parse_succeeded and b.parse_succeeded
    assert a.canonical_hash == b.canonical_hash
    assert a.source_hash == b.source_hash


def test_variable_renaming_produces_same_canonical_hash() -> None:
    """Two functions that differ only in argument names normalise identically."""
    src_a = "def add(a, b):\n    result = a + b\n    return result\n"
    src_b = "def add(x, y):\n    total = x + y\n    return total\n"
    a = ASTNormalizer().normalize(src_a)
    b = ASTNormalizer().normalize(src_b)
    assert a.canonical_hash == b.canonical_hash
    # And the source hashes differ (sanity).
    assert a.source_hash != b.source_hash


def test_docstring_stripping() -> None:
    src_with = '''def f(a):\n    """doc"""\n    return a\n'''
    src_without = "def f(a):\n    return a\n"
    a = ASTNormalizer(strip_docstrings=True).normalize(src_with)
    b = ASTNormalizer(strip_docstrings=True).normalize(src_without)
    assert a.canonical_hash == b.canonical_hash


def test_docstring_kept_when_disabled() -> None:
    src_with = '''def f(a):\n    """doc"""\n    return a\n'''
    src_without = "def f(a):\n    return a\n"
    a = ASTNormalizer(strip_docstrings=False).normalize(src_with)
    b = ASTNormalizer(strip_docstrings=False).normalize(src_without)
    assert a.canonical_hash != b.canonical_hash


def test_import_sorting_handles_unsorted_input() -> None:
    src_a = "import os\nimport sys\n\ndef f(): pass\n"
    src_b = "import sys\nimport os\n\ndef f(): pass\n"
    a = ASTNormalizer().normalize(src_a)
    b = ASTNormalizer().normalize(src_b)
    assert a.canonical_hash == b.canonical_hash


def test_imports_inside_function_not_reordered() -> None:
    """Function-body imports must stay in source order (could have side effects)."""
    src_a = "def f():\n    import os\n    import sys\n    return os\n"
    src_b = "def f():\n    import sys\n    import os\n    return os\n"
    a = ASTNormalizer().normalize(src_a)
    b = ASTNormalizer().normalize(src_b)
    # Different — function-body order is preserved.
    assert a.canonical_hash != b.canonical_hash


def test_module_level_names_not_renamed() -> None:
    """Module-level variables shouldn't be renamed (could be public API)."""
    src_a = "FOO = 1\nBAR = 2\n"
    src_b = "X = 1\nY = 2\n"
    a = ASTNormalizer().normalize(src_a)
    b = ASTNormalizer().normalize(src_b)
    # FOO/BAR vs X/Y stay distinct because module-level names are preserved.
    assert a.canonical_hash != b.canonical_hash


def test_syntactically_different_implementations_produce_different_hashes() -> None:
    src_a = "def f(xs):\n    return [x * 2 for x in xs]\n"
    src_b = (
        "def f(xs):\n"
        "    out = []\n"
        "    for x in xs:\n"
        "        out.append(x * 2)\n"
        "    return out\n"
    )
    a = ASTNormalizer().normalize(src_a)
    b = ASTNormalizer().normalize(src_b)
    # Different AST shapes → different canonical hashes
    # (the embedding fallback is what catches this case as equivalent).
    assert a.canonical_hash != b.canonical_hash


def test_parse_failure_records_error() -> None:
    src = "def broken(:\n    return 1\n"
    a = ASTNormalizer().normalize(src)
    assert a.parse_succeeded is False
    assert a.parse_error
    assert a.canonical_hash == ""


def test_node_count_increases_with_more_code() -> None:
    small = ASTNormalizer().normalize("x = 1\n")
    big = ASTNormalizer().normalize("a = 1\nb = 2\nc = a + b\nd = c * 2\n")
    assert big.node_count > small.node_count
