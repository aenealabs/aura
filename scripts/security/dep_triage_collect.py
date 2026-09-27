"""Collect the Dependabot triage snapshot.

The only module in the pipeline that performs network access: it lists the open
pull requests through ``gh`` and writes the flat JSON document
``dep_triage.py`` classifies. Keeping every call here is what lets the
classifier stay pure and testable against a recorded fixture.

``--record`` writes the raw ``gh`` response verbatim, untransformed. The
snapshot fixture under ``tests/fixtures/dep_triage/`` is derived from such a
capture by running ``build_snapshot`` over it -- never hand-authored -- and a
test asserts the two still agree. That discipline is not bookkeeping: a
transcribed fixture is how an author-login mismatch survived a green suite while
the classifier excluded every Dependabot PR, and replaying the capture through
the real code path is how four inert controls were found. Keep it.

No longer collected: check runs (``gh pr checks``, ``check_state`` and its
bucket mapping), release ages from PyPI, npm and git commit dates,
risk-register tiers, and grouped-PR member lists parsed from PR bodies. Each fed
a control ``dep_triage.py`` no longer has. The committed capture still carries
the ``body`` and ``pr_checks`` payloads those came from, because it is a
verbatim record of one live run and trimming it would make it a transcription.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# `gh pr list --limit N` truncates silently at N. A triage report that omits
# pull requests without saying so is worse than one that errors, so a listing
# that comes back at exactly the limit is treated as truncated and aborts.
# Raise this constant rather than letting the run quietly under-report.
PR_LIST_LIMIT = 100

# Case-insensitive: "Bump vitest from ..." and "Update vitest requirement
# from ..." are Dependabot's own default title forms. This repo happens to see
# the lowercase "bump"/"update" form only because Dependabot infers a
# conventional-commit prefix ("chore(deps): bump ...") from repo history --
# .github/dependabot.yml sets no commit-message.prefix to guarantee that. If
# that inference ever produces a differently-cased title, a case-sensitive
# pattern here would silently fail to parse every PR title.
_BUMP = re.compile(
    r"\b(?:bump|update)\s+(?P<pkg>\S+?)(?:\s+requirement)?\s+"
    r"from\s+(?P<old>\S+)\s+to\s+(?P<new>\S+)",
    re.IGNORECASE,
)


def parse_bump_title(title: str) -> tuple[str, str, str]:
    """Extract (package, from_version, to_version) from a Dependabot title.

    Returns three empty strings when the title is not a single-package bump,
    which is how release PRs and grouped updates fall through harmlessly. The
    package is the sole input to ``dep_triage.family_key``, so
    ``dep_triage.title_parse_line`` reports how many titles reached it.
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
    """Infer the manifest directory for npm PRs; '/' for everything else.

    Load-bearing, not cosmetic: an npm family key is scoped by directory, so the
    same package under frontend/ and sdk/typescript/ must not group together.
    """
    for path in files:
        if path.endswith(("package.json", "package-lock.json")):
            parent = str(Path(path).parent)
            return "/" if parent == "." else f"/{parent}"
    return "/"


def build_snapshot(prs: list[dict]) -> dict:
    """Assemble the snapshot document consumed by dep_triage.load_snapshot."""
    out = []
    for pr in prs:
        files = list(pr.get("files", []))
        package, old, new = parse_bump_title(pr.get("title", ""))
        out.append(
            {
                "number": pr["number"],
                "title": pr.get("title", ""),
                "head_sha": pr.get("head_sha", ""),
                "author": (pr.get("author") or {}).get("login", ""),
                "author_is_bot": bool((pr.get("author") or {}).get("is_bot", False)),
                "files": files,
                "ecosystem": infer_ecosystem(files),
                "directory": infer_directory(files),
                "package": package,
                "from_version": old,
                "to_version": new,
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
            ["gh", *args], capture_output=True, text=True, check=True, timeout=300
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
        "--output", type=Path, required=True, help="Path to write the snapshot JSON."
    )
    parser.add_argument("--repo", required=True, help="owner/name of the repository.")
    parser.add_argument(
        "--record",
        type=Path,
        default=None,
        help=(
            "Path to write the raw, untransformed gh response. Used to capture "
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
            # headRefOid binds every row to the exact commit it was computed
            # against. Dependabot force-pushes its branches on rebase, and the
            # operator consolidating a coupled family by hand needs to confirm
            # nothing moved underneath them.
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

    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(
            json.dumps(
                {
                    # Envelope metadata, kept distinct from the verbatim gh
                    # payload below so a reader can tell which fields this tool
                    # authored and which came off the wire unaltered.
                    "repo": args.repo,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "pr_list": listing,
                },
                indent=2,
                sort_keys=True,
            )
            # Trailing newline so a regenerated capture is already clean under
            # the repo's end-of-file-fixer hook rather than dirtying the tree.
            + "\n",
            encoding="utf-8",
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(build_snapshot(prs), indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
