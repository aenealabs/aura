#!/usr/bin/env python3
"""Recurring dependency risk audit for Project Aura.

Runs three checks against the project's dependency surface and emits
a markdown report:

1. ``pip-audit`` against every ``requirements*.txt`` for Python CVEs.
2. ``npm audit --json`` against ``frontend/`` for npm CVEs.
3. Maintainer-staleness check against the Watch / At-Risk tiers in
   ``docs/security/DEPENDENCY_RISK_REGISTER.md``: looks up the
   "last release date" via ``pip show`` / ``npm view`` metadata so
   no external API call is needed.

The script is intentionally stdlib-plus-CLI-tools only:

- ``pip-audit`` -- PyPA official tool; installed via pip.
- ``npm`` -- already on the runner via Node setup.
- No deps.dev / OSV / Snyk API calls; the register IS the source of
  truth for which deps need staleness tracking, so we only check the
  tracked subset.

Exit codes:

- 0: audit completed; report written. Critical findings are surfaced
     in the report but do not fail the run -- the workflow handles
     posting the report so reviewers can triage.
- 1: audit infrastructure failure (missing tools, parse error). Fix
     the script.

Usage::

    python -m scripts.security.dep_risk_audit \\
        --output reports/dep-audit-$(date +%Y-%m-%d).md
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_REQUIREMENTS = sorted(REPO_ROOT.glob("requirements*.txt")) + sorted(
    REPO_ROOT.glob("deploy/docker/**/requirements*.txt")
)
FRONTEND_DIR = REPO_ROOT / "frontend"
REGISTER_PATH = REPO_ROOT / "docs" / "security" / "DEPENDENCY_RISK_REGISTER.md"


def _run(
    cmd: list[str],
    cwd: Path | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Wrapper around subprocess.run with sane defaults for audit usage."""
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        check=check,
    )


def pip_audit(req_file: Path) -> dict:
    """Run pip-audit against one requirements file. Returns:

    - ``ok`` True if the audit ran (vulnerabilities may still be present)
    - ``vulnerabilities``: list of dicts (name, version, cve, fix_versions)
    - ``error``: str on infrastructure failure
    """
    proc = _run(["pip-audit", "--requirement", str(req_file), "--format", "json"])
    if proc.returncode not in (0, 1):
        # 0 = clean, 1 = vulns found, anything else = pip-audit failure
        return {
            "ok": False,
            "vulnerabilities": [],
            "error": (
                f"pip-audit exited {proc.returncode} for "
                f"{str(req_file.relative_to(REPO_ROOT))}: {proc.stderr.strip() or proc.stdout.strip()}"
            ),
        }
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "vulnerabilities": [],
            "error": f"pip-audit produced invalid JSON for {str(req_file.relative_to(REPO_ROOT))}: {e}",
        }
    vulns: list[dict] = []
    for entry in payload.get("dependencies", []):
        for vuln in entry.get("vulns", []) or []:
            vulns.append(
                {
                    "name": entry.get("name"),
                    "version": entry.get("version"),
                    "id": vuln.get("id"),
                    "fix_versions": vuln.get("fix_versions") or [],
                    "description": (vuln.get("description") or "").split("\n")[0],
                }
            )
    return {"ok": True, "vulnerabilities": vulns, "error": None}


def npm_audit(frontend_dir: Path) -> dict:
    """Run npm audit against frontend/ in JSON mode."""
    if not frontend_dir.exists():
        return {"ok": False, "vulnerabilities": [], "error": "frontend/ not present"}
    proc = _run(
        ["npm", "audit", "--json", "--audit-level", "low"],
        cwd=frontend_dir,
    )
    # npm audit returns nonzero on findings; that's expected.
    if proc.returncode not in (0, 1):
        return {
            "ok": False,
            "vulnerabilities": [],
            "error": (
                f"npm audit exited {proc.returncode}: "
                f"{proc.stderr.strip() or proc.stdout.strip()[:300]}"
            ),
        }
    try:
        payload = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError as e:
        return {
            "ok": False,
            "vulnerabilities": [],
            "error": f"npm audit produced invalid JSON: {e}",
        }
    vulns: list[dict] = []
    for name, entry in (payload.get("vulnerabilities") or {}).items():
        if not isinstance(entry, dict):
            continue
        vulns.append(
            {
                "name": name,
                "severity": entry.get("severity"),
                "via": (
                    [
                        v.get("source") if isinstance(v, dict) else v
                        for v in entry.get("via", [])
                    ]
                    if entry.get("via")
                    else []
                ),
                "fixAvailable": bool(entry.get("fixAvailable")),
            }
        )
    return {"ok": True, "vulnerabilities": vulns, "error": None}


