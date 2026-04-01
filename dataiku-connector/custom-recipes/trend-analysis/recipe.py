"""
Aura Vulnerability Trends Recipe

Custom Dataiku recipe that analyzes vulnerability trends over time.

ADR-048 Phase 4: Dataiku Connector
"""

from datetime import datetime, timezone

import dataiku
import numpy as np
import pandas as pd

# Import Aura trend analysis utilities
from aura_connector import AuraTrendAnalysis
from dataiku.customrecipe import (
    get_input_names_for_role,
    get_output_names_for_role,
    get_recipe_config,
)

# Get recipe configuration
config = get_recipe_config()
time_column = config.get("time_column", "created_at")
aggregation_period = config.get("aggregation_period", "week")
include_predictions = config.get("include_predictions", False)
risk_threshold = config.get("risk_threshold", 50.0)

# Period mapping for pandas
period_map = {
    "day": "D",
    "week": "W",
    "month": "ME",
    "quarter": "QE",
}

# Get input datasets
findings_input_name = get_input_names_for_role("findings_input")[0]
findings_input = dataiku.Dataset(findings_input_name)
findings_df = findings_input.get_dataframe()

historical_input_names = get_input_names_for_role("historical_input")
if historical_input_names:
    historical_input = dataiku.Dataset(historical_input_names[0])
    historical_df = historical_input.get_dataframe()
    # Combine current and historical findings
    all_findings_df = pd.concat([historical_df, findings_df], ignore_index=True)
else:
    all_findings_df = findings_df

# Get output datasets
trends_output_name = get_output_names_for_role("trends_output")[0]
trends_output = dataiku.Dataset(trends_output_name)

risk_output_names = get_output_names_for_role("risk_scores_output")
risk_output = dataiku.Dataset(risk_output_names[0]) if risk_output_names else None

cwe_output_names = get_output_names_for_role("cwe_analysis_output")
cwe_output = dataiku.Dataset(cwe_output_names[0]) if cwe_output_names else None

# Ensure time column is datetime
if time_column in all_findings_df.columns:
    all_findings_df[time_column] = pd.to_datetime(all_findings_df[time_column])
else:
    # Use current timestamp if no time column
    all_findings_df[time_column] = datetime.now(timezone.utc)

# Compute severity weights
severity_weights = {
    "critical": 10.0,
    "high": 8.0,
    "medium": 5.0,
    "low": 2.0,
    "info": 1.0,
}

all_findings_df["severity_weight"] = all_findings_df["severity"].map(
    lambda x: severity_weights.get(str(x).lower(), 1.0)
)

# Aggregate by time period
period_code = period_map.get(aggregation_period, "W")
all_findings_df["period"] = all_findings_df[time_column].dt.to_period(period_code)

# Compute trends
trends_data = []

for period, group in all_findings_df.groupby("period"):
    period_start = period.start_time

    # Count by severity
    severity_counts = group["severity"].value_counts().to_dict()

    # Compute risk score for period
    total_risk = group["severity_weight"].sum()

    trends_data.append(
        {
            "period_start": period_start,
            "period_end": period.end_time,
            "total_findings": len(group),
            "critical_count": severity_counts.get("critical", 0),
            "high_count": severity_counts.get("high", 0),
            "medium_count": severity_counts.get("medium", 0),
            "low_count": severity_counts.get("low", 0),
            "info_count": severity_counts.get("info", 0),
            "risk_score": total_risk,
            "unique_files": (
                group["file_path"].nunique() if "file_path" in group.columns else 0
            ),
            "unique_cwes": (
                group["cwe_id"].nunique() if "cwe_id" in group.columns else 0
            ),
        }
    )

trends_df = pd.DataFrame(trends_data)

if not trends_df.empty:
    # Sort by period
    trends_df = trends_df.sort_values("period_start")

    # Compute period-over-period changes
    trends_df["findings_change"] = trends_df["total_findings"].diff()
    trends_df["findings_pct_change"] = trends_df["total_findings"].pct_change() * 100
    trends_df["risk_change"] = trends_df["risk_score"].diff()

    # Compute moving averages
    if len(trends_df) >= 3:
        trends_df["findings_ma3"] = trends_df["total_findings"].rolling(window=3).mean()
        trends_df["risk_ma3"] = trends_df["risk_score"].rolling(window=3).mean()

    # Add trend predictions if requested
    if include_predictions and len(trends_df) >= 2:
        # Simple linear regression for trend
        x = np.arange(len(trends_df))
        y_findings = trends_df["total_findings"].values
        y_risk = trends_df["risk_score"].values

        # Compute slopes
        if len(x) > 1:
            findings_slope = np.polyfit(x, y_findings, 1)[0]
            risk_slope = np.polyfit(x, y_risk, 1)[0]

            trends_df["findings_trend"] = (
                "increasing" if findings_slope > 0 else "decreasing"
            )
            trends_df["risk_trend"] = "increasing" if risk_slope > 0 else "decreasing"

            # Predict next period
            next_findings = y_findings[-1] + findings_slope
            next_risk = y_risk[-1] + risk_slope

            trends_df["predicted_next_findings"] = max(0, next_findings)
            trends_df["predicted_next_risk"] = max(0, next_risk)

    # Add analysis metadata
    trends_df["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()
    trends_df["aggregation_period"] = aggregation_period

# Write trends output
trends_output.write_with_schema(trends_df)

# Compute and write risk scores per file
if risk_output:
    findings_list = all_findings_df.to_dict("records")
    risk_scores = AuraTrendAnalysis.compute_file_risk_scores(findings_list)

    risk_df = pd.DataFrame(risk_scores)

    if not risk_df.empty:
        # Add risk classification
        risk_df["risk_level"] = risk_df["risk_score"].apply(
            lambda x: (
                "high"
                if x >= risk_threshold
                else ("medium" if x >= risk_threshold / 2 else "low")
            )
        )
        risk_df["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()

    risk_output.write_with_schema(risk_df)

# Compute and write CWE analysis
if cwe_output:
    findings_list = all_findings_df.to_dict("records")
    cwe_summary = AuraTrendAnalysis.compute_cwe_summary(findings_list)

    cwe_df = pd.DataFrame(cwe_summary)

    if not cwe_df.empty:
        # Add percentage of total
        total_with_cwe = cwe_df["count"].sum()
        cwe_df["percentage"] = (cwe_df["count"] / total_with_cwe * 100).round(2)
        cwe_df["analysis_timestamp"] = datetime.now(timezone.utc).isoformat()

    cwe_output.write_with_schema(cwe_df)

print(f"Analyzed {len(all_findings_df)} findings across {len(trends_df)} periods")
if risk_output:
    print(f"Computed risk scores for {len(risk_df) if 'risk_df' in dir() else 0} files")
if cwe_output:
    print(f"Analyzed {len(cwe_df) if 'cwe_df' in dir() else 0} unique CWEs")
