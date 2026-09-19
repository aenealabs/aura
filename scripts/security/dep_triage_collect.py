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
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTER_PATH = REPO_ROOT / "docs/security/DEPENDENCY_RISK_REGISTER.md"

_BUMP = re.compile(
    r"\b(?:bump|update)\s+(?P<pkg>\S+?)(?:\s+requirement)?\s+"
    r"from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)"
)

# Dependabot reports versions as `>=2.13.5`, `^4.1.11` or `v7.0.1`. Strip the
# range operators and any single leading `v` before querying a registry; a
# leading `v` would otherwise blank the whole string below and read as an
# unresolvable version rather than a tagged one.
_VERSION_PREFIX = re.compile(r"^[\^~>=<\s]*[vV]?")
_VERSION_CLEAN = re.compile(r"[^\d.].*$")

# Dependabot states its own case in the preamble, before the first collapsible
# block; everything from that tag onward is upstream release notes and commit
# lists it merely embedded. Truncating at the first tag -- rather than trying to
# strip matched pairs -- is deliberate: paired stripping is not nesting-aware,
# so an outer block whose first close tag belongs to an inner block would leak
# its tail back into scope. The tolerant pattern also catches `<details open>`
# and `< DETAILS >`. Both choices shrink the search scope, which is the safe
# direction here.
_DETAILS_OPEN = re.compile(r"<\s*details\b", re.IGNORECASE)
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
    preamble. Ordinary version bumps embed upstream release notes in
    collapsible blocks, and those routinely mention CVEs fixed in earlier
    releases within the range -- text that says nothing about whether *this*
    update is a security fix.

    That matters because the flag bypasses both the cooldown and the
    major-version hold. The two error directions are not symmetric: a missed
    advisory only means the patch queues through the cooldown normally, while a
    false positive strips both protections from an ordinary bump. Only the
    preamble is searched, and detection errs toward not-security.
    """
    preamble = _DETAILS_OPEN.split(body or "", maxsplit=1)[0]
    return bool(_ADVISORY.search(preamble))


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


def _fetch_json(url: str) -> dict:
    """Fetch and parse a JSON document over HTTPS."""
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def release_age_days(
    ecosystem: str,
    package: str,
    version: str,
    now: datetime,
    fetch: Callable[[str], dict] = _fetch_json,
) -> float | None:
    """Return the age in days of a package version, or None if unavailable.

    Returns None rather than raising on any lookup failure -- network down,
    the package or version missing from the index, an unparseable version
    string, a malformed timestamp, anything. This is deliberate and must stay
    a broad ``except Exception``, not narrowed to a specific error type:
    ``rule_cooldown`` treats an unknown age as held, so a lookup failure here
    is the conservative outcome. Letting an exception propagate instead would
    abort the entire collection run and leave the queue with no snapshot at
    all, which is strictly worse than holding one PR's cooldown decision.
    """
    try:
        clean = _VERSION_CLEAN.sub("", _VERSION_PREFIX.sub("", version or ""))
        if not clean or not package:
            return None
        # The package name comes from a Dependabot PR title. The capture excludes
        # whitespace and the host below is hardcoded, so this is not a header
        # injection or SSRF vector -- quoting only guards against a name
        # containing '/', '?' or '#' reaching an unintended path on that host.
        safe_package = urllib.parse.quote(package, safe="")
        if ecosystem == "pip":
            data = fetch(f"https://pypi.org/pypi/{safe_package}/{clean}/json")
            stamps = [
                u["upload_time_iso_8601"]
                for u in data.get("urls", [])
                if u.get("upload_time_iso_8601")
            ]
            if not stamps:
                return None
            released = datetime.fromisoformat(min(stamps).replace("Z", "+00:00"))
        elif ecosystem == "npm":
            data = fetch(f"https://registry.npmjs.org/{safe_package}")
            stamp = data.get("time", {}).get(clean)
            if not stamp:
                return None
            released = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        else:
            # docker, github-actions, unknown: no stdlib-reachable registry
            # exposes a release timestamp keyed by version. rule_cooldown
            # holds these PRs, which is the intended conservative outcome.
            return None
        if released.tzinfo is None:
            # A timestamp with no offset cannot be compared against an aware
            # `now`. Guessing UTC would invent precision we do not have, and
            # letting the subtraction raise would abort the whole collection
            # run, so treat it as unavailable.
            return None
        return (now - released).total_seconds() / 86400.0
    except Exception:
        return None


def build_snapshot(
    prs: list[dict],
    checks_by_pr: dict[int, list[dict]],
    required_checks: list[str],
    release_ages: dict[tuple[str, str], float | None],
    risk_tiers: dict[str, str],
) -> dict:
    """Assemble the snapshot document consumed by dep_triage.load_snapshot.

    ``release_ages`` is keyed by ``(ecosystem, package)`` rather than bare
    package name, so a same-named pip and npm package in one batch cannot
    clobber each other's cached age.
    """
    out: list[dict] = []
    for pr in prs:
        files = list(pr.get("files", []))
        package, old, new = parse_bump_title(pr.get("title", ""))
        ecosystem = infer_ecosystem(files)
        out.append(
            {
                "number": pr["number"],
                "title": pr.get("title", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "files": files,
                "checks": checks_by_pr.get(pr["number"], []),
                "required_checks": required_checks,
                "ecosystem": ecosystem,
                "directory": infer_directory(files),
                "package": package,
                "from_version": old,
                "to_version": new,
                "release_age_days": release_ages.get((ecosystem, package)),
                "risk_tier": risk_tiers.get(package, "unknown"),
                "security_advisory": bool(pr.get("security_advisory", False)),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pull_requests": out,
    }


def _gh_json(args: list[str]) -> object:
    """Run a gh command and parse its JSON output.

    Raises ``RuntimeError`` naming the command and including its stderr on
    failure, rather than letting a raw ``CalledProcessError`` traceback surface
    on auth failure, rate limiting, or a bad repo. This must not be swallowed:
    a failed collection should fail loudly rather than silently producing a
    partial snapshot.
    """
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as exc:
        command = " ".join(["gh", *args])
        raise RuntimeError(
            f"command failed: {command!r} (exit {exc.returncode}): {exc.stderr}"
        ) from exc
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
                "status": (
                    "in_progress"
                    if r["state"] in ("PENDING", "IN_PROGRESS")
                    else "completed"
                ),
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

    now = datetime.now(timezone.utc)
    release_ages: dict[tuple[str, str], float | None] = {}
    for pr in prs:
        package, _, new = parse_bump_title(pr["title"])
        ecosystem = infer_ecosystem(pr["files"])
        key = (ecosystem, package)
        if package and key not in release_ages:
            # Store even a None: build_snapshot reads this with .get(), so a
            # cached None and an absent key behave identically, and caching the
            # failure stops every later PR for the same (ecosystem, package)
            # refetching it.
            release_ages[key] = release_age_days(ecosystem, package, new, now)

    snapshot = build_snapshot(
        prs=prs,
        checks_by_pr=checks_by_pr,
        required_checks=args.required_check,
        release_ages=release_ages,
        risk_tiers=_risk_tiers(REGISTER_PATH),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
