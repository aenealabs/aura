#!/usr/bin/env python3
"""ADR-092 offline static action scan.

Parses every CloudFormation template under ``deploy/cloudformation/``, extracts
the union of IAM actions used by ``AWS::IAM::Role`` / ``AWS::IAM::Policy`` /
``AWS::IAM::ManagedPolicy`` resources, and cross-references with what
ADR-092's ``CloudFormationScopedManagedPolicy`` grants. Reports gaps that
would surface as ``AccessDenied`` during deploy if the platform were
exercising the deferred ADR-092 deploy phases.

This is an **offline approximation** of ADR-092 Phase 1 (CloudTrail Lake
inventory) for when the cost gate keeps live-AWS validation paused.

Usage
=====

::

    python scripts/adr_092_static_action_scan.py
    python scripts/adr_092_static_action_scan.py --report-markdown report.md
    python scripts/adr_092_static_action_scan.py --fail-on-gap  # exit 1 on gaps
    python scripts/adr_092_static_action_scan.py --service kms,s3  # narrow

Outputs
=======

- stdout: human-readable summary
- ``--report-markdown <path>``: full markdown report
- exit ``1`` if ``--fail-on-gap`` is set and any gap is found

What this catches
=================

- Every IAM action that appears in any ``AWS::IAM::Role`` / ``Policy`` /
  ``ManagedPolicy`` resource in the 170 platform CloudFormation templates
- Whether each action is covered by ADR-092's
  ``CloudFormationScopedManagedPolicy``, accounting for wildcards
  (``s3:*`` covers ``s3:GetObject``, ``s3:Get*`` covers ``s3:GetObject``)

What this misses
================

- Actions CFN takes implicitly during stack deployment that are not in the
  template (e.g., the deploy role calling ``iam:CreateRole`` when deploying
  an ``AWS::IAM::Role`` resource - that action is CFN-internal, not in the
  template's policy bodies)
- Actions that fire only during stack rollback or drift detection
- Cross-region or fresh-account-bootstrap paths

So this script is **lower-bound on gaps** - a clean run does not guarantee
a clean live deploy. But any gap it finds is real and worth fixing before
the deploy phases re-engage.

References
==========

- ADR-092 §"Offline alternatives" (recommends this script)
- ADR-092 §"Phase 1 - Inventory" (live-AWS counterpart)
- Issue #182 (closed code-merge items, deferred deploy items)
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

# ---------------------------------------------------------------------------
# CloudFormation YAML loader (handles !Sub, !Ref, !If, !FindInMap, etc.)
# ---------------------------------------------------------------------------


def _cfn_tag_constructor(
    loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node
) -> Any:
    """Construct any unknown ``!Tag`` CFN intrinsic to its raw payload.

    We do not need to evaluate the intrinsic (we are static-parsing). We
    just need to preserve the contents so the surrounding mapping parses.
    """
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    if isinstance(node, yaml.MappingNode):
        return loader.construct_mapping(node, deep=True)
    return None


class CfnLoader(yaml.SafeLoader):
    """SafeLoader extension that accepts CloudFormation intrinsic tags."""


CfnLoader.add_multi_constructor("!", _cfn_tag_constructor)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionRef:
    """One IAM action reference found in a template."""

    action: str  # 's3:GetObject' or 's3:*' or '*'
    template_path: str  # relative path under deploy/cloudformation/
    resource_logical_id: str  # the CFN resource's logical ID
    statement_sid: str | None  # Statement's Sid, if any

    @property
    def service(self) -> str:
        """Return the service prefix (the bit before the colon).

        ``s3:GetObject`` -> ``s3``. ``*`` (admin wildcard) -> ``*``.
        """
        if ":" not in self.action:
            return self.action
        return self.action.split(":", 1)[0]


@dataclass
class GapReport:
    """Aggregated gap analysis result."""

    uncovered: list[ActionRef] = field(default_factory=list)
    covered: list[ActionRef] = field(default_factory=list)
    scoped_actions: set[str] = field(default_factory=set)
    total_templates_scanned: int = 0

    @property
    def uncovered_by_service(self) -> dict[str, list[ActionRef]]:
        out: dict[str, list[ActionRef]] = defaultdict(list)
        for ref in self.uncovered:
            out[ref.service].append(ref)
        return dict(out)

    @property
    def unique_uncovered_actions(self) -> set[str]:
        return {ref.action for ref in self.uncovered}

    @property
    def has_gaps(self) -> bool:
        return bool(self.uncovered)


# ---------------------------------------------------------------------------
# Action extraction from templates
# ---------------------------------------------------------------------------


_IAM_POLICY_RESOURCE_TYPES = frozenset(
    {
        "AWS::IAM::Role",
        "AWS::IAM::Policy",
        "AWS::IAM::ManagedPolicy",
        "AWS::IAM::User",
        "AWS::IAM::Group",
    }
)


def _normalize_actions(raw: Any) -> list[str]:
    """Coerce a YAML ``Action`` value into a list of strings.

    Handles: single string, list of strings, list-of-list (rare).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        out: list[str] = []
        for item in raw:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, list):
                # rare: list of strings via !If or similar
                out.extend(s for s in item if isinstance(s, str))
        return out
    # Unrecognized shape - ignore.
    return []


