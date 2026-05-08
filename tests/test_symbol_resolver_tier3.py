"""Tests for ADR-090 Phase 4c.1 Tier 3 LLM-driven symbol resolution."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

import pytest

from src.agents.ast_parser_agent import CodeEntity, CodeRelationship
from src.services.graph.edge_labels import EdgeLabel
from src.services.graph.symbol_resolver_tier3 import (
    PLAUSIBLE,
    UNVERIFIED,
    VERIFIED,
    Tier3LLMResolver,
    Tier3Stats,
    strip_python_comments_and_docstrings,
)

REPO_ID = "owner/repo"


# -- Helpers -----------------------------------------------------------


def _entity(
    name: str,
    kind: str,
    file_path: str,
    line: int = 1,
    parent_chain: tuple[str, ...] = (),
) -> CodeEntity:
    return CodeEntity(
        name=name,
        entity_type=kind,
        file_path=file_path,
        line_number=line,
        parent_chain=parent_chain,
        parent_entity=parent_chain[-1] if parent_chain else None,
    )


def _calls(
    source: str,
    target: str,
    file_path: str,
    parent_chain: tuple[str, ...] = (),
    line: int = 1,
) -> CodeRelationship:
    return CodeRelationship(
        source_name=source,
        source_parent_chain=parent_chain,
        target_name=target,
        relationship=EdgeLabel.CALLS.value,
        properties={"call_site_line": line},
        file_path=file_path,
    )


@dataclass
class _FakeRedaction:
    detections: list[Any]


class _FakeScanner:
    def __init__(self, has_secrets: bool = False, raises: bool = False):
        self.has_secrets = has_secrets
        self.raises = raises
        self.calls: list[tuple[str, str | None]] = []

    def scan_and_redact(self, content, file_path=None, organization_id=None):
        if self.raises:
            raise RuntimeError("scanner explosion")
        self.calls.append((content, file_path))
        return _FakeRedaction(detections=["mock-detection"] if self.has_secrets else [])


class _FakeReader:
    def __init__(self, payload: str):
        self.payload = payload
        self.calls = 0

    def read(self, file_path, line_number, context_lines):
        self.calls += 1
        return self.payload


def _make_bedrock(response_text: str):
    """Return an async-callable that records its inputs and returns text."""
    captured: dict[str, Any] = {"prompts": []}

    async def fake_generate(
        prompt,
        agent="X",
        system_prompt=None,
        max_tokens=None,
        operation=None,
        use_semantic_cache=True,
    ):
        captured["prompts"].append(prompt)
        captured["operation"] = operation
        captured["max_tokens"] = max_tokens
        return response_text

    fake_generate.captured = captured  # type: ignore[attr-defined]
    return fake_generate


def _make_failing_bedrock(exc: Exception):
    async def fake_generate(*args, **kwargs):
        raise exc

    return fake_generate


def _run(coro):
    return asyncio.run(coro)


# -- Tests -------------------------------------------------------------


class TestSoftDependency:
    def test_no_bedrock_means_no_op(self):
        resolver = Tier3LLMResolver(bedrock_generate=None)
        relationships = [_calls("run", "external", "x.py")]
        out, stats = _run(resolver.resolve([], relationships, REPO_ID))
        assert out == relationships
        assert stats.llm_unavailable == 1
        assert stats.still_unresolved == 1


class TestCandidateExtraction:
    def test_no_candidates_short_circuits(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        # No same-leaf entity in the index.
        entities = [_entity("App", "class", "x.py")]
        relationships = [_calls("run", "external_helper", "x.py")]
        out, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.no_candidates == 1
        assert stats.llm_invoked == 0
        assert out[0].target_fqn is None


class TestVerifiedResolution:
    def test_resolve_to_unique_candidate(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py", line=5),
            _entity("main", "function", "myapp/runner.py", line=1),
        ]
        relationships = [_calls("main", "helper", "myapp/runner.py")]
        out, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.llm_invoked == 1
        assert stats.llm_resolved_verified == 1
        edge = out[0]
        assert edge.relationship == EdgeLabel.CALLS_INFERRED.value
        assert edge.target_fqn is not None
        assert edge.properties["verification_status"] == VERIFIED
        assert edge.properties["resolution_method"] == "llm"

    def test_llm_returns_none_emits_unverified(self):
        bedrock = _make_bedrock('{"chosen_index": null}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [_calls("main", "helper", "myapp/runner.py")]
        out, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.llm_returned_none == 1
        assert stats.still_unresolved == 1
        assert out[0].relationship == EdgeLabel.CALLS_INFERRED.value
        assert out[0].properties["verification_status"] == UNVERIFIED
        assert out[0].target_fqn is None

    def test_invalid_index_treated_as_invalid(self):
        bedrock = _make_bedrock('{"chosen_index": 42}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [_calls("main", "helper", "myapp/runner.py")]
        out, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.llm_invalid_response == 1
        assert out[0].properties["verification_status"] == UNVERIFIED


class TestPromptShape:
    def test_prompt_includes_file_path_and_candidates(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py", line=12),
            _entity("main", "function", "myapp/runner.py"),
        ]
        relationships = [
            _calls("main", "helper", "myapp/runner.py", line=7),
        ]
        _run(resolver.resolve(entities, relationships, REPO_ID))
        prompt = bedrock.captured["prompts"][0]  # type: ignore[attr-defined]
        assert "myapp/runner.py" in prompt
        assert "Call expression: helper" in prompt
        assert "[0] function helper in myapp/utils.py at line 12" in prompt

    def test_prompt_includes_snippet_when_reader_provided(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        scanner = _FakeScanner(has_secrets=False)
        resolver = Tier3LLMResolver(bedrock_generate=bedrock, secrets_scanner=scanner)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        reader = _FakeReader("def main():\n    helper()  # call site\n")
        _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
                source_reader=reader,
            )
        )
        prompt = bedrock.captured["prompts"][0]  # type: ignore[attr-defined]
        # Comment was stripped before submission.
        assert "# call site" not in prompt
        assert "def main():" in prompt


class TestSecretPrescan:
    def test_secret_prescan_blocks_submission(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        scanner = _FakeScanner(has_secrets=True)
        resolver = Tier3LLMResolver(bedrock_generate=bedrock, secrets_scanner=scanner)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        reader = _FakeReader("AWS_ACCESS_KEY_ID = 'AKIAIOSFODNN7EXAMPLE'")
        out, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
                source_reader=reader,
            )
        )
        # LLM was never invoked.
        assert stats.llm_invoked == 0
        assert stats.secret_prescan_blocked == 1
        assert out[0].relationship == EdgeLabel.CALLS_INFERRED.value
        assert out[0].properties["verification_status"] == UNVERIFIED

    def test_scanner_exception_still_blocks(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        scanner = _FakeScanner(raises=True)
        resolver = Tier3LLMResolver(bedrock_generate=bedrock, secrets_scanner=scanner)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        reader = _FakeReader("function bodies here")
        _, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
                source_reader=reader,
            )
        )
        # Exception treated as a positive: don't send to LLM.
        assert stats.secret_prescan_blocked == 1
        assert stats.llm_invoked == 0

    def test_no_scanner_increments_unavailable(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock, secrets_scanner=None)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        reader = _FakeReader("def main(): helper()")
        _, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
                source_reader=reader,
            )
        )
        assert stats.secret_prescan_unavailable == 1
        # LLM was still invoked (no scanner doesn't block).
        assert stats.llm_invoked == 1


class TestBudget:
    def test_budget_exhaustion_emits_unverified(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock, call_budget=1)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
            _entity("other", "function", "myapp/x.py"),
        ]
        relationships = [
            _calls("main", "helper", "myapp/runner.py", line=1),
            _calls("main", "other", "myapp/runner.py", line=2),
        ]
        out, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.llm_invoked == 1
        assert stats.budget_exhausted == 1
        # Second relationship should be marked unverified.
        assert out[1].properties["verification_status"] == UNVERIFIED


class TestCache:
    def test_cache_hit_avoids_second_invocation(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        # Two identical relationships -> one LLM call, one cache hit.
        relationships = [
            _calls("main", "helper", "myapp/runner.py", line=5),
            _calls("main", "helper", "myapp/runner.py", line=5),
        ]
        _, stats = _run(resolver.resolve(entities, relationships, REPO_ID))
        assert stats.llm_invoked == 1
        assert stats.cache_hits == 1


class TestPromptInjectionDefenses:
    def test_strip_python_docstrings_and_comments(self):
        source = (
            "def f():\n"
            '    """Docstring.\n    Multi-line.\n    """\n'
            "    x = 1  # comment\n"
            "    return x\n"
        )
        cleaned = strip_python_comments_and_docstrings(source)
        assert '"""' not in cleaned
        assert "Docstring" not in cleaned
        assert "# comment" not in cleaned
        assert "return x" in cleaned

    def test_strip_javascript_comments(self):
        source = (
            "function helper() {\n"
            "  // single-line\n"
            "  /* multi\n     line */\n"
            "  return 1;\n"
            "}\n"
        )
        cleaned = strip_python_comments_and_docstrings(source)
        assert "// single-line" not in cleaned
        assert "/* multi" not in cleaned
        assert "return 1;" in cleaned

    def test_strip_collapses_blank_lines(self):
        source = "x = 1\n\n\n\n\ny = 2\n"
        cleaned = strip_python_comments_and_docstrings(source)
        assert cleaned.count("\n\n") == 1


