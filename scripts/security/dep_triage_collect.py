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

from scripts.security import dep_risk_register

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

# Grouped Dependabot PRs. .github/dependabot.yml configures a `minor-and-patch`
# group for pip and for npm, so these are the routine shape here, not an edge
# case. The title carries no package, so the member list has to come from the
# body -- and no single place in the body is complete:
#
# * The summary table has every member, but a body long enough to be truncated
#   by GitHub's size cap keeps the table (it is at the top) and loses the
#   per-member lines. Observed on aenealabs/aura#451: 9 table rows, 4 `Updates`
#   lines.
# * The per-member `Updates` lines carry members the table omits -- a
#   transitively-pulled package. Observed on #311: 6 table/preamble entries,
#   7 `Updates` lines.
# * A single-directory group with no table states its members as a prose list
#   in the preamble instead. Observed on #393.
#
# So all three are parsed and unioned, and the count in the title is the
# authority on whether the union is complete. Shapes verified against live
# bodies; do not narrow any of these to one source.
_GROUP_UPDATES_LINE = re.compile(
    r"^Updates\s+`(?P<pkg>[^`]+)`\s+from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)",
    re.MULTILINE,
)
_GROUP_TABLE_ROW = re.compile(
    r"^\|\s*(?P<pkg>[^|]+?)\s*\|\s*`(?P<old>[^`|]+)`\s*\|\s*`(?P<new>[^`|]+)`\s*\|",
    re.MULTILINE,
)
_GROUP_PREAMBLE = re.compile(
    r"^Bumps the .+? group with \d+ updates?\b[^:\n]*:(?P<rest>.*)$",
    re.MULTILINE,
)
_MARKDOWN_LINK = re.compile(r"\[(?P<text>[^\]]+)\]\([^)]*\)")


def _unlink(cell: str) -> str:
    """Reduce a markdown link to its text, leaving a bare name untouched."""
    match = _MARKDOWN_LINK.fullmatch(cell.strip())
    return match.group("text") if match else cell.strip()


def parse_group_members(body: str) -> list[dict]:
    """Extract a grouped PR's member packages from its body.

    Returns one dict per member with ``package``, ``from_version`` and
    ``to_version``; the versions are empty strings for a member only the
    prose preamble names. Order is stable: per-member lines first, then table
    rows, then preamble names, and the first source to name a package wins its
    versions.

    Never raises. A body shape this does not recognise yields fewer members
    than the title promises, which ``dep_triage.rule_grouped`` turns into an
    explicit ``held:grouped-unparsed`` rather than a silent pass.
    """
    members: dict[str, dict] = {}

    def add(package: str, old: str, new: str) -> None:
        name = package.strip().strip("`")
        if name and name not in members:
            members[name] = {
                "package": name,
                "from_version": old,
                "to_version": new,
            }

    for match in _GROUP_UPDATES_LINE.finditer(body or ""):
        add(match.group("pkg"), match.group("old"), match.group("new"))
    for match in _GROUP_TABLE_ROW.finditer(body or ""):
        # The header row ("| Package | From | To |") and the separator carry no
        # backticks in the version cells, so neither reaches here.
        add(_unlink(match.group("pkg")), match.group("old"), match.group("new"))
    for match in _GROUP_PREAMBLE.finditer(body or ""):
        for link in _MARKDOWN_LINK.finditer(match.group("rest")):
            add(link.group("text"), "", "")
    return list(members.values())


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
    """Map normalized package name to tier by reading the risk register.

    Thin wrapper over ``dep_risk_register.load_risk_tiers`` -- the one parser
    both this module and ``dep_risk_audit.py`` import, so they cannot read
    the register's Tier column two different ways again. See
    ``dep_risk_register``'s module docstring for why a second parser is a
    hazard in itself: a markdown-parsing bug in an earlier version of this
    exact function dropped ``image-size`` -- At-Risk with two unpatched CVEs
    -- and the hold never fired.

    Kept as a module-level name (rather than inlining the import at every
    call site) because the existing tests call ``dc._risk_tiers`` directly;
    it raises the same ``RuntimeError`` (a ``RegisterFormatError``, which
    subclasses it) on a missing or reshaped register that it always has.
    """
    return dep_risk_register.load_risk_tiers(register)


