"""Dependabot triage classifier.

Pure decision logic: consumes a JSON snapshot produced by
``dep_triage_collect.py`` and emits a classification plus a stated reason for
every open pull request. No network access and no side effects, so the whole
rule set is unit-testable against a recorded fixture.

Nothing here merges, approves, or marks a pull request ready. The safety net is
the ``main-protection`` ruleset -- one human approval plus four required status
checks, CodeQL on three languages among them. This module does the one thing
that gate cannot: notice that a pull request is *green* and still unsafe to
merge on its own.

What this used to be
--------------------

This tool was ~3,100 lines and 282 tests. It was cut to what is here. The
history is recorded rather than tidied away: a future reader needs to know
these controls existed and were removed deliberately, not that they were never
considered.

The whole evidence base is two near-misses in one batch. PR #450, one of four
``github/codeql-action/*`` refs: fully green, unsafe alone, because the
sub-actions must move in lockstep or CodeQL refuses to run. PR #443:
``@vitest/coverage-v8`` bumped to 5.x while ``vitest`` stayed on 4.x.
Coupled-family detection catches both; nothing else that was built caught
anything. Removed:

* **A release cooldown** (``rule_cooldown``, per-ecosystem day counts,
  release-age lookups against PyPI, npm, and git commit dates). It guarded no
  observed incident and introduced remediation latency, which then required a
  NIST SI-2 risk acceptance document to accept the latency the cooldown itself
  created. Do not reintroduce it without an incident it would have caught.
* **A 45-minute batch proof** and the ``merge-safe`` verdict it promoted
  candidates into (``promote``, ``CODE_MERGE_SAFE``, ``CODE_CONFLICT``,
  ``--proved`` / ``--conflicted``). Emitting a safety verdict was a blocking
  defect twice: a verdict could attach to a head the classifier never examined,
  and the proof's ``npm ci --legacy-peer-deps`` would not have caught #443
  anyway. No safety verdict means no false safety verdict.
* **A consolidation runner** (``dep_triage_consolidate.py``, 849 lines and 88
  tests, including ``git merge-tree`` verification of contested paths). The
  operator consolidates a coupled family by hand; commit ``ad67a34`` did.
* **All check evaluation** -- the failing, missing-required and
  required-not-passing rules, ``CheckRun``, ``required_checks``, and the ``gh
  pr checks`` call. A reviewer sees red checks on the PR itself. This took a
  defect class with it: ``excluded:no-checks`` existed only because "no failing
  checks" read as safe, and with no safety verdict there is nothing left to be
  vacuous about, so the zero-checks crash guard and the ``bucket`` state
  mapping went too.
* **Risk-register holds** (``rule_held_package``, deliberate holds, At-Risk
  tiers, ``dep_risk_register.py``). Register state belongs to the weekly
  ``dep_risk_audit.py``, which reads the register with its own parser.
* **Grouped-PR handling** (``rule_grouped``, ``GroupMember``, PR-body member
  parsing). It existed only to apply the register holds to a group's members;
  with those gone a grouped PR is simply a ``candidate``.
* **Major-version and policy-path observations** (``note_major``,
  ``note_policy_file``, ``rule_workflow_path``, ``Decision.notes``). Each
  restated something the reviewer reads off the diff they are already
  approving.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

# `gh` normalizes bot logins to `app/<slug>`; the GitHub API and webhooks use
# `<slug>[bot]`. Both are accepted because the collector reads whichever form
# its source returns, and an equality test against a single form made the whole
# tool a silent no-op -- every Dependabot PR excluded -- while its tests stayed
# green.
DEPENDABOT_AUTHORS: frozenset[str] = frozenset({"app/dependabot", "dependabot[bot]"})

# Classification codes. Consumers match on these exact strings.
CODE_NON_DEPENDABOT = "excluded:non-dependabot"
CODE_COUPLED = "coupled"
CODE_CANDIDATE = "candidate"


@dataclass(frozen=True)
class PRSnapshot:
    """Recorded state of one open pull request."""

    number: int
    title: str
    author: str
    files: tuple[str, ...]
    ecosystem: str
    directory: str
    package: str
    from_version: str
    to_version: str
    # Trailing because they carry defaults. `author_is_bot` is recorded for the
    # exclusion reason text only; the author *login* remains the decision,
    # because a non-Dependabot bot is also `is_bot: true`.
    author_is_bot: bool = False
    # Dependabot force-pushes its branches on rebase, so the report names the
    # commit each row was computed against. The operator consolidating a
    # coupled family by hand needs it to confirm nothing moved underneath them.
    head_sha: str = ""


@dataclass(frozen=True)
class Decision:
    """Classification outcome for one pull request."""

    number: int
    code: str
    reason: str
    family: str | None = None


def load_snapshot(path: Path) -> list[PRSnapshot]:
    """Read a snapshot JSON file into immutable PRSnapshot records."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [
        PRSnapshot(
            number=item["number"],
            title=item["title"],
            author=item["author"],
            files=tuple(item["files"]),
            ecosystem=item["ecosystem"],
            directory=item["directory"],
            package=item["package"],
            from_version=item["from_version"],
            to_version=item["to_version"],
            author_is_bot=bool(item.get("author_is_bot", False)),
            head_sha=item.get("head_sha", ""),
        )
        for item in raw["pull_requests"]
    ]


