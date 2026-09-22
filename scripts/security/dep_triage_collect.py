"""Collect the Dependabot triage snapshot.

This is the only module in the triage pipeline that performs network access.
It gathers pull request metadata, check runs, release ages and risk-register
tiers into a single JSON document, so that ``dep_triage.py`` can stay pure and
testable against recorded fixtures.

``--record`` writes the raw ``gh`` responses to a file without transforming
them. The snapshot fixture under ``tests/fixtures/dep_triage/`` is derived from
such a capture by running ``build_snapshot`` over it, never hand-authored: a
transcribed fixture can encode shapes the real tool never emits, which is how
an author-login mismatch and an unreachable zero-checks path both survived a
green suite.
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

# `gh pr list --limit N` truncates silently at N. A triage report that omits
# pull requests without saying so is worse than one that errors, so a listing
# that comes back at exactly the limit is treated as truncated and aborts.
# Raise this constant rather than letting the run quietly under-report.
PR_LIST_LIMIT = 100

# Case-insensitive: "Bump vitest from ..." and "Update vitest requirement
# from ..." are Dependabot's own default title forms. This repo happens to
# see the lowercase "bump"/"update" form only because Dependabot infers a
# conventional-commit prefix ("chore(deps): bump ...") from repo history --
# .github/dependabot.yml sets no commit-message.prefix to guarantee that. If
# that inference ever produces a differently-cased title, a case-sensitive
# pattern here would silently fail to parse every PR title.
_BUMP = re.compile(
    r"\b(?:bump|update)\s+(?P<pkg>\S+?)(?:\s+requirement)?\s+"
    r"from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)",
    re.IGNORECASE,
)

# Dependabot reports versions as `>=2.13.5`, `^4.1.11` or `v7.0.1`. Strip the
# range operators and any single leading `v` before querying a registry; a
# leading `v` would otherwise blank the whole string below and read as an
# unresolvable version rather than a tagged one.
_VERSION_PREFIX = re.compile(r"^[\^~>=<\s]*[vV]?")
_VERSION_CLEAN = re.compile(r"[^\d.].*$")

# Matches the first backticked token in a risk-register table cell, e.g. the
# `image-size` in "`image-size` (via `pptxgenjs`)". The register annotates
# some entries with their transitive source in the same cell, so the package
# name is never assumed to be the entire cell contents.
_FIRST_BACKTICKED = re.compile(r"`([^`]+)`")


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


# `gh pr checks --json` reports both `state`, an open vocabulary GitHub keeps
# extending (CANCELLED, TIMED_OUT, ACTION_REQUIRED, STARTUP_FAILURE, NEUTRAL,
# STALE, ERROR, ...), and `bucket`, gh's own normalization of it into five
# values. Mapping from the closed set means a state GitHub adds later cannot
# silently read as green.
_BUCKET_STATE: dict[str, tuple[str, str | None]] = {
    "pass": ("completed", "success"),
    "fail": ("completed", "failure"),
    "skipping": ("completed", "skipped"),
    "cancel": ("completed", "cancelled"),
    "pending": ("in_progress", None),
}


def check_state(bucket: str, state: str) -> tuple[str, str | None]:
    """Map a gh check bucket to (status, conclusion).

    `bucket` is gh's own normalization over an open-ended `state` vocabulary, so
    mapping from it means a state GitHub adds later cannot silently read as
    green. `state` is retained only for the human-readable reason text.

    An unrecognized bucket maps to ``("completed", None)`` -- no conclusion, not
    success. The classifier's ``rule_required_not_passing`` treats a required
    check with no conclusion as unproven, so an unknown bucket surfaces for a
    human instead of passing as green.
    """
    del state  # kept in the signature to document what is deliberately unused
    return _BUCKET_STATE.get(bucket, ("completed", None))


def _risk_tiers(register: Path) -> dict[str, str]:
    """Map package name to tier by reading the risk register's tables.

    Raises rather than returning an empty mapping when the register is absent
    or yields no tiers. An empty mapping is indistinguishable from "no package
    is At-Risk", so a moved, renamed or reformatted register would silently
    disarm ``rule_held_package`` and let an At-Risk package with unpatched CVEs
    classify as a candidate. Failing the collection is the only outcome that
    cannot be mistaken for a clean bill of health.
    """
    if not register.exists():
        raise RuntimeError(
            f"dependency risk register not found at {register}: the At-Risk "
            "holds cannot be evaluated, and an empty tier map is "
            "indistinguishable from a register in which nothing is held"
        )
    tiers: dict[str, str] = {}
    for line in register.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        # The name cell is usually just a bare backticked package name, but
        # some rows annotate it further, e.g. "`image-size` (via
        # `pptxgenjs`)". Stripping backticks off the whole cell in that case
        # yields "image-size` (via `pptxgenjs" -- garbage that never matches
        # a real package. Extract the first backticked token instead, falling
        # back to the stripped cell when there is no backtick at all.
        match = _FIRST_BACKTICKED.search(cells[0])
        name = match.group(1) if match else cells[0].strip("`")
        tier = cells[2].strip("*").lower()
        if tier in {"at-risk", "replace-now", "watch", "healthy"}:
            tiers[name] = tier
    if not tiers:
        raise RuntimeError(
            f"dependency risk register {register} parsed to zero package "
            "tiers: its table shape changed, so no At-Risk hold can fire"
        )
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
                "head_sha": pr.get("head_sha", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "author_is_bot": bool((pr.get("author") or {}).get("is_bot", False)),
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
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # The control inputs the classification was computed against, echoed
        # into the snapshot so the report can show them. A wrong control input
        # -- a risk register that moved, a title format that stopped parsing --
        # otherwise produces a confident report with no sign anything is off.
        "controls": {
            "risk_register_path": str(
                REGISTER_PATH.relative_to(REPO_ROOT)
                if REGISTER_PATH.is_relative_to(REPO_ROOT)
                else REGISTER_PATH
            ),
            "risk_register_tiers": dict(sorted(risk_tiers.items())),
        },
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
    parser.add_argument(
        "--record",
        type=Path,
        default=None,
        help=(
            "Path to write the raw, untransformed gh responses. Used to capture "
            "a test fixture from live output instead of transcribing one."
        ),
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
            str(PR_LIST_LIMIT),
            "--json",
            # headRefOid binds every verdict to the exact commit it was
            # computed against. Dependabot force-pushes its branches on rebase,
            # so "PR #N is merge-safe" is only true of one head, and the batch
            # proof re-checks this SHA before merging.
            "number,title,author,files,headRefOid",
        ]
    )
    if len(listing) >= PR_LIST_LIMIT:  # type: ignore[arg-type]
        raise RuntimeError(
            f"`gh pr list` returned {PR_LIST_LIMIT} pull requests, its own "
            "--limit: the listing is truncated and an unknown number of open "
            "PRs are missing from it. Raise PR_LIST_LIMIT rather than "
            "publishing a security report that silently omits pull requests."
        )
    prs = [
        {
            "number": item["number"],
            "title": item["title"],
            "author": item["author"],
            "files": [f["path"] for f in item.get("files", [])],
            "head_sha": item.get("headRefOid", ""),
        }
        for item in listing  # type: ignore[union-attr]
    ]

    raw_checks: dict[str, object] = {}
    checks_by_pr: dict[int, list[dict]] = {}
    for pr in prs:
        try:
            runs = _gh_json(
                [
                    "pr",
                    "checks",
                    str(pr["number"]),
                    "--repo",
                    args.repo,
                    "--json",
                    # `description` was fetched only to feed the removed flake
                    # detector, and is empty for every GitHub Actions check run,
                    # so it recorded nothing. See dep_triage's module docstring.
                    "name,state,bucket",
                ]
            )
        except RuntimeError as exc:
            if "no checks reported" not in str(exc).lower():
                raise
            # A pull request with no checks at all makes `gh pr checks` exit
            # non-zero before it can emit JSON. That is a legitimate state, not a
            # failure: rule_no_checks exists precisely to classify it. Any other
            # gh failure still aborts, because a partial snapshot is a silently
            # incomplete security report.
            runs = []
            raw_checks[str(pr["number"])] = {"error": str(exc)}
        else:
            raw_checks[str(pr["number"])] = runs
        mapped: list[dict] = []
        for run in runs:  # type: ignore[union-attr]
            status, conclusion = check_state(
                run.get("bucket", ""), run.get("state", "")
            )
            mapped.append(
                {
                    "name": run["name"],
                    "status": status,
                    "conclusion": conclusion,
                }
            )
        checks_by_pr[pr["number"]] = mapped

    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(
            json.dumps(
                {
                    # Envelope metadata, kept distinct from the two verbatim
                    # gh payloads below so a reader can tell which fields this
                    # tool authored and which came off the wire unaltered.
                    "repo": args.repo,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "pr_list": listing,
                    "pr_checks": raw_checks,
                },
                indent=2,
                sort_keys=True,
            )
            # Trailing newline so a regenerated capture is already clean under
            # the repo's end-of-file-fixer hook rather than dirtying the tree.
            + "\n",
            encoding="utf-8",
        )

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
    args.output.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
