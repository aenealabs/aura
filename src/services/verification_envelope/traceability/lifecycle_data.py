"""Project Aura - DO-178C lifecycle-data template generator (ADR-085 Phase 4).

Produces drafts of the five DO-178C lifecycle plans that DERs (Designated
Engineering Representatives) review during certification:

* **PSAC** — Plan for Software Aspects of Certification.
* **SDP**  — Software Development Plan.
* **SVP**  — Software Verification Plan.
* **SQAP** — Software Quality Assurance Plan.
* **SAS**  — Software Accomplishment Summary.

The templates are Markdown so they can be rendered, version-controlled,
diffed, and reviewed without specialised tooling. They consume the
:class:`TraceabilityService` to populate per-section content (HLR/LLR
counts, gap-analysis findings, traceability diagram) plus a small
:class:`LifecycleContext` of program-level metadata.

What this module *does not* do: it does not promise
certification-grade plans. It produces a starting draft that captures
what the platform has automatable insight into. A human author still
fills in the program-specific sections (assumptions, exceptions,
deviations) before the document goes to the DER.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from src.services.verification_envelope.traceability.contracts import (
    TraceabilityReport,
)
from src.services.verification_envelope.traceability.traceability_service import (
    TraceabilityService,
)


@dataclass(frozen=True)
class LifecycleContext:
    """Program-level metadata that flows into every plan template."""

    program_name: str
    program_id: str
    dal_level: str  # "DAL_A" .. "DAL_D"
    aircraft: str  # e.g. "Boeing 777"
    system: str  # e.g. "FADEC engine controller"
    cognizant_aco: str = ""  # FAA Aircraft Certification Office
    cognizant_der: str = ""  # Designated Engineering Representative
    project_url: str = ""
    revision: str = "DRAFT-1"
    authored_by: str = "Project Aura DVE"
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class LifecycleDocument:
    """A single generated plan."""

    name: str  # "PSAC", "SDP", ...
    title: str
    content: str  # Markdown
    generated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class LifecycleDataGenerator:
    """Generate the five DO-178C lifecycle plans from program data."""

    def __init__(self, traceability: TraceabilityService) -> None:
        self._tr = traceability

    async def generate_all(
        self, context: LifecycleContext
    ) -> tuple[LifecycleDocument, ...]:
        report = await self._tr.gap_report()
        return (
            self.generate_psac(context, report),
            self.generate_sdp(context, report),
            self.generate_svp(context, report),
            self.generate_sqap(context, report),
            self.generate_sas(context, report),
        )

    # ------------------------------------------------------------- PSAC

    def generate_psac(
        self, ctx: LifecycleContext, report: TraceabilityReport
    ) -> LifecycleDocument:
        body = "\n".join(
            [
                self._heading(ctx, "Plan for Software Aspects of Certification (PSAC)"),
                self._program_table(ctx),
                "",
                "## 1. System Overview",
                "",
                f"This PSAC governs the {ctx.system} software developed for the "
                f"{ctx.aircraft} platform. The system is classified at "
                f"**{ctx.dal_level}** per the system safety assessment.",
                "",
                "## 2. Software Life Cycle",
                "",
                "The development life cycle follows DO-178C section 3 with the "
                "Aura Deterministic Verification Envelope (DVE) providing the "
                "output verification argument under DO-330 §11.4.",
                "",
                "## 3. Compliance Strategy",
                "",
                "| Objective | DO-178C Reference | DVE Coverage |",
                "|-----------|-------------------|--------------|",
                "| MC/DC structural coverage | 6.4.4.2c | Phase 2 coverage gate |",
                "| Formal proof of C1-C4 | DO-333 supplement | Phase 3 verification gate |",
                "| Bidirectional requirements traceability | 5.5 | Phase 4 traceability service |",
                "| Output verification | DO-330 §11.4 | DVE pipeline (consensus + CGE + sandbox + HITL) |",
                "",
                "## 4. Tool Qualification",
                "",
                "| Tool | DO-330 Criteria | TQL |",
                "|------|----------------|-----|",
                "| Coder Agent | 1 (output becomes airborne software) | TQL-1, mitigated by DVE output verification |",
                "| Reviewer Agent | 2 (automates verification) | TQL-2 |",
                "| DVE consensus engine | 5 (deterministic software) | TQL-5 |",
                "| DVE coverage gate | 5 (deterministic software) | TQL-5 |",
                "| DVE formal verification gate | 2 (eliminates verification work) | TQL-2 |",
                "",
                self._gap_summary("Open traceability findings", report),
                "",
                "## 5. Roles and Responsibilities",
                "",
                f"- Cognizant ACO: **{ctx.cognizant_aco or '(TBD)'}**",
                f"- Designated Engineering Representative: **{ctx.cognizant_der or '(TBD)'}**",
                f"- Software development authority: {ctx.authored_by}",
                "",
                self._footer(ctx),
            ]
        )
        return LifecycleDocument(
            name="PSAC",
            title="Plan for Software Aspects of Certification",
            content=body,
        )

    # -------------------------------------------------------------- SDP

    def generate_sdp(
        self, ctx: LifecycleContext, report: TraceabilityReport
    ) -> LifecycleDocument:
        body = "\n".join(
            [
                self._heading(ctx, "Software Development Plan (SDP)"),
                self._program_table(ctx),
                "",
                "## 1. Standards",
                "",
                "- DO-178C 5.x (Software Development Process).",
                "- Project Aura coding standards (Black-formatted Python; "
                "mypy strict; flake8 line-length 120).",
                "",
                "## 2. Development Process",
                "",
                "1. HLRs are captured in the Aura traceability service "
                "(see Phase 4 records).",
                "2. LLRs derive from HLRs via DERIVED_FROM edges.",
                "3. Code artefacts trace to LLRs via TRACES_TO edges.",
                "4. Each commit triggers the DVE pipeline: consensus → "
                "CGE → formal verification → sandbox → coverage gate "
                "→ HITL approval.",
                "5. Approved patches merge to the protected branch.",
                "",
                "## 3. Configuration Management",
                "",
                "- Source: git on the customer's repository host.",
                "- Verification artefacts: S3 (proof-hash archive) + "
                "DynamoDB (decision audit). Both encrypted with "
                "customer-managed KMS keys.",
                "- Lifecycle data: this repository's "
                "`docs/certification/<program>/`.",
                "",
                f"## 4. Current State ({ctx.program_id})",
                "",
                f"- Total requirements: {report.requirement_count}",
                f"- Total artefacts: {report.artefact_count}",
                f"- Total trace edges: {report.edge_count}",
                "",
                self._footer(ctx),
            ]
        )
        return LifecycleDocument(
            name="SDP",
            title="Software Development Plan",
            content=body,
        )

    # -------------------------------------------------------------- SVP

    def generate_svp(
        self, ctx: LifecycleContext, report: TraceabilityReport
    ) -> LifecycleDocument:
        body = "\n".join(
            [
                self._heading(ctx, "Software Verification Plan (SVP)"),
                self._program_table(ctx),
                "",
                "## 1. Verification Objectives",
                "",
                f"All DO-178C **{ctx.dal_level}** verification objectives "
                "(Tables A-3 through A-7) are addressed by the DVE pipeline:",
                "",
                "- **Reviews and Analyses** — Constitutional AI and "
                "Constraint Geometry Engine (Phase 1 prerequisite).",
                "- **Test Generation** — Coder Agent under HITL approval.",
                "- **Test Execution** — sandbox runner.",
                "- **Coverage Analysis** — DVE coverage gate (Phase 2).",
                "- **Formal Methods** — DVE formal verification gate "
                "(Phase 3, Z3 SMT, DO-333 supplement).",
                "- **Independence** — HITL approval (Phase 1 prerequisite).",
                "",
                "## 2. Coverage Strategy",
                "",
                "| DAL | Statement | Decision | MC/DC | Object Code |",
                "|-----|-----------|----------|-------|-------------|",
                "| A   | 100%      | 100%     | 100%  | Required    |",
                "| B   | 100%      | 100%     | 100%  | Not required |",
                "| C   | 100%      | 100%     | n/a   | Not required |",
                "| D   | 100%      | n/a      | n/a   | Not required |",
                "",
                "## 3. Test Independence",
                "",
                "Tests run in isolated sandboxes (`src/services/sandbox_*`) "
                "with no shared state with development environments. "
                "Test authors cannot also be code authors for any DAL A "
                "or DAL B requirement.",
                "",
                self._gap_summary("Verification gaps", report),
                "",
                self._footer(ctx),
            ]
        )
        return LifecycleDocument(
            name="SVP",
            title="Software Verification Plan",
            content=body,
        )

    # ------------------------------------------------------------- SQAP

    def generate_sqap(
        self, ctx: LifecycleContext, report: TraceabilityReport
    ) -> LifecycleDocument:
        body = "\n".join(
            [
                self._heading(ctx, "Software Quality Assurance Plan (SQAP)"),
                self._program_table(ctx),
                "",
                "## 1. SQA Activities",
                "",
                "- Process audit of every DVE pipeline run (audit records "
                "in DynamoDB).",
                "- Configuration audit of every merged commit.",
                "- Independence audit: HITL reviewers must not have "
                "authored the patch.",
                "- Tool qualification audit of every TQL-2 / TQL-5 tool.",
                "",
                "## 2. Records",
                "",
                "Every DVE run produces an immutable audit record. The "
                "auditor's archive sink (`InMemoryArchiveSink` in dev, "
                "`FileSystemArchiveSink` for on-prem, S3 sink in cloud) "
                "is the system of record.",
                "",
                "## 3. Non-Conformance",
                "",
                "Failed gates produce non-conformance reports. The DVE "
                "auditor flags these via `ArchiveOutcome.FAILED` and the "
                "operator must reconcile before the patch can proceed.",
                "",
                self._footer(ctx),
            ]
        )
        return LifecycleDocument(
            name="SQAP",
            title="Software Quality Assurance Plan",
            content=body,
        )

    # -------------------------------------------------------------- SAS

    def generate_sas(
        self, ctx: LifecycleContext, report: TraceabilityReport
    ) -> LifecycleDocument:
        body = "\n".join(
            [
                self._heading(ctx, "Software Accomplishment Summary (SAS)"),
                self._program_table(ctx),
                "",
                "## 1. Summary",
                "",
                f"This SAS reports the as-built state of the {ctx.system} "
                "software at certification submission.",
                "",
                "## 2. Compliance with PSAC",
                "",
                "All planned activities documented in the PSAC have "
                "been completed except as noted in §4 (Open Issues).",
                "",
                "## 3. Quantitative Results",
                "",
                f"- Requirements: {report.requirement_count}",
                f"- Artefacts: {report.artefact_count}",
                f"- Trace edges: {report.edge_count}",
                f"- Forward gaps: {len(report.forward_gaps)}",
                f"- Reverse gaps: {len(report.reverse_gaps)}",
                f"- Coverage gate verdict: see `docs/certification/{ctx.program_id}/coverage_gate.md`",
                f"- Formal verification verdict: see `docs/certification/{ctx.program_id}/formal_gate.md`",
                "",
                self._gap_summary("Open issues at submission", report),
                "",
                "## 5. Conclusion",
                "",
                "The software has been developed and verified per the DO-178C "
                f"objectives applicable to {ctx.dal_level} and the DVE "
                "output-verification argument has been independently reviewed "
                f"by the DER ({ctx.cognizant_der or 'TBD'}).",
                "",
                self._footer(ctx),
            ]
        )
        return LifecycleDocument(
            name="SAS",
            title="Software Accomplishment Summary",
            content=body,
        )

    # --------------------------------------------------------- common helpers

    @staticmethod
    def _heading(ctx: LifecycleContext, title: str) -> str:
        return (
            f"# {title}\n\n"
            f"**Program:** {ctx.program_name} ({ctx.program_id})  \n"
            f"**Revision:** {ctx.revision}  \n"
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%MZ')}  \n"
        )

    @staticmethod
    def _program_table(ctx: LifecycleContext) -> str:
        rows: list[str] = [
            "| Field | Value |",
            "|-------|-------|",
            f"| Aircraft | {ctx.aircraft} |",
            f"| System | {ctx.system} |",
            f"| DAL Level | {ctx.dal_level} |",
            f"| Cognizant ACO | {ctx.cognizant_aco or '(TBD)'} |",
            f"| Cognizant DER | {ctx.cognizant_der or '(TBD)'} |",
            f"| Project URL | {ctx.project_url or '(TBD)'} |",
        ]
        for key, value in ctx.extra:
            rows.append(f"| {key} | {value} |")
        return "\n".join(rows)

    @staticmethod
    def _gap_summary(title: str, report: TraceabilityReport) -> str:
        if report.is_complete:
            return f"## {title}\n\n_No open findings._\n"
        lines = [f"## {title}\n"]
        if report.forward_gaps:
            lines.append("### Forward gaps\n")
            for gap in report.forward_gaps:
                lines.append(
                    f"- `{gap.node_id}` ({gap.node_type}) — {gap.description}"
                )
            lines.append("")
        if report.reverse_gaps:
            lines.append("### Reverse gaps\n")
            for gap in report.reverse_gaps:
                lines.append(
                    f"- `{gap.node_id}` ({gap.node_type}) — {gap.description}"
                )
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _footer(ctx: LifecycleContext) -> str:
        return (
            "---\n"
            f"_Authored by {ctx.authored_by}. This is an auto-generated "
            f"draft; sections marked TBD require human authorship before "
            "DER review._\n"
        )
