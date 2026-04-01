#!/usr/bin/env python3
"""
ADR-082 PydanticAI Integration Analysis - PDF Generator

Generates a professional PDF document containing the complete analysis
from all four specialist agents (AWS Architecture, Systems Architecture,
Security Analysis, Product Strategy).
"""

import os
from datetime import date

from reportlab.lib.colors import Color, HexColor, black, lightgrey, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import Flowable

# ─── Color Palette (Aura Brand) ──────────────────────────────────────────────
AURA_BLUE = HexColor("#3B82F6")
AURA_DARK = HexColor("#1E293B")
AURA_SLATE = HexColor("#475569")
AURA_LIGHT = HexColor("#F1F5F9")
AURA_GREEN = HexColor("#10B981")
AURA_RED = HexColor("#DC2626")
AURA_AMBER = HexColor("#F59E0B")
AURA_ORANGE = HexColor("#EA580C")
TABLE_HEADER_BG = HexColor("#1E40AF")
TABLE_ALT_ROW = HexColor("#EFF6FF")
TABLE_BORDER = HexColor("#CBD5E1")
SECTION_BG = HexColor("#DBEAFE")


# ─── Custom Flowables ────────────────────────────────────────────────────────
class ColoredBox(Flowable):
    """A colored box with text for callouts."""

    def __init__(self, text, bg_color, text_color=black, width=None, padding=8):
        super().__init__()
        self.text = text
        self.bg_color = bg_color
        self.text_color = text_color
        self.box_width = width or 7.0 * inch
        self.padding = padding

    def wrap(self, availWidth, availHeight):
        self.box_width = min(self.box_width, availWidth)
        return (self.box_width, 30)

    def draw(self):
        self.canv.setFillColor(self.bg_color)
        self.canv.roundRect(0, 0, self.box_width, 26, 4, fill=1, stroke=0)
        self.canv.setFillColor(self.text_color)
        self.canv.setFont("Helvetica-Bold", 9)
        self.canv.drawString(self.padding, 8, self.text)


# ─── Styles ──────────────────────────────────────────────────────────────────
def build_styles():
    styles = getSampleStyleSheet()

    styles.add(
        ParagraphStyle(
            name="DocTitle",
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=28,
            textColor=AURA_DARK,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="DocSubtitle",
            fontName="Helvetica",
            fontSize=12,
            leading=16,
            textColor=AURA_SLATE,
            spaceAfter=20,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionH1",
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=22,
            textColor=AURA_DARK,
            spaceBefore=20,
            spaceAfter=10,
            borderColor=AURA_BLUE,
            borderWidth=2,
            borderPadding=(0, 0, 4, 0),
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionH2",
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=18,
            textColor=HexColor("#1E40AF"),
            spaceBefore=14,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionH3",
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=AURA_SLATE,
            spaceBefore=10,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodyText2",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=AURA_DARK,
            spaceAfter=6,
            alignment=TA_JUSTIFY,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletItem",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=AURA_DARK,
            leftIndent=18,
            spaceAfter=3,
            bulletIndent=6,
            bulletFontName="Helvetica",
            bulletFontSize=9,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CriticalText",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=AURA_RED,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=AURA_DARK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableCellBold",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=AURA_DARK,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=11,
            textColor=white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="FooterText",
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=AURA_SLATE,
            alignment=TA_CENTER,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Callout",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=13,
            textColor=AURA_DARK,
            backColor=AURA_LIGHT,
            borderColor=AURA_BLUE,
            borderWidth=1,
            borderPadding=8,
            spaceBefore=8,
            spaceAfter=8,
        )
    )
    return styles


# ─── Table Helpers ───────────────────────────────────────────────────────────
def make_table(headers, rows, col_widths=None, styles_obj=None):
    """Build a professional table with alternating row colors."""
    s = styles_obj

    header_cells = [Paragraph(h, s["TableHeader"]) for h in headers]
    data = [header_cells]

    for row in rows:
        cells = []
        for i, cell in enumerate(row):
            if i == 0:
                cells.append(Paragraph(str(cell), s["TableCellBold"]))
            else:
                cells.append(Paragraph(str(cell), s["TableCell"]))
        data.append(cells)

    if col_widths is None:
        available = 7.0 * inch
        col_widths = [available / len(headers)] * len(headers)

    t = Table(data, colWidths=col_widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
    ]

    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))

    t.setStyle(TableStyle(style_commands))
    return t


