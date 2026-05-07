"""Verify that documentation counts match filesystem reality.

Asserts the ADR / CloudFormation / buildspec counts referenced in CLAUDE.md
and docs/PROJECT_STATUS.md match what actually exists in the repo. Run as a
pre-commit hook or CI check to prevent the kind of doc drift identified in
the 2026-05-06 audit (87 vs 88 ADRs, 155 vs 168 CFN templates, 32 vs 38
buildspecs).

Exit codes:
    0  Counts match.
    1  Mismatch found (prints a delta table).
    2  Repo layout unexpected (script needs updating).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
PROJECT_STATUS_MD = REPO_ROOT / "docs" / "PROJECT_STATUS.md"
ADR_DIR = REPO_ROOT / "docs" / "architecture-decisions"
CFN_DIR = REPO_ROOT / "deploy" / "cloudformation"
BUILDSPEC_DIR = REPO_ROOT / "deploy" / "buildspecs"


@dataclass
class Check:
    name: str
    actual: int
    claimed: int | None
    source: str

    @property
    def ok(self) -> bool:
        return self.claimed is not None and self.actual == self.claimed


def count_adrs() -> int:
    return len(list(ADR_DIR.glob("ADR-*.md")))


def count_cfn_templates_top_level() -> int:
    return len(list(CFN_DIR.glob("*.yaml")))


def count_cfn_templates_total() -> int:
    """Count files with the CloudFormation template header.

    `find ... | xargs grep -l AWSTemplateFormatVersion` would be cheaper but
    we keep the logic in Python for portability with pre-commit on Windows.
    Helm/Kubernetes/config YAMLs that lack the header are excluded.
    """
    deploy_dir = REPO_ROOT / "deploy"
    count = 0
    for path in deploy_dir.rglob("*.yaml"):
        try:
            with path.open("r", encoding="utf-8") as fh:
                head = fh.read(4096)
        except (OSError, UnicodeDecodeError):
            continue
        if "AWSTemplateFormatVersion" in head:
            count += 1
    return count


def count_buildspecs() -> int:
    return len(list(BUILDSPEC_DIR.glob("*.yml")))


def find_claimed_count(path: Path, label_pattern: str) -> int | None:
    """Find the first integer that follows ``label_pattern`` in ``path``.

    The pattern matches a regex with one capturing group for the count.
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    match = re.search(label_pattern, text)
    if match is None:
        return None
    return int(match.group(1))


def main() -> int:
    if not ADR_DIR.is_dir() or not CFN_DIR.is_dir() or not BUILDSPEC_DIR.is_dir():
        print(
            "ERROR: expected directories not found; repo layout changed?",
            file=sys.stderr,
        )
        return 2

    adr_actual = count_adrs()
    cfn_top = count_cfn_templates_top_level()
    cfn_total = count_cfn_templates_total()
    bs_actual = count_buildspecs()

    checks: list[Check] = [
        Check(
            name="ADRs",
            actual=adr_actual,
            claimed=find_claimed_count(CLAUDE_MD, r"(\d+)\s+ADRs\s+\("),
            source="CLAUDE.md",
        ),
        Check(
            name="CloudFormation templates",
            actual=cfn_total,
            claimed=find_claimed_count(
                CLAUDE_MD,
                r"CloudFormation Templates:\*\*\s+(\d+)\s+templates",
            ),
            source="CLAUDE.md",
        ),
        Check(
            name="Buildspecs",
            actual=bs_actual,
            claimed=find_claimed_count(CLAUDE_MD, r"(\d+)\s+buildspecs\s+managing"),
            source="CLAUDE.md",
        ),
        Check(
            name="ADRs (PROJECT_STATUS)",
            actual=adr_actual,
            claimed=find_claimed_count(PROJECT_STATUS_MD, r"(\d+)\s+ADRs\s+\("),
            source="docs/PROJECT_STATUS.md",
        ),
        Check(
            name="CloudFormation templates (PROJECT_STATUS)",
            actual=cfn_total,
            claimed=find_claimed_count(
                PROJECT_STATUS_MD,
                r"\|\s*\*\*CloudFormation Templates\*\*\s*\|\s*(\d+)\s+templates",
            ),
            source="docs/PROJECT_STATUS.md",
        ),
        Check(
            name="Buildspecs (PROJECT_STATUS)",
            actual=bs_actual,
            claimed=find_claimed_count(PROJECT_STATUS_MD, r"(\d+)\s+buildspec\s+files"),
            source="docs/PROJECT_STATUS.md",
        ),
    ]

    failures = [c for c in checks if not c.ok]

    print(f"Top-level CFN templates in deploy/cloudformation/: {cfn_top}")
    print(f"Total .yaml under deploy/ (incl. nested):         {cfn_total}")
    print(f"ADRs in docs/architecture-decisions/:              {adr_actual}")
    print(f"Buildspecs in deploy/buildspecs/:                  {bs_actual}")
    print()

    if not failures:
        print("OK: documentation counts match filesystem.")
        return 0

    print("MISMATCH between documentation claims and filesystem:")
    print()
    print(f"{'Source':<30} {'Metric':<45} {'Claimed':>8} {'Actual':>8}")
    print("-" * 95)
    for c in failures:
        claimed = c.claimed if c.claimed is not None else "<missing>"
        print(f"{c.source:<30} {c.name:<45} {str(claimed):>8} {c.actual:>8}")
    print()
    print(
        "Update the relevant docs (or the regex in this script if the format changed)."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
