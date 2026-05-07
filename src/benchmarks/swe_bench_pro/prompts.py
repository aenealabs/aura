"""
Project Aura - SWE-Bench Pro Prompt Templates.

The prompt is intentionally simple: SWE-Bench tests bug-fixing
ability, so we ask the model to produce a unified diff that resolves
the issue. The system prompt establishes the constraint that output
must be a valid unified diff and nothing else; the user prompt
delivers the issue + repo context.

Aura's security-tuned prompts (see ``vulnerability_scanner/analysis``)
are NOT used here. They overweight CWE detection and underweight
general-purpose bug fixing — using them would produce a misleading
SWE-Bench score that isn't representative of either.

Author: Project Aura Team
Created: 2026-05-07
"""

from __future__ import annotations

from .contracts import SWEBenchTask


_SYSTEM_PROMPT = """\
You are an expert software engineer. You will receive a GitHub issue
report and the current state of the affected repository. Your task is
to produce a minimal unified diff that resolves the issue.

OUTPUT REQUIREMENTS:
- Respond with ONLY the unified diff. No prose, no markdown fences,
  no explanation, no commentary.
- The diff must apply cleanly to the repository at its base commit.
- Prefer the smallest change that resolves the issue. Do not refactor
  unrelated code.
- Do not modify test files unless the issue explicitly requires it.

If you cannot produce a confident fix from the information given,
respond with an empty diff (no output at all). Do not guess.
"""


def system_prompt() -> str:
    return _SYSTEM_PROMPT


def build_user_prompt(task: SWEBenchTask, repo_context: str = "") -> str:
    """Construct the user prompt for a SWE-Bench Pro task.

    Args:
        task: The task to solve.
        repo_context: Optional snippet of repository context the
            adapter has retrieved (e.g. via Aura's
            ContextRetrievalService). May be empty for prompt-only
            runs that rely on the model's training-time knowledge of
            the repo.
    """
    parts: list[str] = [
        "<task>",
        f"<repo>{_escape(task.repo)}</repo>",
        f"<base_commit>{_escape(task.base_commit)}</base_commit>",
        f"<instance_id>{_escape(task.instance_id)}</instance_id>",
        "<problem_statement>",
        _escape(task.problem_statement),
        "</problem_statement>",
    ]
    if task.hints_text:
        parts.extend(
            [
                "<hints>",
                _escape(task.hints_text),
                "</hints>",
            ]
        )
    if repo_context:
        parts.extend(
            [
                "<repo_context>",
                _escape(repo_context),
                "</repo_context>",
            ]
        )
    parts.append("</task>")
    parts.append("")
    parts.append(
        "Produce the unified diff that resolves this issue, "
        "or no output if you cannot."
    )
    return "\n".join(parts)


def _escape(text: str) -> str:
    """Escape angle brackets to prevent finding text from breaking
    out of the XML wrapper. Same defence-in-depth used elsewhere in
    Aura's prompt construction (see ADR-049 advanced_prompts)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
