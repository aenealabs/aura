#!/usr/bin/env python3
"""Demo script for the Autonomous ADR Generation Pipeline.

This script demonstrates the full pipeline flow from threat intelligence
to ADR document generation in a dev environment.

Usage:
    python3 scripts/test_adr_pipeline_demo.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.adaptive_intelligence_agent import AdaptiveIntelligenceAgent
from src.agents.adr_generator_agent import ADRGeneratorAgent
from src.agents.architecture_review_agent import ArchitectureReviewAgent
from src.agents.threat_intelligence_agent import (
    ThreatIntelConfig,
    ThreatIntelligenceAgent,
    ThreatSeverity,
)


def print_header(title: str) -> None:
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_subheader(title: str) -> None:
    """Print a formatted subheader."""
    print(f"\n--- {title} ---")


async def run_pipeline_demo():
    """Run the full ADR generation pipeline demo."""
    print_header("AUTONOMOUS ADR GENERATION PIPELINE - DEV DEMO")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Environment: Dev")

    # Initialize agents
    print_subheader("Phase 0: Initializing Agents")

    threat_agent = ThreatIntelligenceAgent(
        config=ThreatIntelConfig(
            check_interval_minutes=60,
            severity_threshold=ThreatSeverity.MEDIUM,
        )
    )

    # Set project SBOM (dependencies to monitor)
    threat_agent.set_dependency_sbom(
        [
            {"name": "requests", "version": "2.28.0"},
            {"name": "fastapi", "version": "0.108.0"},
            {"name": "opensearch-py", "version": "2.4.0"},
            {"name": "boto3", "version": "1.34.0"},
            {"name": "pydantic", "version": "2.5.0"},
        ]
    )
    print("  - ThreatIntelligenceAgent initialized")
    print(f"    SBOM: 5 dependencies configured")

    adaptive_agent = AdaptiveIntelligenceAgent()
    print("  - AdaptiveIntelligenceAgent initialized")
    print(f"    Best practices: {len(adaptive_agent._best_practices_db)} loaded")

    review_agent = ArchitectureReviewAgent(adr_directory="docs/architecture-decisions")
    print("  - ArchitectureReviewAgent initialized")
    print(
        f"    Architecture patterns: {len(review_agent._architecture_patterns)} loaded"
    )
    print(f"    ADR index: {len(review_agent._adr_index)} ADRs tracked")

    generator_agent = ADRGeneratorAgent(adr_directory="docs/architecture-decisions")
    print("  - ADRGeneratorAgent initialized")
    print(f"    Next ADR number: {generator_agent._next_adr_number}")

    # Phase 1: Gather threat intelligence
    print_subheader("Phase 1: Gathering Threat Intelligence")
    threat_reports = await threat_agent.gather_intelligence()

    print(f"\nThreat Reports Gathered: {len(threat_reports)}")
    for i, report in enumerate(threat_reports, 1):
        print(f"\n  [{i}] {report.title}")
        print(f"      Severity: {report.severity.value.upper()}")
        print(f"      Source: {report.source}")
        print(f"      CVEs: {', '.join(report.cve_ids) if report.cve_ids else 'N/A'}")
        if report.cvss_score:
            print(f"      CVSS: {report.cvss_score}")
        if report.affected_components:
            print(f"      Affects: {', '.join(report.affected_components)}")

    # Phase 2: Analyze and generate recommendations
    print_subheader("Phase 2: Analyzing Threats & Generating Recommendations")
    recommendations = adaptive_agent.analyze_threats(threat_reports)

    print(f"\nRecommendations Generated: {len(recommendations)}")
    for i, rec in enumerate(recommendations, 1):
        print(f"\n  [{i}] {rec.title}")
        print(f"      Type: {rec.recommendation_type.value}")
        print(f"      Risk Score: {rec.risk_score}/10 ({rec.risk_level.value})")
        print(f"      Effort: {rec.effort_level.value}")
        print(f"      Compliance Impact: {len(rec.compliance_impact)} controls")
        print(f"      Implementation Steps: {len(rec.implementation_steps)}")

    # Phase 3: Evaluate for ADR-worthiness
    print_subheader("Phase 3: Evaluating ADR-Worthiness")
    trigger_events = review_agent.evaluate_recommendations(recommendations)

    print(f"\nADR Triggers Identified: {len(trigger_events)}")
    for i, trigger in enumerate(trigger_events, 1):
        print(f"\n  [{i}] {trigger.title}")
        print(f"      Category: {trigger.category.value}")
        print(f"      Significance: {trigger.significance.value}")
        print(f"      HITL Required: {'Yes' if trigger.requires_hitl else 'No'}")
        if trigger.pattern_deviations:
            print(f"      Pattern Deviations: {len(trigger.pattern_deviations)}")
        if trigger.existing_adr_references:
            print(f"      Related ADRs: {', '.join(trigger.existing_adr_references)}")

    # Phase 4: Generate ADR documents
    print_subheader("Phase 4: Generating ADR Documents")
    adrs = generator_agent.generate_adrs(trigger_events)

    print(f"\nADR Documents Generated: {len(adrs)}")
    for i, adr in enumerate(adrs, 1):
        print(f"\n  [{i}] ADR-{adr.number:03d}: {adr.title}")
        print(f"      Status: {adr.status}")
        print(f"      Decision Makers: {adr.decision_makers}")
        print(f"      Alternatives: {len(adr.alternatives)}")
        print(f"      Positive Consequences: {len(adr.consequences_positive)}")
        print(f"      Negative Consequences: {len(adr.consequences_negative)}")
        print(f"      Mitigations: {len(adr.consequences_mitigation)}")
        print(f"      References: {len(adr.references)}")
        print(f"      Filename: {adr.get_filename()}")

    # Show sample ADR content
    if adrs:
        print_subheader("Sample ADR Preview (First ADR)")
        sample_adr = adrs[0]
        markdown = sample_adr.to_markdown()

        # Show first 50 lines
        lines = markdown.split("\n")[:50]
        print("\n" + "\n".join(lines))
        if len(markdown.split("\n")) > 50:
            print(f"\n... ({len(markdown.split(chr(10))) - 50} more lines)")

    # Summary
    print_header("PIPELINE EXECUTION SUMMARY")
    print(f"""
    Threat Reports Gathered:    {len(threat_reports)}
    Recommendations Generated:  {len(recommendations)}
    ADR Triggers Identified:    {len(trigger_events)}
    ADR Documents Generated:    {len(adrs)}

    HITL Required:              {sum(1 for t in trigger_events if t.requires_hitl)}
    Auto-Approvable:            {sum(1 for t in trigger_events if not t.requires_hitl)}

    Status: Pipeline execution complete
    Note: ADRs generated with 'Proposed' status pending review
    """)

    return {
        "threat_reports": len(threat_reports),
        "recommendations": len(recommendations),
        "triggers": len(trigger_events),
        "adrs": len(adrs),
    }


if __name__ == "__main__":
    result = asyncio.run(run_pipeline_demo())
    print(f"\nDemo complete. Results: {result}")