def _fetch_json(url: str) -> dict:
    """Fetch and parse a JSON document over HTTPS."""
    with urllib.request.urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _gh_api_json(path: str) -> dict:
    """Fetch one GitHub REST resource as JSON through the gh CLI."""
    return _gh_json(["api", path])  # type: ignore[return-value]


def _gh_text(args: list[str]) -> str:
    """Run a gh command and return its stdout, or "" when it fails.

    Unlike ``_gh_json`` this swallows the failure. Its only caller is the
    optional diff read below, which has a working fallback, so aborting the
    collection over it would trade a complete snapshot for nothing.
    """
    try:
        result = subprocess.run(
            ["gh", *args], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, OSError):
        return ""
    return result.stdout


# An added `uses:` line pinning an action to a full commit SHA, which is this
# repository's convention. Anchored to the '+' so a removed line -- the old
# pin -- cannot be read as the new one.
_USES_PIN = re.compile(
    r"^\+.*\buses:\s*(?P<action>[\w.-]+/[\w./-]+)@(?P<sha>[0-9a-f]{40})\b",
    re.MULTILINE,
)


def action_sha_from_diff(diff: str, package: str) -> str | None:
    """Return the commit SHA a PR's diff pins ``package`` to, or None."""
    for match in _USES_PIN.finditer(diff or ""):
        if match.group("action") == package:
            return match.group("sha")
    return None


def _action_commit_age_days(
    package: str,
    version: str,
    now: datetime,
    gh_api: Callable[[str], dict],
    action_sha: str | None,
) -> float | None:
    """Age in days of the commit a GitHub Action bump pins, or None.

    For a SHA-pinned action the commit date of the pinned SHA is the metric
    that matters, not the tag's release date: the tag is a mutable label that
    can be repointed after publication, and what actually executes with
    repository credentials is the commit.

    ``action_sha`` -- read from the PR's own diff -- is preferred for exactly
    that reason. Resolving the tag is the fallback for when the diff could not
    be read, and it dereferences an annotated tag object rather than treating
    the tag's own SHA as a commit.
    """
    owner, _, rest = (package or "").partition("/")
    repo = rest.split("/", 1)[0]
    if not owner or not repo:
        return None

    sha = action_sha
    if not sha:
        tag = (version or "").strip()
        if not tag:
            return None
        # Dependabot's titles carry the bare version ("4.38.1") while the tag
        # is conventionally "v4.38.1". Try both rather than assuming either.
        candidates = [tag] if tag[:1] in "vV" else [f"v{tag}", tag]
        ref: dict | None = None
        for candidate in candidates:
            quoted = urllib.parse.quote(candidate, safe="")
            try:
                ref = gh_api(f"repos/{owner}/{repo}/git/ref/tags/{quoted}")
            except Exception:
                continue
            break
        obj = (ref or {}).get("object") or {}
        sha = obj.get("sha")
        if obj.get("type") == "tag" and sha:
            annotated = gh_api(f"repos/{owner}/{repo}/git/tags/{sha}")
            sha = ((annotated or {}).get("object") or {}).get("sha")
    if not sha:
        return None

    commit = gh_api(f"repos/{owner}/{repo}/commits/{sha}")
    stamp = (((commit or {}).get("commit") or {}).get("committer") or {}).get("date")
    if not stamp:
        return None
    committed = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    if committed.tzinfo is None:
        return None
    return (now - committed).total_seconds() / 86400.0