def rule_non_dependabot(pr: PRSnapshot) -> Decision | None:
    """R1: only Dependabot PRs are in scope.

    Keyed on author identity rather than title text, so Release Please and
    other bot PRs are excluded regardless of how they are titled. Membership is
    tested against every login form Dependabot is known to appear under,
    because an equality test against a single form excludes the whole queue
    whenever the collector's source reports the other one.
    """
    if pr.author not in DEPENDABOT_AUTHORS:
        accepted = ", ".join(repr(name) for name in sorted(DEPENDABOT_AUTHORS))
        bot_note = "a bot" if pr.author_is_bot else "not a bot"
        return Decision(
            number=pr.number,
            code=CODE_NON_DEPENDABOT,
            reason=(
                f"author is {pr.author!r} ({bot_note}), which is not one of the "
                f"accepted Dependabot logins: {accepted}"
            ),
        )
    return None


def family_key(pr: PRSnapshot) -> str | None:
    """Return a candidate update-family key for a PR, or None if not groupable.

    Two signals produce a candidate:

    * A GitHub Action whose package path has a sub-action segment
      (``github/codeql-action/init``) groups under its owner/repo. Those
      sub-actions must move in lockstep or CodeQL refuses to run.
    * An npm package groups with its scoped peers in the same directory. A
      shared scope alone is not coupling; validation in ``detect_families``
      ensures the group contains the unscoped root the scope is named for.
    """
    if pr.ecosystem == "github-actions" and pr.package.count("/") >= 2:
        owner, repo, *_ = pr.package.split("/")
        return f"{owner}/{repo}"
    if pr.ecosystem == "npm" and pr.package:
        root = pr.package.lstrip("@").split("/")[0]
        return f"npm:{pr.directory}:{root}"
    return None


def _has_unscoped_root(key: str, members: list[PRSnapshot]) -> bool:
    """True when one member is the unscoped package the scope is named for.

    A shared npm scope is not evidence of coupling: @types/react and
    @types/node release on independent cadences. The coupling that matters is a
    scoped package pinned to its unscoped namesake, as @vitest/coverage-v8 is
    to vitest, so a family requires that namesake to be under update as well.

    Known limitation, accepted deliberately: a scoped cluster with no unscoped
    root in the batch (@vitest/coverage-v8 alongside @vitest/ui, with no vitest
    PR) is not detected. It loses nothing, because either member alone is a
    singleton that no grouping rule would have caught either.
    """
    root = key.rsplit(":", 1)[-1]
    return any(member.package == root for member in members)