def _watch_tier_packages(register_path: Path) -> list[tuple[str, str]]:
    """Parse the Watch / At-Risk / Replace-Now headline table from
    the register and return ``(name, surface)`` tuples. ``surface`` is
    the second column verbatim (e.g., ``"Frontend (devDep)"``,
    ``"Python (API runtime)"``, ``"GitHub Action"``); callers dispatch
    the correct staleness-check function from it. Falls back to an
    empty list if the register is missing or unparseable; the audit
    can still run pip-audit and npm audit.

    Register table header (source of truth):
        | Package | Surface | Tier | Reason | Mitigation |

    Closes #162. Prior version returned only the package name and the
    caller dispatched via a brittle ``npm_known`` allowlist that
    missed ``eslint-plugin-react`` (it fell through to ``pip show``,
    surfacing as "not installed" under the Python section). Reading
    the Surface column directly from the register matches the table's
    own intent.
    """
    if not register_path.exists():
        return []
    text = register_path.read_text()
    # Pull the first markdown table after the "act on these" anchor.
    anchor = "## At-Risk and Replace-Now Items"
    if anchor not in text:
        return []
    section = text.split(anchor, 1)[1].split("\n## ", 1)[0]
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or cells[0].startswith("---"):
            continue
        # First cell is something like `package-name` (in backticks).
        # Header row "| Package | Surface | ..." has no backticks and
        # falls through cleanly.
        match = re.search(r"`([^`]+)`", cells[0])
        if not match:
            continue
        name = match.group(1).split(" ", 1)[0]
        surface = cells[1] if len(cells) >= 2 else ""
        rows.append((name, surface))
    return rows


def staleness_check_python(package: str) -> dict:
    """Look up Python package release date via ``pip show``."""
    proc = _run(["pip", "show", package])
    if proc.returncode != 0:
        return {"package": package, "found": False, "summary": "not installed"}
    home = ""
    version = ""
    for line in proc.stdout.splitlines():
        if line.startswith("Version:"):
            version = line.split(":", 1)[1].strip()
        elif line.startswith("Home-page:"):
            home = line.split(":", 1)[1].strip()
    return {
        "package": package,
        "found": True,
        "version": version,
        "home": home,
        "summary": f"installed {package}=={version}",
    }


def staleness_check_npm(package: str, frontend_dir: Path) -> dict:
    """Look up npm package metadata via ``npm view``."""
    proc = _run(["npm", "view", package, "time", "--json"], cwd=frontend_dir)
    if proc.returncode != 0:
        return {"package": package, "found": False, "summary": "npm view failed"}
    try:
        times = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {
            "package": package,
            "found": False,
            "summary": "invalid npm view output",
        }
    latest_modified = times.get("modified")
    return {
        "package": package,
        "found": True,
        "latest_modified": latest_modified,
        "summary": f"last published {latest_modified}",
    }