def _iter_statements(
    policy_document: Any,
) -> Iterable[tuple[dict[str, Any], str | None]]:
    """Yield ``(statement_dict, sid)`` for each statement in a PolicyDocument.

    Handles malformed inputs by returning nothing rather than raising.
    """
    if not isinstance(policy_document, dict):
        return
    statements = policy_document.get("Statement")
    if not isinstance(statements, list):
        return
    for stmt in statements:
        if not isinstance(stmt, dict):
            continue
        sid = stmt.get("Sid") if isinstance(stmt.get("Sid"), str) else None
        yield stmt, sid


def _iter_policy_documents_in_resource(
    resource: dict[str, Any],
) -> Iterable[dict[str, Any]]:
    """Yield every PolicyDocument inside an IAM resource's Properties.

    Covers:
    - ``AWS::IAM::Role`` ``Properties.Policies[].PolicyDocument``
    - ``AWS::IAM::Policy`` ``Properties.PolicyDocument``
    - ``AWS::IAM::ManagedPolicy`` ``Properties.PolicyDocument``
    - ``AWS::IAM::Role`` ``Properties.AssumeRolePolicyDocument`` (trust policy)
    """
    props = resource.get("Properties") or {}
    if not isinstance(props, dict):
        return
    # AWS::IAM::Role inline policies
    for pol in props.get("Policies") or []:
        if isinstance(pol, dict):
            doc = pol.get("PolicyDocument")
            if isinstance(doc, dict):
                yield doc
    # AWS::IAM::Policy / ManagedPolicy
    doc = props.get("PolicyDocument")
    if isinstance(doc, dict):
        yield doc
    # AWS::IAM::Role trust policy
    trust = props.get("AssumeRolePolicyDocument")
    if isinstance(trust, dict):
        yield trust


def extract_actions_from_template(
    template_path: Path, root_dir: Path
) -> list[ActionRef]:
    """Parse one CFN template and return all IAM action references in it."""
    try:
        raw = template_path.read_text(encoding="utf-8")
    except OSError:
        return []
    try:
        doc = yaml.load(raw, Loader=CfnLoader)  # noqa: S506 (CfnLoader is safe-derived)
    except yaml.YAMLError:
        return []
    if not isinstance(doc, dict):
        return []

    resources = doc.get("Resources")
    if not isinstance(resources, dict):
        return []

    rel_path = str(template_path.relative_to(root_dir))
    out: list[ActionRef] = []
    for logical_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        if resource.get("Type") not in _IAM_POLICY_RESOURCE_TYPES:
            continue
        for policy_doc in _iter_policy_documents_in_resource(resource):
            for stmt, sid in _iter_statements(policy_doc):
                # Only the Allow statements matter for "what actions does the
                # platform USE?" - Deny statements show what we forbid.
                effect = stmt.get("Effect")
                if effect != "Allow":
                    continue
                for action in _normalize_actions(stmt.get("Action")):
                    out.append(
                        ActionRef(
                            action=action,
                            template_path=rel_path,
                            resource_logical_id=logical_id,
                            statement_sid=sid,
                        )
                    )
    return out