def detect_families(prs: list[PRSnapshot]) -> dict[int, str]:
    """Map PR number to family key, for families with more than one member.

    An npm candidate family is kept only when it contains the unscoped package
    its scope is named for. A shared scope alone is not coupling.
    """
    grouped: dict[str, list[PRSnapshot]] = {}
    for pr in prs:
        key = family_key(pr)
        if key is not None:
            grouped.setdefault(key, []).append(pr)

    families: dict[int, str] = {}
    for key, members in grouped.items():
        if len(members) < 2:
            continue
        if key.startswith("npm:") and not _has_unscoped_root(key, members):
            continue
        for pr in members:
            families[pr.number] = key
    return families


def rule_coupled(pr: PRSnapshot, families: dict[int, str]) -> Decision | None:
    """R5: no member of a multi-PR family is individually mergeable.

    Evaluated before check results, because the dangerous case is a *green*
    sibling: a PR can pass every check and still leave the repository
    inconsistent once merged alone.
    """
    key = families.get(pr.number)
    if key is None:
        return None
    return Decision(
        number=pr.number,
        code=CODE_COUPLED,
        reason=(
            f"member of update family {key!r}; members must land together, so "
            "this PR is not individually mergeable regardless of its checks"
        ),
        family=key,
    )


def classify(prs: list[PRSnapshot]) -> list[Decision]:
    """Classify every PR with the first matching rule.

    Rule order carries one obligation: the author exclusion runs first, so a
    non-Dependabot PR never reaches family logic. ``rule_coupled`` is evaluated
    against the batch as a whole, because coupling is a property of the set
    rather than of any single PR, and it is deliberately blind to check results
    -- the failure mode it exists for is a green sibling.

    ``candidate`` means "this tool found no objection", never "safe to merge".
    The verdict that meant that was removed; see the module docstring.
    """
    families = detect_families(prs)
    return [
        rule_non_dependabot(pr)
        or rule_coupled(pr, families)
        or Decision(
            number=pr.number,
            code=CODE_CANDIDATE,
            reason=(
                "no objection found; one human approval and the four required "
                "status checks remain what gates the merge"
            ),
        )
        for pr in prs
    ]


_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Candidates", (CODE_CANDIDATE,)),
    ("Coupled sets", (CODE_COUPLED,)),
    ("Excluded", (CODE_NON_DEPENDABOT,)),
)


def title_parse_line(prs: list[PRSnapshot]) -> str:
    """State how many Dependabot titles yielded a package name.

    Family detection is keyed entirely on the package ``parse_bump_title``
    recovers from the title. If Dependabot changes that format, every title
    parses to no package, every family disappears, and this tool reports a clean
    batch while its one control is inert -- the same class of silent no-op the
    author-login mismatch was. Stating the count puts it in front of the only
    reader who can notice. A grouped PR names no package and is expected here:
    a group lands as one commit, so it is a member of no family.
    """
    attempted = [p for p in prs if p.author in DEPENDABOT_AUTHORS]
    unparsed = sorted(p.number for p in attempted if not p.package)
    line = (
        f"- Bump titles: {len(attempted) - len(unparsed)} of {len(attempted)} "
        "Dependabot title(s) named a package."
    )
    if unparsed:
        numbers = ", ".join(f"#{n}" for n in unparsed)
        line += (
            f" Named none: {numbers} -- no family can be detected for these. "
            "Expected for a grouped update; a whole batch here means the title "
            "format moved and coupled detection is inert."
        )
    return line