def release_age_days(
    ecosystem: str,
    package: str,
    version: str,
    now: datetime,
    fetch: Callable[[str], dict] = _fetch_json,
    gh_api: Callable[[str], dict] = _gh_api_json,
    action_sha: str | None = None,
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

    That discipline covers the github-actions path too: every gh API call it
    makes is inside this same broad handler, so a rate limit, a deleted tag or
    an unreachable repository yields None -- which rule_cooldown holds on --
    rather than aborting the run.
    """
    try:
        if not package:
            return None
        if ecosystem == "github-actions":
            return _action_commit_age_days(package, version, now, gh_api, action_sha)
        clean = _VERSION_CLEAN.sub("", _VERSION_PREFIX.sub("", version or ""))
        if not clean:
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
            # docker and unknown: no stdlib-reachable registry exposes a
            # release timestamp keyed by version. rule_cooldown holds these
            # PRs under held:no-release-metadata, which is the intended
            # conservative outcome. github-actions used to be in this list,
            # which meant ACTION_COOLDOWN_DAYS never evaluated and every
            # action bump was held forever; it is resolved above instead.
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

    ``risk_tiers`` is keyed by ``dep_risk_register.normalize_package``'s
    output, not the bare register spelling, so every lookup below normalizes
    the PR's own package name through the same function before matching --
    otherwise a casing or separator difference (``Pillow`` vs ``pillow``,
    ``nest_asyncio`` vs ``nest-asyncio``) would miss a real register entry.
    Today's register rows happen to be lowercase-hyphenated already, so this
    was latent rather than live, but a lookup keyed on exact string equality
    is one register edit away from a silent miss.
    """
    out: list[dict] = []
    for pr in prs:
        files = list(pr.get("files", []))
        package, old, new = parse_bump_title(pr.get("title", ""))
        ecosystem = infer_ecosystem(files)
        # Members are emitted for every PR whose body names any, not only for
        # ones whose title reads as a group. Deciding what counts as a grouped
        # PR is the classifier's job, and it makes that call from the title;
        # the collector's job is to supply whatever the body states.
        #
        # A grouped update's members share the PR's own ecosystem --
        # .github/dependabot.yml groups pip with pip and npm with npm, never
        # mixed -- so normalizing every member through the PR-level
        # `ecosystem` is correct, not an approximation.
        members = [
            {
                **member,
                "risk_tier": risk_tiers.get(
                    dep_risk_register.normalize_package(ecosystem, member["package"]),
                    "unknown",
                ),
                "release_age_days": release_ages.get((ecosystem, member["package"])),
            }
            for member in parse_group_members(pr.get("body", ""))
        ]
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
                "risk_tier": risk_tiers.get(
                    dep_risk_register.normalize_package(ecosystem, package),
                    "unknown",
                ),
                "members": members,
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
            #
            # `body` is fetched again, having been dropped when the advisory
            # detector was removed. It is the only place a grouped PR states
            # its member packages, and without them a grouped PR -- the most
            # common shape in this repo -- carries no package name at all, so
            # no deliberate hold and no At-Risk tier can fire for anything
            # inside it. The bodies are large; that is the price of the holds.
            "number,title,author,files,headRefOid,body",
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
            "body": item.get("body", ""),
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
        wanted = [(package, new)]
        # A grouped PR's cooldown is decided member by member. Without these
        # lookups a group would carry no age at all, and the only honest thing
        # to do with it would be to skip the cooldown -- which would let the
        # most common PR shape in the repo bypass the control outright.
        wanted += [
            (member["package"], member["to_version"])
            for member in parse_group_members(pr.get("body", ""))
        ]
        for name, version in wanted:
            key = (ecosystem, name)
            if not name or key in release_ages:
                continue
            action_sha = None
            if ecosystem == "github-actions" and name == package:
                # The SHA this PR actually pins, read from its own diff. A tag
                # is a mutable label; the commit is what will execute with
                # repository credentials. Falls back to resolving the tag ref
                # inside release_age_days when the diff cannot be read.
                action_sha = action_sha_from_diff(
                    _gh_text(["pr", "diff", str(pr["number"]), "--repo", args.repo]),
                    name,
                )
            # Store even a None: build_snapshot reads this with .get(), so a
            # cached None and an absent key behave identically, and caching
            # the failure stops every later PR for the same (ecosystem,
            # package) refetching it.
            # `fetch` and `gh_api` are named explicitly rather than left to
            # release_age_days' defaults: a default argument binds at
            # definition time, so the collaborators would not be substitutable
            # from here and the wiring above could only be tested by
            # reimplementing it.
            release_ages[key] = release_age_days(
                ecosystem,
                name,
                version,
                now,
                fetch=_fetch_json,
                gh_api=_gh_api_json,
                action_sha=action_sha,
            )

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