# ---------------------------------------------------------------------------
# Action extraction from the ADR-092 scoped policy
# ---------------------------------------------------------------------------


def extract_scoped_policy_actions(iam_yaml_path: Path) -> set[str]:
    """Extract the Action set that the ADR-092 scoped policy grants.

    Looks at every ``AWS::IAM::ManagedPolicy`` whose logical ID starts
    with ``CloudFormationScoped`` (e.g.,
    ``CloudFormationScopedManagedPolicy``,
    ``CloudFormationScopedAdditionalServicesPolicy``) PLUS the
    ``CloudFormationServiceRole``'s inline policy. ADR-092 splits the
    policy across managed-policy + inline: Statements 1-3 in the primary
    managed policy, Wave 13 follow-up additional-services in the
    secondary managed policy, Statements 4-7 inline on the role.
    All grant access; all must be checked.

    The ``CloudFormationLegacyManagedPolicy`` is intentionally excluded
    because it is the rollback-only policy and the scan should report
    against the production-default scoped path.

    Returns a set of action strings. Wildcards (``s3:*``, ``s3:Get*``) are
    preserved verbatim so the matcher can expand them.
    """
    try:
        raw = iam_yaml_path.read_text(encoding="utf-8")
    except OSError:
        return set()
    try:
        doc = yaml.load(raw, Loader=CfnLoader)  # noqa: S506
    except yaml.YAMLError:
        return set()
    if not isinstance(doc, dict):
        return set()

    resources = doc.get("Resources") or {}
    if not isinstance(resources, dict):
        return set()

    granted: set[str] = set()

    # 1) Every CloudFormationScoped* managed policy (primary scoped +
    #    Wave 13 additional services).
    for logical_id, resource in resources.items():
        if not isinstance(resource, dict):
            continue
        if resource.get("Type") != "AWS::IAM::ManagedPolicy":
            continue
        if not logical_id.startswith("CloudFormationScoped"):
            continue
        for doc_obj in _iter_policy_documents_in_resource(resource):
            for stmt, _sid in _iter_statements(doc_obj):
                if stmt.get("Effect") != "Allow":
                    continue
                granted.update(_normalize_actions(stmt.get("Action")))

    # 2) The role's inline policy (Statements 4-7 + existing IAM/CFN/etc.
    #    blocks). Deny statements are excluded - they constrain, not grant.
    role = resources.get("CloudFormationServiceRole")
    if isinstance(role, dict):
        for doc_obj in _iter_policy_documents_in_resource(role):
            for stmt, _sid in _iter_statements(doc_obj):
                if stmt.get("Effect") != "Allow":
                    continue
                granted.update(_normalize_actions(stmt.get("Action")))

    return granted


# ---------------------------------------------------------------------------
# Wildcard-aware coverage matching
# ---------------------------------------------------------------------------


def action_is_covered(needed: str, granted: Iterable[str]) -> bool:
    """Return True if ``needed`` is granted by any pattern in ``granted``.

    Patterns may contain ``*`` and ``?`` wildcards (IAM/fnmatch semantics).
    Special cases:
    - ``*`` in ``granted`` covers everything
    - exact string match always covers
    - case-insensitive (IAM is case-insensitive on action names)
    """
    needed_lower = needed.lower()
    for pattern in granted:
        pattern_lower = pattern.lower()
        if pattern_lower == "*":
            return True
        if pattern_lower == needed_lower:
            return True
        # fnmatch supports * and ? wildcards
        if fnmatch.fnmatchcase(needed_lower, pattern_lower):
            return True
    return False


# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------


