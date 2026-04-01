"""
Aura Repository Scan Recipe

Custom Dataiku recipe that triggers repository scans and exports findings.

ADR-048 Phase 4: Dataiku Connector
"""

from datetime import datetime, timezone

import dataiku
import pandas as pd

# Import Aura connector
from aura_connector import AuraFindingsConnector, AuraTrendAnalysis
from dataiku.customrecipe import get_output_names_for_role, get_recipe_config

# Get recipe configuration
config = get_recipe_config()
server_url = config.get("server_url", "http://localhost:8080")
severity_filter = config.get("severity_filter", "all")
include_info = config.get("include_info", False)

# Get output datasets
findings_output_name = get_output_names_for_role("findings_output")[0]
findings_output = dataiku.Dataset(findings_output_name)

summary_output_names = get_output_names_for_role("summary_output")
summary_output = (
    dataiku.Dataset(summary_output_names[0]) if summary_output_names else None
)

# Initialize connector
connector = AuraFindingsConnector({"server_url": server_url})

# Determine severity filter
severity_map = {
    "critical": ["critical"],
    "high": ["critical", "high"],
    "medium": ["critical", "high", "medium"],
    "low": ["critical", "high", "medium", "low"],
    "all": None,
}

severity_list = severity_map.get(severity_filter)
if include_info and severity_list:
    severity_list.append("info")

# Fetch findings
all_findings = []
if severity_list:
    for severity in severity_list:
        findings = connector.get_rows(severity=severity)
        all_findings.extend(findings)
    # Deduplicate
    seen_ids = set()
    unique_findings = []
    for f in all_findings:
        if f["finding_id"] not in seen_ids:
            seen_ids.add(f["finding_id"])
            unique_findings.append(f)
    all_findings = unique_findings
else:
    all_findings = connector.get_rows()

# Convert to DataFrame and write
findings_df = pd.DataFrame(all_findings)

if not findings_df.empty:
    # Add metadata columns
    findings_df["scan_timestamp"] = datetime.now(timezone.utc).isoformat()
    findings_df["source"] = "aura_scan"

findings_output.write_with_schema(findings_df)

# Write summary if requested
if summary_output:
    # Compute summary statistics
    severity_dist = AuraTrendAnalysis.compute_severity_distribution(all_findings)
    category_dist = AuraTrendAnalysis.compute_category_distribution(all_findings)
    cwe_summary = AuraTrendAnalysis.compute_cwe_summary(all_findings)

    summary_data = {
        "metric": [],
        "value": [],
        "category": [],
    }

    # Total findings
    summary_data["metric"].append("total_findings")
    summary_data["value"].append(len(all_findings))
    summary_data["category"].append("overview")

    # Severity distribution
    for severity, count in severity_dist.items():
        summary_data["metric"].append(f"severity_{severity}")
        summary_data["value"].append(count)
        summary_data["category"].append("severity")

    # Top categories
    for category, count in list(category_dist.items())[:10]:
        summary_data["metric"].append(f"category_{category}")
        summary_data["value"].append(count)
        summary_data["category"].append("category")

    summary_df = pd.DataFrame(summary_data)
    summary_df["scan_timestamp"] = datetime.now(timezone.utc).isoformat()

    summary_output.write_with_schema(summary_df)

print(f"Exported {len(all_findings)} findings to {findings_output_name}")