def _inert_span(text: str) -> str:
    """Wrap ``text`` in a Markdown code span it cannot escape out of.

    A PR title is attacker-controlled: this repository is public, and any
    non-Dependabot PR's title -- reported verbatim in the "Excluded" section --
    is chosen by whoever opened it. Without this, backticks, a ``[link](...)``
    or an inline ``<img>``/``<details>`` tag pass straight through into an issue
    body an operator reads and acts on.

    Follows CommonMark's rule for code spans: a fence one backtick longer than
    the longest run inside the content (so the content cannot close the span
    early), padded with one space per side when the content starts or ends with
    a backtick. A PR title holds no newline, so a forged table *row* is
    impossible here -- only a forged inline element in one cell, which a code
    span defeats.
    """
    longest_run = 0
    current = 0
    for char in text:
        if char == "`":
            current += 1
            longest_run = max(longest_run, current)
        else:
            current = 0
    fence = "`" * (longest_run + 1)
    body = f" {text} " if text[:1] == "`" or text[-1:] == "`" else text
    return f"{fence}{body}{fence}"


def render_report(decisions: list[Decision], prs: list[PRSnapshot]) -> str:
    """Build the markdown triage report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    titles = {p.number: p.title for p in prs}
    heads = {p.number: p.head_sha for p in prs}

    def head_of(number: int) -> str:
        sha = heads.get(number, "")
        return f"`{sha[:10]}`" if sha else "(unknown)"

    lines = [
        f"# Dependabot Triage -- {now}",
        "",
        "Advisory only. Nothing here merges, approves, or marks a pull request "
        "ready; one human approval and four required status checks still gate "
        "every merge. This answers the one question that gate cannot: which of "
        "these are green and still unsafe to merge alone. `candidate` means no "
        "objection was found here, not that a PR is safe.",
        "",
        "Rows name the head commit each row was computed against. Dependabot "
        "force-pushes on rebase, so confirm the head still matches.",
        "",
        title_parse_line(prs),
        "",
    ]

    for heading, codes in _SECTIONS:
        selected = sorted(
            (d for d in decisions if d.code in codes), key=lambda d: d.number
        )
        lines += [f"## {heading}", ""]
        if not selected:
            lines += ["(none)", ""]
            continue
        if heading == "Coupled sets":
            by_family: dict[str, list[Decision]] = {}
            for d in selected:
                by_family.setdefault(d.family or "unknown", []).append(d)
            for family, members in sorted(by_family.items()):
                numbers = ", ".join(
                    f"#{d.number} ({head_of(d.number)})" for d in members
                )
                lines += [
                    f"### `{family}`",
                    "",
                    f"Members ({len(members)}): {numbers}. These must land "
                    "together; no member is individually mergeable.",
                    "",
                ]
            continue
        lines += [
            "| PR | Head | Code | Title | Reason |",
            "|----|------|------|-------|--------|",
        ]
        for d in selected:
            # The "Excluded" section prints every non-Dependabot PR's title
            # verbatim, and anyone can open one against this public repo, so the
            # title is untrusted: `_inert_span` neutralizes backticks, links and
            # raw HTML. The `|` escape runs first -- a code span protects inline
            # markup, not a cell's column boundary. `d.reason` gets the pipe
            # escape and no span: reasons come from this module's own rule set,
            # so only a version range ("^4.1.11") could hide a pipe in one.
            title = _inert_span(titles.get(d.number, "").replace("|", "\\|"))
            reason = d.reason.replace("|", "\\|")
            lines.append(
                f"| #{d.number} | {head_of(d.number)} | `{d.code}` | "
                f"{title} | {reason} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    """Classify a snapshot and write the markdown report."""
    parser = argparse.ArgumentParser(
        description="Classify open Dependabot PRs for Project Aura."
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        required=True,
        help="Path to the snapshot JSON from dep_triage_collect.",
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="Path to write the markdown report."
    )
    parser.add_argument(
        "--decisions",
        type=Path,
        default=None,
        help="Optional path to write decisions as JSON.",
    )
    args = parser.parse_args(argv)

    prs = load_snapshot(args.snapshot)
    decisions = classify(prs)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_report(decisions, prs), encoding="utf-8")
    if args.decisions:
        args.decisions.parent.mkdir(parents=True, exist_ok=True)
        args.decisions.write_text(
            json.dumps({"decisions": [d.__dict__ for d in decisions]}, indent=2),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