def scan(
    cfn_dir: Path,
    iam_yaml_path: Path,
    *,
    services_filter: set[str] | None = None,
    exclude_self: bool = True,
) -> GapReport:
    """Run the scan; return a GapReport.

    ``exclude_self``: skip the iam.yaml file when extracting template actions,
    because we are comparing the rest of the platform against iam.yaml's
    policy. Including iam.yaml in the template scan would double-count.
    """
    scoped = extract_scoped_policy_actions(iam_yaml_path)
    report = GapReport(scoped_actions=scoped)

    for template_path in sorted(cfn_dir.glob("**/*.yaml")):
        if exclude_self and template_path.resolve() == iam_yaml_path.resolve():
            continue
        report.total_templates_scanned += 1
        for ref in extract_actions_from_template(template_path, cfn_dir):
            if services_filter and ref.service not in services_filter:
                continue
            if action_is_covered(ref.action, scoped):
                report.covered.append(ref)
            else:
                report.uncovered.append(ref)
    return report


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_markdown_report(report: GapReport, cfn_dir: Path) -> str:
    """Render a markdown report of the gap analysis."""
    lines: list[str] = []
    lines.append("# ADR-092 Static Action Scan Report")
    lines.append("")
    try:
        cfn_display = (
            cfn_dir.relative_to(Path.cwd()) if cfn_dir.is_absolute() else cfn_dir
        )
    except ValueError:
        cfn_display = cfn_dir
    lines.append(
        f"Offline cross-reference of IAM actions used across `{cfn_display}/` "
        "templates vs. the ADR-092 scoped policy."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Templates scanned: **{report.total_templates_scanned}**")
    lines.append(
        f"- Actions granted by ADR-092 scoped policy: **{len(report.scoped_actions)}**"
    )
    lines.append(
        f"- Action references found in templates: **{len(report.covered) + len(report.uncovered)}**"
    )
    lines.append(
        f"- Covered: **{len(report.covered)}** | "
        f"Uncovered (gaps): **{len(report.uncovered)}** | "
        f"Unique uncovered actions: **{len(report.unique_uncovered_actions)}**"
    )
    lines.append("")

    if not report.uncovered:
        lines.append("## Result: ✅ No gaps")
        lines.append("")
        lines.append(
            "Every IAM action used by the platform's CloudFormation templates "
            "is covered by ADR-092's scoped policy (directly or via a "
            "wildcard match). This is necessary but not sufficient for live "
            'deploy success - see ADR-092 §"What this misses" for the gaps '
            "this scan cannot detect."
        )
        return "\n".join(lines) + "\n"

    lines.append("## Result: ⚠️ Gaps found")
    lines.append("")
    lines.append(
        "Each row below is an action that one of the platform's IAM resources "
        "lists, but that the ADR-092 scoped policy does NOT grant. **Important: "
        "this does not necessarily mean the CFN deploy role needs this action.** "
        "Most of these actions are granted to OTHER principals (Lambda execution "
        "roles, EKS pods, etc.), not the CFN deploy role itself. Use this as a "
        "discovery list, not a fix list. The CFN deploy role only needs actions "
        "that the platform takes on AWS APIs at deploy time, which is a smaller "
        "subset."
    )
    lines.append("")

    # Per-service breakdown
    lines.append("## Uncovered actions by service")
    lines.append("")
    by_service = report.uncovered_by_service
    for service in sorted(by_service):
        refs = by_service[service]
        unique_actions = sorted({r.action for r in refs})
        lines.append(f"### `{service}` ({len(unique_actions)} unique actions)")
        lines.append("")
        for action in unique_actions:
            templates = sorted({r.template_path for r in refs if r.action == action})
            lines.append(f"- `{action}`")
            for t in templates[:5]:
                lines.append(f"  - {t}")
            if len(templates) > 5:
                lines.append(f"  - ...and {len(templates) - 5} more templates")
        lines.append("")

    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "- Parser: PyYAML with a custom loader that accepts CloudFormation intrinsic tags (`!Sub`, `!Ref`, `!If`, etc.) without evaluating them"
    )
    lines.append(
        "- IAM resource types scanned: `AWS::IAM::Role`, `AWS::IAM::Policy`, `AWS::IAM::ManagedPolicy`"
    )
    lines.append("- Effect filter: only `Effect: Allow` statements")
    lines.append(
        "- Wildcard matching: case-insensitive `fnmatch` (`s3:*` matches `s3:GetObject`, `s3:Get*` matches `s3:GetObject`)"
    )
    lines.append(
        "- ADR-092 grant source: both `CloudFormationScopedManagedPolicy` "
        "and the inline policy on `CloudFormationServiceRole` "
        "(Statements 4-7 + existing IAM/CFN/Secrets/Bedrock/SSM blocks)"
    )
    return "\n".join(lines) + "\n"