class TestErrorHandling:
    def test_bedrock_failure_treated_as_invalid_response(self):
        bedrock = _make_failing_bedrock(RuntimeError("bedrock down"))
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        out, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
            )
        )
        # Failure increments the invalid-response counter and emits
        # an unverified edge rather than dropping the call.
        assert stats.llm_invalid_response == 1
        assert stats.llm_invoked == 1
        assert out[0].properties["verification_status"] == UNVERIFIED

    def test_llm_returns_markdown_wrapped_json(self):
        bedrock = _make_bedrock('```json\n{"chosen_index": 0}\n```')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        _, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
            )
        )
        # The fence-stripping path resolves as expected.
        assert stats.llm_resolved_verified == 1

    def test_llm_returns_garbage_with_embedded_json(self):
        bedrock = _make_bedrock('Sure! Here is my pick:\n"chosen_index": 0\nThanks.')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        entities = [
            _entity("helper", "function", "myapp/utils.py"),
            _entity("main", "function", "myapp/runner.py"),
        ]
        _, stats = _run(
            resolver.resolve(
                entities,
                [_calls("main", "helper", "myapp/runner.py")],
                REPO_ID,
            )
        )
        # Regex fallback finds the embedded value.
        assert stats.llm_resolved_verified == 1


class TestPassThrough:
    def test_inherits_relationships_unchanged(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        relationships = [
            CodeRelationship(
                source_name="X",
                source_parent_chain=(),
                target_name="Y",
                relationship=EdgeLabel.INHERITS.value,
                file_path="x.py",
            )
        ]
        out, stats = _run(resolver.resolve([], relationships, REPO_ID))
        assert out[0] is relationships[0]
        assert stats.llm_invoked == 0

    def test_already_resolved_edges_pass_through(self):
        bedrock = _make_bedrock('{"chosen_index": 0}')
        resolver = Tier3LLMResolver(bedrock_generate=bedrock)
        rel = CodeRelationship(
            source_name="main",
            source_parent_chain=(),
            target_name="helper",
            relationship=EdgeLabel.CALLS.value,
            file_path="x.py",
            target_fqn="python:repo:x:helper#function",
        )
        out, stats = _run(resolver.resolve([], [rel], REPO_ID))
        assert out[0] is rel
        assert stats.llm_invoked == 0


class TestStatsDefaults:
    def test_all_counters_default_zero(self):
        s = Tier3Stats()
        assert s.relationships_seen == 0
        assert s.candidates_considered == 0
        assert s.no_candidates == 0
        assert s.secret_prescan_blocked == 0
        assert s.secret_prescan_unavailable == 0
        assert s.llm_unavailable == 0
        assert s.llm_invoked == 0
        assert s.llm_resolved_verified == 0
        assert s.llm_resolved_plausible == 0
        assert s.llm_returned_none == 0
        assert s.llm_invalid_response == 0
        assert s.cache_hits == 0
        assert s.budget_exhausted == 0
        assert s.still_unresolved == 0