def make_risk_table(findings, styles_obj):
    """Build a risk-rated findings table with color-coded severity."""
    s = styles_obj
    headers = ["#", "Finding", "Risk Rating", "Net Risk After Mitigation"]
    header_cells = [Paragraph(h, s["TableHeader"]) for h in headers]
    data = [header_cells]

    risk_colors = {
        "CRITICAL": AURA_RED,
        "HIGH": AURA_ORANGE,
        "MEDIUM": AURA_AMBER,
        "LOW": AURA_GREEN,
    }

    for row in findings:
        num, finding, rating, net_risk = row
        rating_color = risk_colors.get(rating, black)
        net_color = risk_colors.get(
            net_risk.split(" ")[0] if " " in net_risk else net_risk, black
        )

        cells = [
            Paragraph(str(num), s["TableCellBold"]),
            Paragraph(finding, s["TableCell"]),
            Paragraph(
                f'<font color="#{rating_color.hexval()[2:]}">{rating}</font>',
                s["TableCellBold"],
            ),
            Paragraph(
                f'<font color="#{net_color.hexval()[2:]}">{net_risk}</font>',
                s["TableCellBold"],
            ),
        ]
        data.append(cells)

    widths = [0.4 * inch, 3.0 * inch, 1.2 * inch, 2.4 * inch]
    t = Table(data, colWidths=widths, repeatRows=1)

    style_commands = [
        ("BACKGROUND", (0, 0), (-1, 0), TABLE_HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), white),
        ("GRID", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        if i % 2 == 0:
            style_commands.append(("BACKGROUND", (0, i), (-1, i), TABLE_ALT_ROW))
    t.setStyle(TableStyle(style_commands))
    return t


# ─── Page Template ───────────────────────────────────────────────────────────
def header_footer(canvas, doc):
    canvas.saveState()

    # Header line
    canvas.setStrokeColor(AURA_BLUE)
    canvas.setLineWidth(2)
    canvas.line(0.75 * inch, 10.35 * inch, 7.75 * inch, 10.35 * inch)

    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(AURA_SLATE)
    canvas.drawString(0.75 * inch, 10.45 * inch, "Project Aura | ADR-082 Analysis")
    canvas.drawRightString(7.75 * inch, 10.45 * inch, "CONFIDENTIAL")

    # Footer
    canvas.setStrokeColor(TABLE_BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.6 * inch, 7.75 * inch, 0.6 * inch)

    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(AURA_SLATE)
    canvas.drawString(
        0.75 * inch, 0.42 * inch, f"Aenea Labs | {date.today().isoformat()}"
    )
    canvas.drawCentredString(
        4.25 * inch, 0.42 * inch, "ADR-082: PydanticAI Agent Framework Integration"
    )
    canvas.drawRightString(7.75 * inch, 0.42 * inch, f"Page {doc.page}")

    canvas.restoreState()


# ─── Document Content ────────────────────────────────────────────────────────
def build_document():
    output_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "ADR-082-pydanticai-integration-analysis.pdf",
    )

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        topMargin=0.9 * inch,
        bottomMargin=0.8 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    s = build_styles()
    story = []

    # ═══════════════════════════════════════════════════════════════════════
    # COVER PAGE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Spacer(1, 1.5 * inch))
    story.append(
        Paragraph("ADR-082: PydanticAI Agent Framework Integration", s["DocTitle"])
    )
    story.append(
        Paragraph("Multi-Agent Architecture Analysis Report", s["DocSubtitle"])
    )
    story.append(HRFlowable(width="100%", thickness=2, color=AURA_BLUE))
    story.append(Spacer(1, 0.3 * inch))

    cover_data = [
        ["Document Type", "Architecture Decision Record - Pre-Decision Analysis"],
        ["Classification", "Internal - Architecture Review"],
        ["Date", date.today().isoformat()],
        ["Project", "Project Aura - Autonomous AI SaaS Platform"],
        ["Organization", "Aenea Labs"],
        ["Subject", "Integration of PydanticAI as Agent Orchestration Framework"],
        [
            "Analysts",
            "AWS AI/SaaS Architect, Senior Systems Architect,\nCybersecurity Analyst, Senior AI Product Manager",
        ],
    ]
    cover_table = Table(cover_data, colWidths=[1.8 * inch, 5.2 * inch])
    cover_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("TEXTCOLOR", (0, 0), (0, -1), AURA_SLATE),
                ("TEXTCOLOR", (1, 0), (1, -1), AURA_DARK),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, TABLE_BORDER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(cover_table)

    story.append(Spacer(1, 0.5 * inch))

    # Analyst summary box
    story.append(Paragraph("Analysis Scope", s["SectionH2"]))
    scope_items = [
        "AWS Infrastructure & Deployment Impact (Architecture Review)",
        "Systems Architecture & Migration Strategy (Systems Architecture Review)",
        "Security Threat Model & Risk Assessment (Security Review)",
        "Product Strategy & Competitive Analysis (Product Strategy Review)",
    ]
    for item in scope_items:
        story.append(Paragraph(f"\u2022  {item}", s["BulletItem"]))

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # TABLE OF CONTENTS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Table of Contents", s["SectionH1"]))
    story.append(Spacer(1, 0.1 * inch))

    toc_entries = [
        ("1.", "Executive Summary & Cross-Agent Synthesis", "3"),
        ("2.", "AWS Infrastructure Analysis Architecture", "5"),
        ("3.", "Systems Architecture Analysis Systems Review", "9"),
        ("4.", "Security Threat Model Security Review", "15"),
        ("5.", "Product Strategy Analysis Product Review", "21"),
        ("6.", "Consolidated Recommendations", "25"),
        ("A.", "Appendix: MITRE ATT&CK Mapping", "27"),
        ("B.", "Appendix: Key Files Referenced", "28"),
    ]
    toc_data = [
        [
            Paragraph(e[0], s["TableCellBold"]),
            Paragraph(e[1], s["TableCell"]),
            Paragraph(e[2], s["TableCell"]),
        ]
        for e in toc_entries
    ]
    toc_table = Table(toc_data, colWidths=[0.4 * inch, 5.6 * inch, 1.0 * inch])
    toc_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, TABLE_BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(toc_table)

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 1: EXECUTIVE SUMMARY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(
        Paragraph("1. Executive Summary & Cross-Agent Synthesis", s["SectionH1"])
    )
    story.append(Spacer(1, 0.1 * inch))

    story.append(
        Paragraph(
            "Four specialist agents independently analyzed the proposal to integrate PydanticAI "
            "into Project Aura's agent orchestration layer. PydanticAI is a production-stable, "
            "type-safe Python framework from the Pydantic team supporting 33 LLM providers, "
            "structured output enforcement, multi-agent patterns, MCP client/server, and "
            "OpenTelemetry observability. This section synthesizes all four perspectives.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("1.1 Recommendation Spectrum", s["SectionH2"]))
    story.append(
        make_table(
            ["Agent", "Role", "Recommendation", "Depth", "Timeline"],
            [
                [
                    "Product Review",
                    "Product Strategy",
                    "Thin compatibility adapter only",
                    "Shallowest",
                    "~7 weeks",
                ],
                [
                    "Architecture Review",
                    "AWS Architecture",
                    "New agents PydanticAI-native, adapter for existing",
                    "Moderate",
                    "~9-13 eng-weeks",
                ],
                [
                    "Security Review",
                    "Security",
                    "Proceed contingent on 24 mitigations",
                    "Scope-agnostic",
                    "4 security phases",
                ],
                [
                    "Systems Review",
                    "Systems Architecture",
                    "Full strangler fig, pydantic-graph replaces workflow",
                    "Deepest",
                    "24 weeks (5 phases)",
                ],
            ],
            col_widths=[0.6 * inch, 1.1 * inch, 2.3 * inch, 1.0 * inch, 2.0 * inch],
            styles_obj=s,
        )
    )
    story.append(Spacer(1, 0.1 * inch))

    story.append(
        Paragraph("1.2 Universal Consensus (All 4 Agents Agree)", s["SectionH2"])
    )
    consensus_items = [
        "Never do a Big Bang replacement - too risky for 22,317+ tests and 415,500+ LOC",
        "Never bypass BedrockLLMService - must preserve cost controls, caching, rate limiting",
        "Never enable Logfire - sends telemetry externally, violates GovCloud/compliance",
        "AuraModelFactory required - enforce Bedrock-only, block all 32 other providers",
        "Capability Governance (ADR-066) must wrap all PydanticAI tools - no ungoverned execution",
        "GovCloud fully compatible with proper configuration (IRSA, no Logfire, egress controls)",
        "Shared service layer stays untouched (Context, Sandbox, Bedrock, Titan Memory, etc.)",
        "VPC egress controls must block outbound to non-Bedrock LLM endpoints",
    ]
    for item in consensus_items:
        story.append(Paragraph(f"\u2022  {item}", s["BulletItem"]))

    story.append(Spacer(1, 0.1 * inch))
    story.append(Paragraph("1.3 Key Disagreement: Integration Depth", s["SectionH2"]))
    story.append(
        make_table(
            ["Decision Point", "Product Review", "Architecture", "Systems Review"],
            [
                ["Build new agents with PydanticAI?", "No", "Yes", "Yes"],
                [
                    "Migrate existing agents?",
                    "No",
                    "Phase 2 (wrap)",
                    "Phase 2-3 (rewrite)",
                ],
                [
                    "Use pydantic-graph for workflows?",
                    "No",
                    "Evaluate Phase 3",
                    "Yes, Phase 2+",
                ],
                ["Replace WorkflowPhase state machine?", "No", "Defer", "Yes"],
                [
                    "Replace AgentCheckpoint?",
                    "No",
                    "Defer",
                    "Yes (typed Pydantic state)",
                ],
                [
                    "Remove legacy orchestrator?",
                    "Never",
                    "Maybe Phase 3",
                    "Phase 5 (week 21-24)",
                ],
                ["Market 'PydanticAI-powered'?", "Absolutely not", "N/A", "N/A"],
            ],
            col_widths=[1.8 * inch, 1.4 * inch, 1.4 * inch, 2.4 * inch],
            styles_obj=s,
        )
    )

    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "1.4 Recommended Path: Architecture-Systems Hybrid Gated by Security Phases",
            s["SectionH2"],
        )
    )
    story.append(
        Paragraph(
            "Start with the pragmatic scope (adapter + new agents) and Security Phase 1 security "
            "prerequisites (AuraModelFactory, egress controls, tool wrapper). Use the technical "
            "blueprint for agent typing, tool tiering, and graph design. Adopt the strangler fig "
            "facade with feature flags for safe rollout. Heed the warning: keep this as an "
            "implementation detail, not a marketing feature. Gate pydantic-graph adoption on Phase 1 "
            "Scanner success (Architecture Phase 3 decision gate).",
            s["BodyText2"],
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 2: TARA - AWS INFRASTRUCTURE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("2. AWS Infrastructure Analysis", s["SectionH1"]))
    story.append(Paragraph("Analyst: Architecture Review", s["DocSubtitle"]))

    story.append(Paragraph("2.1 Core Recommendation", s["SectionH2"]))
    story.append(
        Paragraph(
            "Selective Adoption via Adapter Layer (NOT Full Replacement). Adopt PydanticAI as "
            "the agent definition and execution framework for new agents, while wrapping existing "
            "agents behind a PydanticAI-compatible adapter layer. Do NOT rip-and-replace the "
            "existing System2Orchestrator or MetaOrchestrator in the initial phase.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("2.2 Infrastructure Impact Assessment", s["SectionH2"]))
    story.append(
        make_table(
            ["Component", "Current State", "Change Required"],
            [
                [
                    "EKS Pods",
                    "Python 3.11 containers",
                    "Add pydantic-ai[bedrock] to requirements - no container changes",
                ],
                [
                    "Bedrock VPC Endpoint",
                    "Already deployed (ADR-002)",
                    "None - PydanticAI uses boto3 under the hood",
                ],
                [
                    "Neptune/OpenSearch",
                    "Graph + vector via dnsmasq",
                    "Exposed as PydanticAI tools via dependency injection",
                ],
                [
                    "IRSA Roles",
                    "Bedrock invoke permissions exist",
                    "None - same IAM permissions apply",
                ],
                [
                    "ECR Images",
                    "Private base images (ADR-020)",
                    "Rebuild with updated requirements.txt",
                ],
                [
                    "CloudFormation",
                    "140 templates deployed",
                    "Zero template changes for Phase 1",
                ],
            ],
            col_widths=[1.3 * inch, 2.2 * inch, 3.5 * inch],
            styles_obj=s,
        )
    )

    story.append(
        Paragraph(
            "2.3 Critical Architecture Decision: BedrockLLMService Adapter",
            s["SectionH2"],
        )
    )
    story.append(
        Paragraph(
            "PydanticAI must NEVER bypass BedrockLLMService and call Bedrock directly. Instead, "
            "a PydanticAI model adapter must delegate to BedrockLLMService to preserve: tiered "
            "model routing (ADR-015), cost controls and budget enforcement (ADR-008), rate limiting "
            "per agent, semantic caching (ADR-029 Phase 1.3), guardrail integration, and token "
            "tracking with CloudWatch metrics. If PydanticAI agents bypass BedrockLLMService, "
            "all existing cost controls, caching, and observability are lost.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("2.4 Deployment Strategy", s["SectionH2"]))
    story.append(
        make_table(
            ["Approach", "Recommendation", "Rationale"],
            [
                [
                    "Sidecar pattern",
                    "REJECT",
                    "PydanticAI is not a runtime or daemon; it is a library",
                ],
                [
                    "New microservice",
                    "REJECT",
                    "Adds network latency and operational complexity for zero benefit",
                ],
                [
                    "In-process library",
                    "ACCEPT",
                    "Import and use within existing agent pods",
                ],
                [
                    "Replace orchestrator",
                    "REJECT (Phase 1)",
                    "Too much risk; defer to Phase 3",
                ],
            ],
            col_widths=[1.4 * inch, 1.2 * inch, 4.4 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("2.5 GovCloud Compatibility", s["SectionH2"]))
    story.append(
        make_table(
            ["Concern", "Assessment"],
            [
                [
                    "Bedrock provider uses boto3",
                    "boto3 works in GovCloud; uses ${AWS::Partition} ARN format automatically",
                ],
                ["Bedrock availability", "Available in us-gov-west-1 (confirmed)"],
                [
                    "Model availability",
                    "Claude 3.5 Sonnet available in GovCloud Bedrock",
                ],
                ["VPC Endpoint", "Bedrock Runtime VPC endpoint available in GovCloud"],
                [
                    "FIPS 140-2",
                    "boto3 supports FIPS endpoints; PydanticAI does not bypass this",
                ],
                [
                    "External network calls",
                    "PydanticAI does not phone home or call external services",
                ],
                [
                    "Air-gapped deployment",
                    "PydanticAI is pip-installable from private PyPI mirror",
                ],
                [
                    "Logfire (PROHIBITED)",
                    "Must NOT be enabled in GovCloud - sends telemetry externally",
                ],
            ],
            col_widths=[1.8 * inch, 5.2 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("2.6 Three-Phase Rollout", s["SectionH2"]))
    story.append(
        make_table(
            ["Phase", "Timeline", "Scope", "Effort"],
            [
                [
                    "Phase 1: Foundation",
                    "Q2 2026",
                    "Adapter layer, tool registry, deps types, 1-2 new agents",
                    "3-4 eng-weeks",
                ],
                [
                    "Phase 2: Migration",
                    "Q3 2026",
                    "Wrap existing 12+ spawnable leaf agents",
                    "4-6 eng-weeks",
                ],
                [
                    "Phase 3: Evaluation",
                    "Q4 2026",
                    "Evaluate pydantic-graph vs MetaOrchestrator (decision gate)",
                    "2-3 eng-weeks",
                ],
            ],
            col_widths=[1.4 * inch, 0.9 * inch, 3.2 * inch, 1.5 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("2.7 Cost Estimate", s["SectionH2"]))
    story.append(
        make_table(
            ["Item", "One-Time Cost", "Monthly Recurring"],
            [
                ["PydanticAI library", "$0 (MIT license)", "$0"],
                ["Phase 1 development", "3-4 engineer-weeks", "N/A"],
                ["Phase 2 migration", "4-6 engineer-weeks", "N/A"],
                ["Phase 3 evaluation", "2-3 engineer-weeks", "N/A"],
                ["Container image rebuild", "Negligible (~10MB)", "$0"],
                ["Bedrock API costs", "No change", "No change"],
                ["EKS compute", "No change", "No change"],
            ],
            col_widths=[2.5 * inch, 2.0 * inch, 2.5 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("2.8 Risks and Mitigations", s["SectionH2"]))
    story.append(
        make_table(
            ["Risk", "Severity", "Likelihood", "Mitigation"],
            [
                [
                    "PydanticAI breaking changes",
                    "Medium",
                    "Medium",
                    "Pin exact version; adapter layer isolates impact",
                ],
                [
                    "Bedrock provider feature gaps",
                    "High",
                    "Medium",
                    "Adapter wraps BedrockLLMService, not raw Bedrock",
                ],
                [
                    "Team unfamiliarity",
                    "Low",
                    "High",
                    "Pydantic v2 already in codebase; same patterns",
                ],
                [
                    "pydantic-graph immaturity",
                    "Medium",
                    "High",
                    "Do NOT use in Phase 1/2; evaluate in Phase 3",
                ],
                [
                    "Logfire in GovCloud",
                    "High",
                    "Low",
                    "Env validator (ADR-062) blocks Logfire config",
                ],
                [
                    "Dependency conflicts",
                    "Low",
                    "Low",
                    "Aura already uses pydantic>=2.10.0; compatible",
                ],
            ],
            col_widths=[1.5 * inch, 0.7 * inch, 0.8 * inch, 3.0 * inch],
            styles_obj=s,
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 3: MACY - SYSTEMS ARCHITECTURE
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("3. Systems Architecture Analysis", s["SectionH1"]))
    story.append(
        Paragraph("Analyst: Systems Architecture Review", s["DocSubtitle"])
    )

    story.append(
        Paragraph(
            "3.1 Integration Strategy: Strangler Fig with Orchestrator Facade",
            s["SectionH2"],
        )
    )
    story.append(
        Paragraph(
            "The existing system has three deeply intertwined orchestration layers: (1) agent_orchestrator.py "
            "(V7 workflow engine with WorkflowPhase state machine), (2) meta_orchestrator.py (dynamic spawning "
            "with AgentCapability routing and AutonomyLevel enforcement), and (3) orchestration_service.py "
            "(SQS/DynamoDB job management). PydanticAI replaces layers 1 and 2 but NOT layer 3. The "
            "Orchestrator Facade routes by severity, tenant, and workflow type via feature flags.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("3.2 Agent Type Mapping", s["SectionH2"]))
    story.append(
        make_table(
            [
                "Agent",
                "DepsT (Dependencies)",
                "OutputT (Structured Output)",
                "Current Return",
            ],
            [
                [
                    "CoderAgent",
                    "ContextRetrieval, Bedrock, Monitor, RLM, CapabilityGov",
                    "PatchProposal (patch_id, diff, affected_files, confidence, alternatives)",
                    "dict[str, Any]",
                ],
                [
                    "ReviewerAgent",
                    "ContextRetrieval, Bedrock, ConstitutionalAI, Guardrails, Reflection",
                    "ReviewDecision (decision, findings, severity_max, revision_notes)",
                    "dict[str, Any]",
                ],
                [
                    "ValidatorAgent",
                    "Sandbox, Monitor, AnomalyDetector, RuntimeSecurity",
                    "ValidationResult (verdict, syntax_valid, test_results, anomalies)",
                    "dict[str, Any]",
                ],
            ],
            col_widths=[1.0 * inch, 2.0 * inch, 2.5 * inch, 1.5 * inch],
            styles_obj=s,
        )
    )

    story.append(
        Paragraph("3.3 Tool Tier Design (Aligned with ADR-066)", s["SectionH2"])
    )
    story.append(
        make_table(
            ["Tier", "Classification", "Tools", "Governance"],
            [
                [
                    "1",
                    "Read-Only",
                    "query_code_graph, search_semantic, retrieve_hybrid_context, check_provenance",
                    "No approval required",
                ],
                [
                    "2",
                    "Write",
                    "generate_code, run_security_check, apply_self_reflection",
                    "Logged, audited",
                ],
                [
                    "3",
                    "Privileged",
                    "provision_sandbox, execute_in_sandbox, destroy_sandbox",
                    "Rate-limited, budget-checked via prepare()",
                ],
                [
                    "4",
                    "Critical",
                    "request_human_approval, deploy_patch",
                    "Mandatory HITL via DeferredToolRequests",
                ],
            ],
            col_widths=[0.5 * inch, 1.0 * inch, 3.2 * inch, 2.3 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("3.4 pydantic-graph Workflow DAG", s["SectionH2"]))
    story.append(
        Paragraph(
            "The linear WorkflowPhase enum (INIT -> PLANNING -> MEMORY_LOAD -> CONTEXT_RETRIEVAL -> "
            "CODE_GENERATION -> SECURITY_REVIEW -> VALIDATION -> REMEDIATION -> MEMORY_STORE -> COMPLETED) "
            "becomes a branching DAG with conditional routing:",
            s["BodyText2"],
        )
    )
    story.append(
        make_table(
            ["Node", "Purpose", "Transitions", "New/Existing"],
            [
                [
                    "TriggerNode",
                    "Initialize workflow from external event",
                    "-> PlanningNode",
                    "Existing (INIT)",
                ],
                [
                    "PlanningNode",
                    "Decompose task into sub-tasks",
                    "-> MemoryLoadNode",
                    "Existing (PLANNING)",
                ],
                [
                    "MemoryLoadNode",
                    "Titan Neural Memory retrieval (ADR-024)",
                    "-> ContextNode",
                    "Existing (MEMORY_LOAD)",
                ],
                [
                    "ContextNode",
                    "Hybrid GraphRAG query",
                    "-> TriageNode",
                    "Existing (CONTEXT_RETRIEVAL)",
                ],
                [
                    "TriageNode",
                    "Route by severity: LOW/MED vs HIGH/CRITICAL",
                    "-> AutoFixNode or CoderNode",
                    "NEW",
                ],
                [
                    "AutoFixNode",
                    "Template-based fixes for known patterns",
                    "-> ReviewNode",
                    "NEW",
                ],
                [
                    "CoderNode",
                    "LLM-powered patch generation",
                    "-> ReviewNode",
                    "Existing (CODE_GENERATION)",
                ],
                [
                    "ReviewNode",
                    "Security review with self-reflection",
                    "-> ValidateNode / CoderNode / ArchiveNode",
                    "Existing (SECURITY_REVIEW)",
                ],
                [
                    "ValidateNode",
                    "AST parsing + sandbox testing",
                    "-> ConstraintNode / DiagnoseNode",
                    "Existing (VALIDATION)",
                ],
                [
                    "ConstraintNode",
                    "ADR-081 deterministic coherence gate",
                    "-> HITLGateNode / CoderNode",
                    "NEW",
                ],
                [
                    "DiagnoseNode",
                    "Analyze failure, retry Coder",
                    "-> CoderNode",
                    "Existing (REMEDIATION)",
                ],
                [
                    "HITLGateNode",
                    "Human approval via DeferredToolRequests",
                    "-> MemoryStoreNode / ArchiveNode",
                    "Enhanced",
                ],
                [
                    "MemoryStoreNode",
                    "Titan Neural Memory persistence",
                    "-> DeployNode",
                    "Existing (MEMORY_STORE)",
                ],
                ["DeployNode", "Apply validated patch", "-> END", "NEW"],
            ],
            col_widths=[1.2 * inch, 2.0 * inch, 2.0 * inch, 1.8 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("3.5 Context Service Integration", s["SectionH2"]))
    story.append(
        Paragraph(
            "Dual integration approach: (1) Internal agents use dependency injection via typed "
            "ContextRetrievalClient wrapper (faster, no HTTP overhead, type-safe), and (2) External "
            "consumers (IDE plugins, Palantir AIP) use MCP Server over SSE transport. Internal agents "
            "do NOT use MCP. Direct dependency injection is faster, type-safe, and simpler. MCP is "
            "exclusively for cross-process, cross-system communication.",
            s["BodyText2"],
        )
    )

    story.append(
        Paragraph("3.6 State Management: RunContext vs Graph State", s["SectionH2"])
    )
    story.append(
        make_table(
            [
                "Aspect",
                "RunContext (Per-Agent-Run)",
                "RemediationWorkflowState (Per-Workflow)",
            ],
            [
                [
                    "Scope",
                    "Single agent invocation (seconds to minutes)",
                    "Entire remediation pipeline (hours to days)",
                ],
                [
                    "Persistence",
                    "NOT persisted (ephemeral)",
                    "DynamoDB checkpoint after every node",
                ],
                [
                    "Contains",
                    "DepsT, message history, usage",
                    "Accumulated results, control flow, audit trail",
                ],
                ["Replaces", "N/A (new concept)", "AgentCheckpoint dataclass"],
                [
                    "Serialization",
                    "Automatic by PydanticAI",
                    "model_dump_json() / model_validate_json()",
                ],
            ],
            col_widths=[1.3 * inch, 2.85 * inch, 2.85 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("3.7 Five-Phase Migration Plan", s["SectionH2"]))
    story.append(
        make_table(
            ["Phase", "Weeks", "Scope", "Risk", "Rollback"],
            [
                [
                    "0: Foundation",
                    "1-3",
                    "Package structure, models, facade (100% legacy)",
                    "Minimal",
                    "Delete new package",
                ],
                [
                    "1: Scanner",
                    "4-6",
                    "First PydanticAI agent, Tier 1 tools, 10% LOW severity",
                    "Low",
                    "Feature flag to 0%",
                ],
                [
                    "2: Coder+Reviewer",
                    "7-11",
                    "Core agent pair, Tier 2 tools, LOW severity",
                    "Medium",
                    "Feature flag to legacy",
                ],
                [
                    "3: Validator+HITL",
                    "12-15",
                    "Complete pipeline, Tier 3-4, MEDIUM severity added",
                    "Medium",
                    "Feature flag fallback",
                ],
                [
                    "4: Full Migration",
                    "16-20",
                    "All severities, MCP server, legacy deprecated",
                    "High (mitigated)",
                    "Per-tenant flags",
                ],
                [
                    "5: Cleanup",
                    "21-24",
                    "Remove legacy, archive, update docs",
                    "Low",
                    "Git revert",
                ],
            ],
            col_widths=[1.2 * inch, 0.6 * inch, 2.4 * inch, 1.0 * inch, 1.8 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("3.8 Testing Strategy: ~1,200 New Tests", s["SectionH2"]))
    story.append(
        make_table(
            ["Layer", "Tests", "What It Validates"],
            [
                [
                    "L1: Pydantic Models",
                    "~200",
                    "Serialization, deserialization, from_dataclass() converters, schema migration",
                ],
                [
                    "L2: Tool Unit Tests",
                    "~300",
                    "Each tool with mock deps, budget limits, parallel execution, timeouts",
                ],
                [
                    "L3: Agent with TestModel",
                    "~150",
                    "Output matches OutputT, tool calls made, DI works, max_retries",
                ],
                [
                    "L4: Behavioral (FunctionModel)",
                    "~200",
                    "Context-dependent decisions, severity routing, policy violations",
                ],
                [
                    "L5: Graph Workflow",
                    "~250",
                    "Node transitions, revision loops, checkpoint/resume, full traversal",
                ],
                [
                    "L6: Integration",
                    "~100",
                    "Full pipeline with mocks, MCP protocol, DynamoDB suspend/resume",
                ],
            ],
            col_widths=[1.8 * inch, 0.6 * inch, 4.6 * inch],
            styles_obj=s,
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 4: SALLY - SECURITY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(
        Paragraph("4. Security Threat Model & Risk Assessment", s["SectionH1"])
    )
    story.append(Paragraph("Analyst: Security Review", s["DocSubtitle"]))

    story.append(
        Paragraph(
            "Overall Risk Rating: MEDIUM (manageable with mitigations). Recommendation: Proceed "
            "with integration, contingent on implementing all Critical and High mitigations before "
            "production deployment.",
            s["Callout"],
        )
    )

    story.append(Paragraph("4.1 Consolidated Risk Matrix", s["SectionH2"]))
    story.append(
        make_risk_table(
            [
                ["1", "Supply Chain (new PyPI dependency)", "MEDIUM", "LOW"],
                ["2", "Prompt Injection Surface", "MEDIUM", "LOW"],
                ["3", "Agent Confusion Mitigation", "MEDIUM", "LOW"],
                ["4", "Tool Execution Bypasses ADR-066", "HIGH", "MEDIUM"],
                ["5", "MCP Network Exposure", "HIGH", "MEDIUM"],
                ["6", "HITL Bypass (timing/replay attacks)", "HIGH", "LOW"],
                ["7", "Data Exfiltration (33 LLM providers)", "CRITICAL", "LOW"],
                ["8", "Secrets Management", "HIGH", "LOW"],
                ["9", "Audit Trail (NIST 800-53 AU controls)", "MEDIUM", "LOW"],
                ["10", "Sandbox Container Escape", "HIGH", "MEDIUM"],
            ],
            styles_obj=s,
        )
    )

    story.append(
        Paragraph(
            "4.2 CRITICAL Finding: Data Exfiltration via Multi-Provider Support",
            s["SectionH2"],
        )
    )
    story.append(
        Paragraph(
            "PydanticAI supports 33 LLM providers. A single-line configuration change could route "
            "all agent interactions - including proprietary code, vulnerability details, and customer "
            "data - to OpenAI/Anthropic/Google instead of remaining within the AWS Bedrock boundary. "
            "This constitutes the highest-severity finding because Project Aura processes entire "
            "enterprise codebases.",
            s["CriticalText"],
        )
    )
    story.append(
        Paragraph(
            "Required mitigations (must implement before any PydanticAI code):",
            s["BodyText2"],
        )
    )
    critical_mitigations = [
        "M7.1: AuraModelFactory - The ONLY way to instantiate models, hardcoded to Bedrock-only",
        "M7.2: VPC egress controls - Security groups blocking outbound to api.openai.com, api.anthropic.com, etc.",
        "M7.3: Startup validation - Application refuses to start if any agent uses non-Bedrock provider",
        "M7.4: DNS monitoring - Alert on resolution attempts for non-Bedrock LLM domains",
    ]
    for m in critical_mitigations:
        story.append(Paragraph(f"\u2022  {m}", s["BulletItem"]))

    story.append(
        Paragraph(
            "4.3 HIGH Finding: Tool Execution Bypasses Capability Governance",
            s["SectionH2"],
        )
    )
    story.append(
        Paragraph(
            "PydanticAI has its own tool execution pathway that bypasses MCPToolMixin.invoke_tool() "
            "entirely. If PydanticAI tools call functions directly, they circumvent the Capability "
            "Enforcement Middleware (ADR-066). Every PydanticAI tool function MUST route through "
            "CapabilityEnforcementMiddleware.check() before executing. A mandatory PydanticAIToolWrapper "
            "decorator enforces this - no ungoverned tools can be registered.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("4.4 HIGH Finding: HITL Integrity", s["SectionH2"]))
    story.append(
        make_table(
            ["HITL Risk", "Severity", "Mitigation"],
            [
                [
                    "Approval replay",
                    "HIGH",
                    "Nonce/idempotency keys consumed on approval (M6.3)",
                ],
                [
                    "Timing attack",
                    "MEDIUM",
                    "Approval expiration TTL: 15min DANGEROUS, 60min CRITICAL (M6.4)",
                ],
                [
                    "Approver impersonation",
                    "HIGH",
                    "Cognito/JWT authentication on approval channel (M6.6)",
                ],
                [
                    "Bypass via non-deferred tools",
                    "CRITICAL",
                    "Mandatory DeferredToolRequests for CRITICAL tools (M6.2)",
                ],
                [
                    "Context mismatch",
                    "HIGH",
                    "Cryptographic hash binding of approval to execution payload (M6.5)",
                ],
            ],
            col_widths=[1.8 * inch, 0.8 * inch, 4.4 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("4.5 Security Implementation Roadmap", s["SectionH2"]))
    story.append(
        make_table(
            ["Phase", "When", "Key Mitigations"],
            [
                [
                    "1: Pre-Integration",
                    "Before ANY code",
                    "AuraModelFactory, VPC egress controls, PydanticAI tool wrapper, IRSA auth",
                ],
                [
                    "2: Core Integration",
                    "During implementation",
                    "Guardrails upstream, per-role agents, HITL/DynamicGrantManager, MCP NetworkPolicies, mTLS",
                ],
                [
                    "3: Hardening",
                    "Before production",
                    "Minimal extras install, SBOM attestation, strict result models, security audit layer",
                ],
                [
                    "4: Ongoing",
                    "Post-deployment",
                    "Nightly dependency audit, DNS monitoring, CloudWatch alerting, penetration test",
                ],
            ],
            col_widths=[1.3 * inch, 1.3 * inch, 4.4 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("4.6 NIST 800-53 AU Control Compliance", s["SectionH2"]))
    story.append(
        make_table(
            ["Control", "Requirement", "PydanticAI OTel Coverage", "Gap"],
            [
                [
                    "AU-2",
                    "Define auditable events",
                    "Partial - traces tool calls",
                    "Must trace ALL tool calls, not sampled",
                ],
                [
                    "AU-3",
                    "Content of records (who/what/when)",
                    "Partial - spans may lack agent ID",
                    "Add aura.agent.type, aura.tool.classification",
                ],
                [
                    "AU-6",
                    "Regular audit review",
                    "Not addressed",
                    "Requires CloudWatch/SIEM integration",
                ],
                [
                    "AU-9",
                    "Protect audit records",
                    "Depends on export destination",
                    "Must export to immutable store",
                ],
                [
                    "AU-11",
                    "Audit record retention",
                    "Depends on export destination",
                    "Configure 90-day minimum retention",
                ],
                [
                    "AU-12",
                    "Generate at all components",
                    "Partial - only instrumented paths",
                    "Must instrument all PydanticAI tool paths",
                ],
            ],
            col_widths=[0.6 * inch, 1.6 * inch, 1.9 * inch, 2.9 * inch],
            styles_obj=s,
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 5: SUE - PRODUCT STRATEGY
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("5. Product Strategy Analysis", s["SectionH1"]))
    story.append(
        Paragraph("Analyst: Product Strategy Review", s["DocSubtitle"])
    )

    story.append(Paragraph("5.1 Build vs. Adopt: ROI Analysis", s["SectionH2"]))
    story.append(
        Paragraph(
            "Aura's custom agent orchestration layer comprises ~43,000 lines of production code "
            "across 20+ agent classes, ~88,000 lines of tests, and deep integration with 12+ "
            "domain-specific services. Estimated replacement cost: $600K-$900K over 12-18 months, "
            "during which zero customer-facing features ship. ROI Verdict: Negative for full "
            "replacement.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("5.2 What Aura Already Has vs. PydanticAI", s["SectionH2"]))
    story.append(
        make_table(
            ["Capability", "PydanticAI Feature", "Aura Already Has It?"],
            [
                [
                    "Type-safe agent definitions",
                    "Pydantic models for I/O",
                    "YES - FastAPI + Pydantic v2",
                ],
                [
                    "Multi-model support",
                    "OpenAI, Anthropic, Bedrock",
                    "YES - BedrockLLMService with tiered routing",
                ],
                [
                    "Structured output streaming",
                    "Validated streaming",
                    "NO - gap identified",
                ],
                [
                    "MCP client integration",
                    "Built-in MCP support",
                    "YES - custom MCPGatewayClient + MCPToolServer",
                ],
                [
                    "HITL tool approval",
                    "ApprovalRequired exceptions",
                    "YES - HITLApprovalService with 4 autonomy levels",
                ],
                [
                    "Durable execution",
                    "Temporal integration",
                    "PARTIAL - AgentCheckpoint + DynamoDB",
                ],
                [
                    "A2A protocol",
                    "FastA2A library",
                    "YES - custom A2AGateway + A2AAgentRegistry",
                ],
                [
                    "Graph-based workflows",
                    "Type-hint graphs",
                    "NO - uses DAG in MetaOrchestrator",
                ],
                [
                    "Testing/evaluation",
                    "TestModel/FunctionModel",
                    "YES - AgentEvaluationService",
                ],
                ["Dependency injection", "RunContext DI", "PARTIAL - factory pattern"],
            ],
            col_widths=[1.5 * inch, 1.8 * inch, 3.7 * inch],
            styles_obj=s,
        )
    )

    story.append(
        Paragraph("5.3 Competitive Landscape: Framework Adoption", s["SectionH2"])
    )
    story.append(
        make_table(
            ["Competitor", "Framework", "Market Position"],
            [
                ["GitHub Copilot / Advanced Security", "Custom", "Market leader"],
                ["Snyk (DeepCode AI)", "Custom", "Enterprise security leader"],
                [
                    "AWS Security Agent (Bedrock AgentCore)",
                    "Custom (AWS SDK)",
                    "Cloud-native leader",
                ],
                ["Veracode Fix", "Custom", "Legacy SAST leader"],
                ["SonarQube AI", "Custom", "Code quality leader"],
                [
                    "Most Y-Combinator AI startups",
                    "LangChain/CrewAI",
                    "Early-stage, prototype-grade",
                ],
            ],
            col_widths=[2.2 * inch, 1.5 * inch, 3.3 * inch],
            styles_obj=s,
        )
    )
    story.append(
        Paragraph(
            "Key insight: No enterprise-grade AI security product uses PydanticAI, LangChain, or "
            "CrewAI as core orchestration. Successful teams use frameworks for prototyping, then "
            "replace with custom infrastructure. Aura has already completed this maturation arc.",
            s["BodyText2"],
        )
    )

    story.append(Paragraph("5.4 Deployment Recommendation", s["SectionH2"]))
    story.append(
        Paragraph(
            "'PydanticAI-powered' is NOT a selling point for enterprise buyers. Enterprise CTOs and "
            "CISOs buy outcomes (fewer vulnerabilities, faster remediation, compliance certification), "
            "not frameworks. Framework branding signals immaturity. Procurement teams will flag external "
            "framework dependencies during security reviews. Keep as implementation detail.",
            s["BodyText2"],
        )
    )
    story.append(Paragraph("Recommended marketing messages instead:", s["BodyText2"]))
    marketing = [
        "'Purpose-built agent architecture for security-critical environments'",
        "'Constitutional AI-aligned autonomous agents with deterministic guardrails'",
        "'The only AI security platform with GovCloud-native agent execution'",
    ]
    for m in marketing:
        story.append(Paragraph(f"\u2022  {m}", s["BulletItem"]))

    story.append(Paragraph("5.5 Decision Matrix", s["SectionH2"]))
    story.append(
        make_table(
            [
                "Factor",
                "Weight",
                "Full Adoption",
                "Selective Integration",
                "No Adoption",
            ],
            [
                ["Engineering effort (inverse)", "15%", "1/10", "7/10", "10/10"],
                ["Customer value", "25%", "2/10", "4/10", "3/10"],
                ["Strategic alignment", "30%", "2/10", "7/10", "6/10"],
                ["Revenue impact", "20%", "1/10", "3/10", "5/10"],
                ["Risk (inverse)", "10%", "1/10", "6/10", "9/10"],
                ["WEIGHTED SCORE", "100%", "1.7", "5.3", "5.8"],
            ],
            col_widths=[1.5 * inch, 0.7 * inch, 1.2 * inch, 1.4 * inch, 2.2 * inch],
            styles_obj=s,
        )
    )

    story.append(
        Paragraph("5.6 Recommended 'Embrace and Extend' Strategy", s["SectionH2"])
    )
    story.append(
        make_table(
            ["Phase", "Timeline", "Scope"],
            [
                [
                    "Phase 1: Compatibility Adapter",
                    "Q2 2026 (~2 weeks)",
                    "Thin wrappers in src/services/pydantic_ai_adapter/, expose Aura agents as PydanticAI-compatible",
                ],
                [
                    "Phase 2: Streaming Enhancement",
                    "Q3 2026 (~3 weeks)",
                    "Add structured output streaming natively (build independently, NOT via PydanticAI)",
                ],
                [
                    "Phase 3: A2A Interoperability",
                    "Q4 2026 (~2 weeks)",
                    "Test FastA2A as compatibility layer; adopt only if customer demand materializes",
                ],
            ],
            col_widths=[1.8 * inch, 1.3 * inch, 3.9 * inch],
            styles_obj=s,
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # SECTION 6: CONSOLIDATED RECOMMENDATIONS
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("6. Consolidated Recommendations", s["SectionH1"]))

    story.append(Paragraph("6.1 Architectural Decision Summary", s["SectionH2"]))
    story.append(
        make_table(
            ["Aspect", "Decision"],
            [
                [
                    "Adoption scope",
                    "Selective - new agents only in Phase 1, gradual migration in Phase 2",
                ],
                [
                    "Bedrock integration",
                    "Via adapter wrapping existing BedrockLLMService; never bypass cost controls",
                ],
                ["Deployment model", "In-process library within existing EKS pods"],
                [
                    "GovCloud compatibility",
                    "Fully compatible; Logfire must be disabled",
                ],
                [
                    "MCP integration",
                    "PydanticAI MCP client connects to existing servers; internal tools as native PydanticAI tools",
                ],
                [
                    "Orchestration",
                    "Keep MetaOrchestrator; evaluate pydantic-graph in Phase 3 decision gate",
                ],
                ["Durable execution", "Keep DynamoDB checkpointing; defer Temporal"],
                [
                    "Cost controls",
                    "All LLM calls route through BedrockLLMService adapter",
                ],
                [
                    "Observability",
                    "PydanticAI OTel -> existing OTLP collector -> X-Ray (never Logfire)",
                ],
                [
                    "Marketing",
                    "Implementation detail only; never market as 'PydanticAI-powered'",
                ],
                [
                    "Data exfiltration",
                    "AuraModelFactory + VPC egress controls before any PydanticAI code",
                ],
                [
                    "Tool governance",
                    "All PydanticAI tools wrapped by ADR-066 CapabilityEnforcementMiddleware",
                ],
            ],
            col_widths=[1.5 * inch, 5.5 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("6.2 Unified Implementation Roadmap", s["SectionH2"]))
    story.append(
        make_table(
            ["Week", "Phase", "Deliverables", "Gate Criteria"],
            [
                [
                    "0",
                    "Security Prerequisites",
                    "AuraModelFactory, VPC egress controls, PydanticAIToolWrapper, IRSA config",
                    "All CRITICAL mitigations verified",
                ],
                [
                    "1-3",
                    "Foundation",
                    "Package structure, Pydantic models, typed wrappers, Orchestrator Facade (100% legacy)",
                    "All models serialize/deserialize correctly",
                ],
                [
                    "4-6",
                    "Scanner Agent",
                    "First PydanticAI agent, Tier 1 tools, 10% LOW severity routing",
                    "Scanner quality >= legacy on same inputs",
                ],
                [
                    "7-11",
                    "Coder + Reviewer",
                    "Core agent pair, Tier 2 tools, LOW severity on PydanticAI",
                    "Patch quality >= legacy; HITL integration verified",
                ],
                [
                    "12-15",
                    "Validator + HITL",
                    "Complete pipeline, Tier 3-4 tools, MEDIUM severity added",
                    "E2E workflow passes; sandbox integration stable",
                ],
                [
                    "16-20",
                    "Full Migration",
                    "All severities, MCP server, legacy deprecated",
                    "Per-tenant flags validated; load test passed",
                ],
                [
                    "21-24",
                    "Cleanup",
                    "Remove legacy code, archive, update Big 3 docs",
                    "All 23,500+ tests pass; 70% coverage maintained",
                ],
            ],
            col_widths=[0.5 * inch, 1.2 * inch, 2.8 * inch, 2.5 * inch],
            styles_obj=s,
        )
    )

    story.append(Paragraph("6.3 Net Cost Impact", s["SectionH2"]))
    story.append(
        make_table(
            ["Category", "Cost"],
            [
                ["PydanticAI license", "$0 (MIT open source)"],
                ["AWS infrastructure changes", "$0/month (no new services)"],
                ["Engineering investment", "~24 weeks across 5 phases"],
                ["New tests", "~1,200 (bringing total to ~23,500)"],
                [
                    "Bedrock cost change",
                    "Potential 5-10% reduction (fewer retries from structured outputs)",
                ],
                ["Container image size", "+~10MB (negligible)"],
            ],
            col_widths=[2.0 * inch, 5.0 * inch],
            styles_obj=s,
        )
    )

    story.append(PageBreak())

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX A: MITRE ATT&CK
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Appendix A: MITRE ATT&CK Mapping", s["SectionH1"]))
    story.append(
        make_table(
            ["Technique", "ATT&CK ID", "Relevance"],
            [
                [
                    "Supply Chain: Compromise Dependencies",
                    "T1195.001",
                    "Finding 1: PydanticAI as new PyPI dependency",
                ],
                [
                    "Exploitation for Client Execution",
                    "T1203",
                    "Finding 2: Prompt injection causing tool misuse",
                ],
                [
                    "Command and Scripting: Python",
                    "T1059.006",
                    "Finding 4: PydanticAI tool functions execute Python",
                ],
                [
                    "Application Layer Protocol: Web",
                    "T1071.001",
                    "Finding 5: MCP over HTTP/SSE",
                ],
                [
                    "Exfiltration Over Web Service",
                    "T1567",
                    "Finding 7: Data sent to non-Bedrock LLM providers",
                ],
                [
                    "Unsecured Credentials: In Files",
                    "T1552.001",
                    "Finding 8: API keys in environment/config",
                ],
                [
                    "Impair Defenses: Disable Tools",
                    "T1562.001",
                    "Finding 6: HITL bypass via non-deferred tools",
                ],
                [
                    "Escape to Host",
                    "T1611",
                    "Finding 10: Container escape via sandbox interaction",
                ],
                [
                    "Modify Authentication Process",
                    "T1556",
                    "Finding 6: Approval mechanism bypass",
                ],
            ],
            col_widths=[2.2 * inch, 1.0 * inch, 3.8 * inch],
            styles_obj=s,
        )
    )

    story.append(Spacer(1, 0.3 * inch))

    # ═══════════════════════════════════════════════════════════════════════
    # APPENDIX B: KEY FILES
    # ═══════════════════════════════════════════════════════════════════════
    story.append(Paragraph("Appendix B: Key Files Referenced", s["SectionH1"]))
    story.append(
        make_table(
            ["File", "Relevance"],
            [
                [
                    "src/agents/agent_orchestrator.py",
                    "V7 System2Orchestrator - primary migration target",
                ],
                [
                    "src/agents/meta_orchestrator.py",
                    "MetaOrchestrator - DAG execution, autonomy levels",
                ],
                [
                    "src/agents/base_agent.py",
                    "BaseAgent, MCPToolMixin, HITLApproval dataclasses",
                ],
                ["src/agents/coder_agent.py", "CoderAgent - Chain of Draft prompting"],
                [
                    "src/agents/reviewer_agent.py",
                    "ReviewerAgent - security policies, self-reflection",
                ],
                [
                    "src/agents/validator_agent.py",
                    "ValidatorAgent - AST parsing, sandbox orchestration",
                ],
                [
                    "src/agents/context_objects.py",
                    "ContextSource, ContextItem, HybridContext",
                ],
                [
                    "src/services/bedrock_llm_service.py",
                    "Bedrock client - must NOT be bypassed",
                ],
                [
                    "src/services/context_retrieval_service.py",
                    "Hybrid GraphRAG query engine",
                ],
                [
                    "src/services/sandbox_network_service.py",
                    "Sandbox provisioning with dnsmasq/Fargate",
                ],
                [
                    "src/services/orchestration_service.py",
                    "SQS/DynamoDB job management (UNCHANGED)",
                ],
                [
                    "src/services/capability_governance/middleware.py",
                    "ADR-066 tool enforcement - must wrap PydanticAI",
                ],
                [
                    "src/services/capability_governance/policy.py",
                    "4-tier tool classifications",
                ],
                [
                    "src/services/capability_governance/dynamic_grants.py",
                    "HITL grant management",
                ],
                [
                    "src/services/semantic_guardrails/engine.py",
                    "6-layer threat detection - upstream of PydanticAI",
                ],
                [
                    "src/services/supply_chain/sbom_attestation.py",
                    "SBOM pipeline - must include PydanticAI",
                ],
                [
                    "src/services/runtime_security/escape_detector.py",
                    "Container escape detection",
                ],
            ],
            col_widths=[3.5 * inch, 3.5 * inch],
            styles_obj=s,
        )
    )

    story.append(Spacer(1, 0.5 * inch))
    story.append(HRFlowable(width="100%", thickness=1, color=TABLE_BORDER))
    story.append(Spacer(1, 0.1 * inch))
    story.append(
        Paragraph("End of ADR-082 Multi-Agent Analysis Report", s["FooterText"])
    )

    # ─── Build PDF ────────────────────────────────────────────────────────
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    return output_path


if __name__ == "__main__":
    path = build_document()
    print(f"PDF generated: {path}")