def format_stdout_summary(report: GapReport) -> str:
    """Short human-readable summary for stdout."""
    lines: list[str] = []
    lines.append("ADR-092 Static Action Scan")
    lines.append("=" * 40)
    lines.append(f"Templates scanned: {report.total_templates_scanned}")
    lines.append(f"Scoped policy grants: {len(report.scoped_actions)} actions")
    lines.append(
        f"Action refs: {len(report.covered) + len(report.uncovered)} "
        f"({len(report.covered)} covered, {len(report.uncovered)} uncovered)"
    )
    lines.append(f"Unique uncovered actions: {len(report.unique_uncovered_actions)}")
    lines.append("")
    if not report.uncovered:
        lines.append("Result: NO GAPS")
        return "\n".join(lines)
    lines.append("Result: GAPS FOUND")
    lines.append("")
    by_service = report.uncovered_by_service
    for service in sorted(by_service):
        unique = {r.action for r in by_service[service]}
        lines.append(f"  {service}: {len(unique)} unique uncovered actions")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "ADR-092 offline static action scan. Surfaces IAM actions used "
            "by platform CloudFormation templates that are not granted by "
            "ADR-092's scoped policy."
        )
    )
    p.add_argument(
        "--cfn-dir",
        type=Path,
        default=Path("deploy/cloudformation"),
        help="CloudFormation template directory (default: deploy/cloudformation)",
    )
    p.add_argument(
        "--iam-yaml",
        type=Path,
        default=Path("deploy/cloudformation/iam.yaml"),
        help="Path to iam.yaml containing the scoped policy (default: deploy/cloudformation/iam.yaml)",
    )
    p.add_argument(
        "--service",
        type=str,
        default=None,
        help="Comma-separated list of services to filter (e.g. 's3,kms')",
    )
    p.add_argument(
        "--report-markdown",
        type=Path,
        default=None,
        help="Write full markdown report to this path",
    )
    p.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Write machine-readable JSON report to this path",
    )
    p.add_argument(
        "--fail-on-gap",
        action="store_true",
        help="Exit 1 if any uncovered actions are found (for CI gating)",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])
    services_filter: set[str] | None = None
    if args.service:
        services_filter = {s.strip() for s in args.service.split(",") if s.strip()}

    if not args.cfn_dir.is_dir():
        print(f"ERROR: cfn-dir not found: {args.cfn_dir}", file=sys.stderr)
        return 2
    if not args.iam_yaml.is_file():
        print(f"ERROR: iam-yaml not found: {args.iam_yaml}", file=sys.stderr)
        return 2

    report = scan(
        args.cfn_dir,
        args.iam_yaml,
        services_filter=services_filter,
    )

    print(format_stdout_summary(report))

    if args.report_markdown:
        args.report_markdown.parent.mkdir(parents=True, exist_ok=True)
        args.report_markdown.write_text(
            format_markdown_report(report, args.cfn_dir), encoding="utf-8"
        )
        print(f"\nMarkdown report: {args.report_markdown}")

    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "templates_scanned": report.total_templates_scanned,
            "scoped_policy_actions": sorted(report.scoped_actions),
            "covered_count": len(report.covered),
            "uncovered_count": len(report.uncovered),
            "unique_uncovered_actions": sorted(report.unique_uncovered_actions),
            "uncovered_by_service": {
                service: sorted({r.action for r in refs})
                for service, refs in report.uncovered_by_service.items()
            },
        }
        args.report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"JSON report: {args.report_json}")

    if args.fail_on_gap and report.has_gaps:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
