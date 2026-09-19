"""Collect the Dependabot triage snapshot.

This is the only module in the triage pipeline that performs network access.
It gathers pull request metadata, check runs, release ages and risk-register
tiers into a single JSON document, so that ``dep_triage.py`` can stay pure and
testable against recorded fixtures.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER_PATH = REPO_ROOT / "docs/security/DEPENDENCY_RISK_REGISTER.md"

_BUMP = re.compile(
    r"\b(?:bump|update)\s+(?P<pkg>\S+?)(?:\s+requirement)?\s+"
    r"from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)"
)

_DETAILS_BLOCK = re.compile(r"<details>.*?</details>", re.DOTALL | re.IGNORECASE)
_DETAILS_OPEN = re.compile(r"<details>", re.IGNORECASE)
_ADVISORY = re.compile(r"(GHSA-[0-9a-z-]+|CVE-\d{4}-\d+)", re.IGNORECASE)


def parse_bump_title(title: str) -> tuple[str, str, str]:
    """Extract (package, from_version, to_version) from a Dependabot title.

    Returns three empty strings when the title is not a version bump, which is
    how non-Dependabot PRs such as release PRs fall through harmlessly.
    """
    match = _BUMP.search(title or "")
    if not match:
        return ("", "", "")
    return (match.group("pkg"), match.group("old"), match.group("new"))


def infer_ecosystem(files: list[str]) -> str:
    """Infer the package ecosystem from the paths a PR touches."""
    for path in files:
        if path.startswith(".github/workflows/"):
            return "github-actions"
        if path.endswith(("package.json", "package-lock.json")):
            return "npm"
        if "requirements" in path and path.endswith(".txt"):
            return "pip"
        if path.endswith("pyproject.toml"):
            return "pip"
        if "Dockerfile" in path:
            return "docker"
    return "unknown"


def infer_directory(files: list[str]) -> str:
    """Infer the manifest directory for npm PRs; '/' for everything else."""
    for path in files:
        if path.endswith(("package.json", "package-lock.json")):
            parent = str(Path(path).parent)
            return "/" if parent == "." else f"/{parent}"
    return "/"


def is_security_advisory(body: str | None) -> bool:
    """True when Dependabot itself cites a GHSA or CVE for this update.

    Dependabot security updates name the advisory they fix in their own
    preamble. Ordinary version bumps embed upstream release notes inside
    <details> blocks, and those routinely mention CVEs fixed in earlier
    releases within the range -- text that says nothing about whether *this*
    update is a security fix. Matching the whole body therefore reads an
    unrelated changelog as an advisory.

    That matters because the flag bypasses both the cooldown and the
    major-version hold. The two error directions are not symmetric: a missed
    advisory only means the patch queues normally, while a false positive
    strips both protections from an ordinary bump. So <details> content is
    excluded and detection errs toward not-security.
    """
    text = _DETAILS_BLOCK.sub("", body or "")
    # An unclosed <details> would otherwise leave its whole tail in scope.
    text = _DETAILS_OPEN.split(text, maxsplit=1)[0]
    return bool(_ADVISORY.search(text))


def _risk_tiers(register: Path) -> dict[str, str]:
    """Map package name to tier by reading the risk register's tables."""
    tiers: dict[str, str] = {}
    if not register.exists():
        return tiers
    for line in register.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        name = cells[0].strip("`")
        tier = cells[2].strip("*").lower()
        if tier in {"at-risk", "replace-now", "watch", "healthy"}:
            tiers[name] = tier
    return tiers


def build_snapshot(
    prs: list[dict],
    checks_by_pr: dict[int, list[dict]],
    required_checks: list[str],
    release_ages: dict[str, float],
    risk_tiers: dict[str, str],
) -> dict:
    """Assemble the snapshot document consumed by dep_triage.load_snapshot."""
    out: list[dict] = []
    for pr in prs:
        files = list(pr.get("files", []))
        package, old, new = parse_bump_title(pr.get("title", ""))
        out.append(
            {
                "number": pr["number"],
                "title": pr.get("title", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "files": files,
                "checks": checks_by_pr.get(pr["number"], []),
                "required_checks": required_checks,
                "ecosystem": infer_ecosystem(files),
                "directory": infer_directory(files),
                "package": package,
                "from_version": old,
                "to_version": new,
                "release_age_days": release_ages.get(package),
                "risk_tier": risk_tiers.get(package, "unknown"),
                "security_advisory": bool(pr.get("security_advisory", False)),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_requests": out,
    }


def _gh_json(args: list[str]) -> object:
    """Run a gh command and parse its JSON output."""
    result = subprocess.run(["gh", *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def main(argv: list[str] | None = None) -> int:
    """Collect the snapshot and write it to --output."""
    parser = argparse.ArgumentParser(
        description="Collect the Dependabot triage snapshot."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the snapshot JSON.",
    )
    parser.add_argument("--repo", required=True, help="owner/name of the repository.")
    parser.add_argument(
        "--required-check",
        action="append",
        default=[],
        help="Name of a required status check; repeatable.",
    )
    args = parser.parse_args(argv)

    listing = _gh_json(
        [
            "pr",
            "list",
            "--repo",
            args.repo,
            "--state",
            "open",
            "--limit",
            "100",
            "--json",
            "number,title,author,files,body",
        ]
    )
    prs = [
        {
            "number": item["number"],
            "title": item["title"],
            "author": item["author"],
            "files": [f["path"] for f in item.get("files", [])],
            "security_advisory": is_security_advisory(item.get("body")),
        }
        for item in listing  # type: ignore[union-attr]
    ]

    checks_by_pr: dict[int, list[dict]] = {}
    for pr in prs:
        runs = _gh_json(
            [
                "pr",
                "checks",
                str(pr["number"]),
                "--repo",
                args.repo,
                "--json",
                "name,state,description",
            ]
        )
        checks_by_pr[pr["number"]] = [
            {
                "name": r["name"],
                "status": "completed",
                "conclusion": (
                    "success"
                    if r["state"] == "SUCCESS"
                    else (
                        "failure"
                        if r["state"] == "FAILURE"
                        else "skipped" if r["state"] == "SKIPPED" else None
                    )
                ),
                "failing_log_excerpt": r.get("description", ""),
            }
            for r in runs  # type: ignore[union-attr]
        ]

    snapshot = build_snapshot(
        prs=prs,
        checks_by_pr=checks_by_pr,
        required_checks=args.required_check,
        release_ages={},
        risk_tiers=_risk_tiers(REGISTER_PATH),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
