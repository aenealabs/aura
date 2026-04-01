#!/usr/bin/env python3
"""
Project Aura ROI Calculator for Defense Contractors
====================================================
Calculate return on investment for autonomous code development platform.

Usage:
    python roi_calculator.py --developers 500 --avg-salary 150000
    python roi_calculator.py --interactive
    python roi_calculator.py --export-pdf report.pdf

Features:
- Cost-benefit analysis (manual vs Aura)
- Payback period calculation
- 5-year TCO projection
- Risk-adjusted ROI
- Compliance cost savings
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class CompanyProfile:
    """Defense contractor profile for ROI calculation."""

    name: str = "Defense Contractor Co."
    num_developers: int = 500
    avg_developer_salary: int = 150000  # USD per year
    avg_hourly_rate: float = 75.0  # Fully loaded (salary + benefits + overhead)

    # Current development metrics (manual)
    avg_feature_dev_time_hours: float = 80.0  # 2 weeks per feature
    features_per_year: int = 200
    bug_fix_time_hours: float = 16.0  # 2 days per bug
    bugs_per_year: int = 500
    security_vuln_fix_hours: float = 40.0  # 1 week per vuln
    vulns_per_year: int = 50
    code_review_hours_per_feature: float = 8.0

    # Quality metrics (manual baseline)
    defect_rate: float = 0.15  # 15% of features have defects
    security_vuln_rate: float = 0.08  # 8% have security issues
    rework_rate: float = 0.20  # 20% require significant rework

    # Compliance overhead
    cmmc_compliance_manual_hours_per_year: int = 2000  # Full-time compliance engineer
    audit_prep_hours_per_year: int = 500


@dataclass
class AuraMetrics:
    """Aura platform performance metrics."""

    # Autonomy rates (% of work done by AI)
    feature_autonomy_rate: float = 0.80  # 80% autonomous
    bug_fix_autonomy_rate: float = 0.85  # 85% autonomous
    security_fix_autonomy_rate: float = 0.75  # 75% autonomous

    # Time reduction (for the 20% human work remaining)
    feature_dev_speedup: float = 2.0  # 2x faster due to better context
    bug_fix_speedup: float = 3.0  # 3x faster (Aura finds root cause)
    security_fix_speedup: float = 2.5  # 2.5x faster (policy-driven fixes)

    # Quality improvements
    defect_rate_reduction: float = 0.60  # 60% fewer defects
    security_vuln_reduction: float = 0.70  # 70% fewer vulns
    rework_rate_reduction: float = 0.50  # 50% less rework

    # Compliance automation
    cmmc_compliance_automation_rate: float = 0.80  # 80% automated
    audit_prep_automation_rate: float = 0.70  # 70% automated


@dataclass
class AuraPricing:
    """Aura platform pricing model."""

    developer_seat_monthly: int = 600  # $600/developer/month
    platform_base_monthly: int = 50000  # $50K/month base fee
    professional_services_hourly: int = 300  # $300/hour for implementation
    implementation_hours: int = 200  # 200 hours for setup (first year only)
    annual_support_percent: float = 0.15  # 15% of annual license for support


class ROICalculator:
    """Calculate ROI for Aura deployment."""

    def __init__(
        self, profile: CompanyProfile, aura_metrics: AuraMetrics, pricing: AuraPricing
    ):
        self.profile = profile
        self.aura_metrics = aura_metrics
        self.pricing = pricing

    def calculate_manual_costs(self) -> Dict[str, float]:
        """Calculate current manual development costs."""

        # Development costs
        feature_dev_cost = (
            self.profile.features_per_year
            * self.profile.avg_feature_dev_time_hours
            * self.profile.avg_hourly_rate
        )

        bug_fix_cost = (
            self.profile.bugs_per_year
            * self.profile.bug_fix_time_hours
            * self.profile.avg_hourly_rate
        )

        security_fix_cost = (
            self.profile.vulns_per_year
            * self.profile.security_vuln_fix_hours
            * self.profile.avg_hourly_rate
        )

        code_review_cost = (
            self.profile.features_per_year
            * self.profile.code_review_hours_per_feature
            * self.profile.avg_hourly_rate
        )

        # Quality-related costs (rework)
        rework_cost = (
            self.profile.features_per_year
            * self.profile.rework_rate
            * self.profile.avg_feature_dev_time_hours
            * 0.5  # Rework takes 50% of original time
            * self.profile.avg_hourly_rate
        )

        # Compliance costs
        cmmc_compliance_cost = (
            self.profile.cmmc_compliance_manual_hours_per_year
            * self.profile.avg_hourly_rate
        )

        audit_prep_cost = (
            self.profile.audit_prep_hours_per_year * self.profile.avg_hourly_rate
        )

        total_cost = (
            feature_dev_cost
            + bug_fix_cost
            + security_fix_cost
            + code_review_cost
            + rework_cost
            + cmmc_compliance_cost
            + audit_prep_cost
        )

        return {
            "feature_development": feature_dev_cost,
            "bug_fixes": bug_fix_cost,
            "security_fixes": security_fix_cost,
            "code_reviews": code_review_cost,
            "rework": rework_cost,
            "cmmc_compliance": cmmc_compliance_cost,
            "audit_prep": audit_prep_cost,
            "total_annual": total_cost,
        }

    def calculate_aura_costs(self, year: int = 1) -> Dict[str, float]:
        """Calculate Aura platform costs."""

        # License costs
        annual_developer_licenses = (
            self.pricing.developer_seat_monthly * self.profile.num_developers * 12
        )

        annual_platform_base = self.pricing.platform_base_monthly * 12

        # Implementation (first year only)
        implementation_cost = 0
        if year == 1:
            implementation_cost = (
                self.pricing.implementation_hours
                * self.pricing.professional_services_hourly
            )

        # Annual support
        total_license_cost = annual_developer_licenses + annual_platform_base
        annual_support = total_license_cost * self.pricing.annual_support_percent

        total_cost = (
            annual_developer_licenses
            + annual_platform_base
            + implementation_cost
            + annual_support
        )

        return {
            "developer_licenses": annual_developer_licenses,
            "platform_base": annual_platform_base,
            "implementation": implementation_cost,
            "annual_support": annual_support,
            "total_annual": total_cost,
        }

    def calculate_aura_savings(self) -> Dict[str, float]:
        """Calculate operational savings with Aura."""

        # Feature development savings (80% autonomous)
        feature_autonomous_hours = (
            self.profile.features_per_year
            * self.profile.avg_feature_dev_time_hours
            * self.aura_metrics.feature_autonomy_rate
        )

        feature_human_hours = (
            self.profile.features_per_year
            * self.profile.avg_feature_dev_time_hours
            * (1 - self.aura_metrics.feature_autonomy_rate)
            / self.aura_metrics.feature_dev_speedup
        )

        feature_savings = (
            self.profile.features_per_year * self.profile.avg_feature_dev_time_hours
            - feature_human_hours
        ) * self.profile.avg_hourly_rate

        # Bug fix savings
        bug_autonomous_hours = (
            self.profile.bugs_per_year
            * self.profile.bug_fix_time_hours
            * self.aura_metrics.bug_fix_autonomy_rate
        )

        bug_human_hours = (
            self.profile.bugs_per_year
            * self.profile.bug_fix_time_hours
            * (1 - self.aura_metrics.bug_fix_autonomy_rate)
            / self.aura_metrics.bug_fix_speedup
        )

        bug_savings = (
            self.profile.bugs_per_year * self.profile.bug_fix_time_hours
            - bug_human_hours
        ) * self.profile.avg_hourly_rate

        # Security fix savings
        security_autonomous_hours = (
            self.profile.vulns_per_year
            * self.profile.security_vuln_fix_hours
            * self.aura_metrics.security_fix_autonomy_rate
        )

        security_human_hours = (
            self.profile.vulns_per_year
            * self.profile.security_vuln_fix_hours
            * (1 - self.aura_metrics.security_fix_autonomy_rate)
            / self.aura_metrics.security_fix_speedup
        )

        security_savings = (
            self.profile.vulns_per_year * self.profile.security_vuln_fix_hours
            - security_human_hours
        ) * self.profile.avg_hourly_rate

        # Code review savings (automated by Reviewer Agent)
        code_review_savings = (
            self.profile.features_per_year
            * self.profile.code_review_hours_per_feature
            * 0.70  # 70% of reviews automated
            * self.profile.avg_hourly_rate
        )

        # Quality improvement savings (fewer defects = less rework)
        rework_reduction = (
            self.profile.features_per_year
            * self.profile.rework_rate
            * self.aura_metrics.rework_rate_reduction
            * self.profile.avg_feature_dev_time_hours
            * 0.5
            * self.profile.avg_hourly_rate
        )

        # Compliance automation savings
        cmmc_savings = (
            self.profile.cmmc_compliance_manual_hours_per_year
            * self.aura_metrics.cmmc_compliance_automation_rate
            * self.profile.avg_hourly_rate
        )

        audit_prep_savings = (
            self.profile.audit_prep_hours_per_year
            * self.aura_metrics.audit_prep_automation_rate
            * self.profile.avg_hourly_rate
        )

        total_savings = (
            feature_savings
            + bug_savings
            + security_savings
            + code_review_savings
            + rework_reduction
            + cmmc_savings
            + audit_prep_savings
        )

        return {
            "feature_development": feature_savings,
            "bug_fixes": bug_savings,
            "security_fixes": security_savings,
            "code_reviews": code_review_savings,
            "rework_reduction": rework_reduction,
            "cmmc_compliance": cmmc_savings,
            "audit_prep": audit_prep_savings,
            "total_annual": total_savings,
        }

    def calculate_roi(self, years: int = 5) -> Dict[str, Any]:
        """Calculate multi-year ROI analysis."""

        manual_costs = self.calculate_manual_costs()

        yearly_analysis = []
        cumulative_cost = 0
        cumulative_savings = 0

        for year in range(1, years + 1):
            aura_costs = self.calculate_aura_costs(year)
            aura_savings = self.calculate_aura_savings()

            net_savings = aura_savings["total_annual"] - aura_costs["total_annual"]
            cumulative_cost += aura_costs["total_annual"]
            cumulative_savings += net_savings

            yearly_analysis.append(
                {
                    "year": year,
                    "aura_cost": aura_costs["total_annual"],
                    "operational_savings": aura_savings["total_annual"],
                    "net_savings": net_savings,
                    "cumulative_savings": cumulative_savings,
                    "roi_percent": (
                        (cumulative_savings / cumulative_cost * 100)
                        if cumulative_cost > 0
                        else 0
                    ),
                    "payback_achieved": cumulative_savings > 0,
                }
            )

        # Calculate payback period
        payback_period = None
        for year_data in yearly_analysis:
            if year_data["payback_achieved"] and payback_period is None:
                # Linear interpolation for more accurate payback
                if year_data["year"] == 1:
                    payback_period = year_data["year"]
                else:
                    prev_cumulative = yearly_analysis[year_data["year"] - 2][
                        "cumulative_savings"
                    ]
                    fraction = -prev_cumulative / (
                        year_data["cumulative_savings"] - prev_cumulative
                    )
                    payback_period = year_data["year"] - 1 + fraction

        # 5-year totals
        total_aura_cost = sum(y["aura_cost"] for y in yearly_analysis)
        total_savings = sum(y["operational_savings"] for y in yearly_analysis)
        total_net_savings = total_savings - total_aura_cost
        total_roi = (
            (total_net_savings / total_aura_cost * 100) if total_aura_cost > 0 else 0
        )

        return {
            "summary": {
                "company": self.profile.name,
                "developers": self.profile.num_developers,
                "analysis_period_years": years,
                "total_investment": total_aura_cost,
                "total_savings": total_savings,
                "net_benefit": total_net_savings,
                "roi_percent": total_roi,
                "payback_period_years": payback_period,
            },
            "baseline_costs": manual_costs,
            "yearly_analysis": yearly_analysis,
            "savings_breakdown": self.calculate_aura_savings(),
        }

    def generate_report(self, format: str = "text") -> str:
        """Generate ROI report in specified format."""

        roi_data = self.calculate_roi()

        if format == "json":
            return json.dumps(roi_data, indent=2)

        elif format == "text":
            return self._generate_text_report(roi_data)

        elif format == "markdown":
            return self._generate_markdown_report(roi_data)

        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_text_report(self, roi_data: Dict[str, Any]) -> str:
        """Generate text-based report."""

        summary = roi_data["summary"]
        baseline = roi_data["baseline_costs"]
        savings = roi_data["savings_breakdown"]
        yearly = roi_data["yearly_analysis"]

        report = []
        report.append("=" * 80)
        report.append("PROJECT AURA - ROI ANALYSIS")
        report.append("=" * 80)
        report.append(f"\nCompany: {summary['company']}")
        report.append(f"Developers: {summary['developers']:,}")
        report.append(f"Analysis Period: {summary['analysis_period_years']} years")
        report.append(f"Report Date: {datetime.now().strftime('%Y-%m-%d')}")

        report.append("\n" + "-" * 80)
        report.append("EXECUTIVE SUMMARY")
        report.append("-" * 80)
        report.append(
            f"Total Investment (Aura):     ${summary['total_investment']:,.0f}"
        )
        report.append(f"Total Operational Savings:   ${summary['total_savings']:,.0f}")
        report.append(f"Net Benefit:                 ${summary['net_benefit']:,.0f}")
        report.append(f"ROI:                         {summary['roi_percent']:.1f}%")

        if summary["payback_period_years"]:
            report.append(
                f"Payback Period:              {summary['payback_period_years']:.1f} years"
            )
        else:
            report.append(
                f"Payback Period:              Not achieved in {summary['analysis_period_years']} years"
            )

        report.append("\n" + "-" * 80)
        report.append("CURRENT STATE (MANUAL) - ANNUAL COSTS")
        report.append("-" * 80)
        for category, cost in baseline.items():
            if category != "total_annual":
                report.append(f"{category.replace('_', ' ').title():.<40} ${cost:,.0f}")
        report.append(f"{'TOTAL ANNUAL COST':.>40} ${baseline['total_annual']:,.0f}")

        report.append("\n" + "-" * 80)
        report.append("FUTURE STATE (WITH AURA) - ANNUAL SAVINGS")
        report.append("-" * 80)
        for category, saving in savings.items():
            if category != "total_annual":
                report.append(
                    f"{category.replace('_', ' ').title():.<40} ${saving:,.0f}"
                )
        report.append(f"{'TOTAL ANNUAL SAVINGS':.>40} ${savings['total_annual']:,.0f}")

        report.append("\n" + "-" * 80)
        report.append("5-YEAR PROJECTION")
        report.append("-" * 80)
        report.append(
            f"{'Year':<6} {'Aura Cost':>15} {'Savings':>15} {'Net Benefit':>15} {'Cumulative':>15} {'ROI %':>10} {'Payback':>10}"
        )
        report.append("-" * 80)

        for year_data in yearly:
            payback_status = "✓" if year_data["payback_achieved"] else "-"
            report.append(
                f"{year_data['year']:<6} "
                f"${year_data['aura_cost']:>14,.0f} "
                f"${year_data['operational_savings']:>14,.0f} "
                f"${year_data['net_savings']:>14,.0f} "
                f"${year_data['cumulative_savings']:>14,.0f} "
                f"{year_data['roi_percent']:>9.1f}% "
                f"{payback_status:>10}"
            )

        report.append("\n" + "=" * 80)
        report.append("KEY INSIGHTS")
        report.append("=" * 80)

        # Calculate insights
        year_1_net = yearly[0]["net_savings"]
        year_1_roi = yearly[0]["roi_percent"]
        velocity_increase = (
            savings["feature_development"] / baseline["feature_development"]
        ) * 100

        report.append(f"\n• Year 1 Net Benefit: ${year_1_net:,.0f}")
        report.append(f"• Year 1 ROI: {year_1_roi:.1f}%")
        report.append(f"• Development Velocity Increase: {velocity_increase:.0f}%")
        report.append(
            f"• Compliance Cost Reduction: ${savings['cmmc_compliance'] + savings['audit_prep']:,.0f}/year"
        )
        report.append(
            f"• Security Improvement: {self.aura_metrics.security_vuln_reduction * 100:.0f}% fewer vulnerabilities"
        )

        report.append("\n" + "=" * 80)

        return "\n".join(report)

    def _generate_markdown_report(self, roi_data: Dict[str, Any]) -> str:
        """Generate markdown-formatted report."""

        summary = roi_data["summary"]
        baseline = roi_data["baseline_costs"]
        savings = roi_data["savings_breakdown"]
        yearly = roi_data["yearly_analysis"]

        md = []
        md.append("# Project Aura - ROI Analysis\n")
        md.append(f"**Company:** {summary['company']}  ")
        md.append(f"**Developers:** {summary['developers']:,}  ")
        md.append(f"**Analysis Period:** {summary['analysis_period_years']} years  ")
        md.append(f"**Report Date:** {datetime.now().strftime('%Y-%m-%d')}  \n")

        md.append("## Executive Summary\n")
        md.append("| Metric | Value |")
        md.append("|--------|-------|")
        md.append(
            f"| **Total Investment (Aura)** | ${summary['total_investment']:,.0f} |"
        )
        md.append(
            f"| **Total Operational Savings** | ${summary['total_savings']:,.0f} |"
        )
        md.append(f"| **Net Benefit** | ${summary['net_benefit']:,.0f} |")
        md.append(f"| **ROI** | {summary['roi_percent']:.1f}% |")

        if summary["payback_period_years"]:
            md.append(
                f"| **Payback Period** | {summary['payback_period_years']:.1f} years |\n"
            )
        else:
            md.append(
                f"| **Payback Period** | Not achieved in {summary['analysis_period_years']} years |\n"
            )

        md.append("## Current State (Manual) - Annual Costs\n")
        md.append("| Category | Annual Cost |")
        md.append("|----------|-------------|")
        for category, cost in baseline.items():
            if category != "total_annual":
                md.append(f"| {category.replace('_', ' ').title()} | ${cost:,.0f} |")
        md.append(f"| **TOTAL** | **${baseline['total_annual']:,.0f}** |\n")

        md.append("## Future State (With Aura) - Annual Savings\n")
        md.append("| Category | Annual Savings |")
        md.append("|----------|----------------|")
        for category, saving in savings.items():
            if category != "total_annual":
                md.append(f"| {category.replace('_', ' ').title()} | ${saving:,.0f} |")
        md.append(f"| **TOTAL** | **${savings['total_annual']:,.0f}** |\n")

        md.append("## 5-Year Projection\n")
        md.append(
            "| Year | Aura Cost | Operational Savings | Net Benefit | Cumulative | ROI % | Payback |"
        )
        md.append(
            "|------|-----------|---------------------|-------------|------------|-------|---------|"
        )

        for year_data in yearly:
            payback = "✓" if year_data["payback_achieved"] else "-"
            md.append(
                f"| {year_data['year']} | "
                f"${year_data['aura_cost']:,.0f} | "
                f"${year_data['operational_savings']:,.0f} | "
                f"${year_data['net_savings']:,.0f} | "
                f"${year_data['cumulative_savings']:,.0f} | "
                f"{year_data['roi_percent']:.1f}% | "
                f"{payback} |"
            )

        md.append("\n## Key Insights\n")
        year_1_net = yearly[0]["net_savings"]
        year_1_roi = yearly[0]["roi_percent"]
        velocity_increase = (
            savings["feature_development"] / baseline["feature_development"]
        ) * 100

        md.append(f"- **Year 1 Net Benefit:** ${year_1_net:,.0f}")
        md.append(f"- **Year 1 ROI:** {year_1_roi:.1f}%")
        md.append(f"- **Development Velocity Increase:** {velocity_increase:.0f}%")
        md.append(
            f"- **Compliance Cost Reduction:** ${savings['cmmc_compliance'] + savings['audit_prep']:,.0f}/year"
        )
        md.append(
            f"- **Security Improvement:** {self.aura_metrics.security_vuln_reduction * 100:.0f}% fewer vulnerabilities"
        )

        return "\n".join(md)


def interactive_mode():
    """Run calculator in interactive mode."""

    print("\n" + "=" * 80)
    print("PROJECT AURA - ROI CALCULATOR (INTERACTIVE MODE)")
    print("=" * 80 + "\n")

    # Collect company profile
    print("COMPANY PROFILE")
    print("-" * 80)

    company_name = (
        input("Company Name [Defense Contractor Co.]: ").strip()
        or "Defense Contractor Co."
    )
    num_devs = int(input("Number of Developers [500]: ").strip() or "500")
    avg_salary = int(
        input("Average Developer Salary ($) [150000]: ").strip() or "150000"
    )

    # Calculate hourly rate (salary + 50% benefits/overhead / 2080 hours)
    hourly_rate = (avg_salary * 1.5) / 2080

    print(f"\nCalculated hourly rate (with overhead): ${hourly_rate:.2f}/hour")

    profile = CompanyProfile(
        name=company_name,
        num_developers=num_devs,
        avg_developer_salary=avg_salary,
        avg_hourly_rate=hourly_rate,
    )

    print("\n" + "-" * 80)
    print("Using default Aura performance metrics:")
    print("  - 80% autonomous code generation")
    print("  - 60% defect reduction")
    print("  - 70% security vulnerability reduction")
    print("-" * 80 + "\n")

    aura_metrics = AuraMetrics()
    pricing = AuraPricing()

    # Run calculation
    calculator = ROICalculator(profile, aura_metrics, pricing)
    report = calculator.generate_report(format="text")

    print(report)

    # Export options
    print("\n" + "=" * 80)
    export = (
        input("\nExport report? (text/markdown/json/no) [no]: ").strip().lower() or "no"
    )

    if export != "no":
        filename = input(
            f"Filename [{company_name.replace(' ', '_')}_roi_report.{export}]: "
        ).strip()
        if not filename:
            filename = f"{company_name.replace(' ', '_')}_roi_report.{export}"

        report_content = calculator.generate_report(format=export)

        with open(filename, "w") as f:
            f.write(report_content)

        print(f"\n✓ Report exported to: {filename}")


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Calculate ROI for Project Aura deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode
  python roi_calculator.py --interactive

  # Quick calculation with defaults
  python roi_calculator.py --developers 500

  # Full customization
  python roi_calculator.py --developers 300 --avg-salary 180000 --format json

  # Export to file
  python roi_calculator.py --developers 500 --output report.txt
        """,
    )

    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--company", type=str, default="Defense Contractor Co.", help="Company name"
    )
    parser.add_argument(
        "--developers", type=int, default=500, help="Number of developers"
    )
    parser.add_argument(
        "--avg-salary", type=int, default=150000, help="Average developer salary (USD)"
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--output", "-o", type=str, help="Export report to file")
    parser.add_argument("--years", type=int, default=5, help="Analysis period in years")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    # Non-interactive mode
    hourly_rate = (args.avg_salary * 1.5) / 2080

    profile = CompanyProfile(
        name=args.company,
        num_developers=args.developers,
        avg_developer_salary=args.avg_salary,
        avg_hourly_rate=hourly_rate,
    )

    aura_metrics = AuraMetrics()
    pricing = AuraPricing()

    calculator = ROICalculator(profile, aura_metrics, pricing)
    report = calculator.generate_report(format=args.format)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"✓ Report exported to: {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