def render_report(
    pip_results: list[tuple[Path, dict]],
    npm_result: dict,
    staleness_python: list[dict],
    staleness_npm: list[dict],
) -> str:
    """Build the markdown report."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = []
    lines.append(f"# Dependency Risk Audit -- {now}")
    lines.append("")
    lines.append(
        "Automated weekly audit. See "
        "`docs/runbooks/DEPENDENCY_RISK_AUDIT_RUNBOOK.md` for triage."
    )
    lines.append("")

    # Python CVEs
    lines.append("## Python -- pip-audit")
    lines.append("")
    total_py_vulns = 0
    for req_file, result in pip_results:
        if not result["ok"]:
            lines.append(
                f"- **{str(req_file.relative_to(REPO_ROOT))}** -- audit failed: {result['error']}"
            )
            continue
        if not result["vulnerabilities"]:
            lines.append(f"- **{str(req_file.relative_to(REPO_ROOT))}** -- clean")
            continue
        total_py_vulns += len(result["vulnerabilities"])
        lines.append(
            f"- **{str(req_file.relative_to(REPO_ROOT))}** -- {len(result['vulnerabilities'])} "
            "vulnerabilit(y/ies):"
        )
        for v in result["vulnerabilities"]:
            fix = (
                "fixed in " + ", ".join(v["fix_versions"])
                if v["fix_versions"]
                else "no fix yet"
            )
            lines.append(f"  - `{v['name']}=={v['version']}` -- {v['id']} ({fix})")
            if v["description"]:
                lines.append(f"    - {v['description']}")
    lines.append("")
    lines.append(f"**Python vulns total:** {total_py_vulns}")
    lines.append("")

    # npm CVEs
    lines.append("## Frontend -- npm audit")
    lines.append("")
    if not npm_result["ok"]:
        lines.append(f"audit failed: {npm_result['error']}")
    elif not npm_result["vulnerabilities"]:
        lines.append("clean")
    else:
        for v in npm_result["vulnerabilities"]:
            fix = "fix available" if v["fixAvailable"] else "no fix yet"
            lines.append(f"- `{v['name']}` -- severity {v['severity']} ({fix})")
    lines.append("")
    lines.append(f"**npm vulns total:** {len(npm_result.get('vulnerabilities', []))}")
    lines.append("")

    # Staleness
    lines.append("## Watch / At-Risk staleness")
    lines.append("")
    lines.append("Last-release dates for tracked Watch and At-Risk deps.")
    lines.append("")
    if staleness_python:
        lines.append("### Python")
        lines.append("")
        for entry in staleness_python:
            if entry["found"]:
                lines.append(f"- `{entry['package']}` -- {entry['summary']}")
            else:
                lines.append(f"- `{entry['package']}` -- {entry['summary']}")
        lines.append("")
    if staleness_npm:
        lines.append("### Frontend")
        lines.append("")
        for entry in staleness_npm:
            if entry["found"]:
                lines.append(f"- `{entry['package']}` -- {entry['summary']}")
            else:
                lines.append(f"- `{entry['package']}` -- {entry['summary']}")
        lines.append("")

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Recurring dependency risk audit for Project Aura."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to write the markdown report.",
    )
    parser.add_argument(
        "--skip-pip-audit",
        action="store_true",
        help="Skip the pip-audit step (useful for environments where "
        "pip-audit isn't available).",
    )
    parser.add_argument(
        "--skip-npm-audit",
        action="store_true",
        help="Skip the npm audit step.",
    )
    args = parser.parse_args(argv)

    pip_results: list[tuple[Path, dict]] = []
    if not args.skip_pip_audit:
        for req_file in PYTHON_REQUIREMENTS:
            pip_results.append((req_file, pip_audit(req_file)))

    npm_result: dict
    if args.skip_npm_audit or not (FRONTEND_DIR / "package.json").exists():
        npm_result = {
            "ok": True,
            "vulnerabilities": [],
            "error": "skipped",
        }
    else:
        npm_result = npm_audit(FRONTEND_DIR)

    tracked_packages = _watch_tier_packages(REGISTER_PATH)
    # Dispatch on the register's Surface column (closes #162). The prior
    # heuristic used an `npm_known` allowlist that had to be hand-curated
    # and missed `eslint-plugin-react` (which then surfaced as
    # "not installed" under the Python section). Surface column values
    # in the register: "Python (...)", "Frontend (...)", "GitHub Action",
    # "Backend (...)", etc.
    staleness_python: list[dict] = []
    staleness_npm: list[dict] = []
    for pkg, surface in tracked_packages:
        surface_lower = surface.lower()
        if surface_lower.startswith("frontend"):
            staleness_npm.append(staleness_check_npm(pkg, FRONTEND_DIR))
        elif surface_lower.startswith("python") or surface_lower.startswith("backend"):
            staleness_python.append(staleness_check_python(pkg))
        elif surface_lower.startswith("github action"):
            # Skip: tracked by SHA pinning, not release-date staleness.
            continue
        elif pkg.startswith("@"):
            # Fallback for npm-scoped packages whose Surface value didn't
            # match (e.g., a future addition with a non-standard label).
            staleness_npm.append(staleness_check_npm(pkg, FRONTEND_DIR))
        else:
            # Conservative fallback: try pip first. If a package's
            # Surface label is novel, surface it under Python; the
            # follow-up triage notices the misclassification and the
            # register can be updated.
            staleness_python.append(staleness_check_python(pkg))

    report = render_report(
        pip_results=pip_results,
        npm_result=npm_result,
        staleness_python=staleness_python,
        staleness_npm=staleness_npm,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report)
    print(f"Wrote audit report to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
