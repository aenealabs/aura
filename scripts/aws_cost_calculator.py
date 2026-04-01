#!/usr/bin/env python3
"""
AWS Cost Calculator for Project Aura
=====================================
Calculate detailed AWS infrastructure costs for different deployment scenarios.

Usage:
    python aws_cost_calculator.py --scenario development
    python aws_cost_calculator.py --scenario production --developers 500
    python aws_cost_calculator.py --interactive
    python aws_cost_calculator.py --export-csv costs.csv
"""

import argparse
import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class DeploymentScenario(Enum):
    """Deployment scenarios with different resource configurations."""

    MINIMAL = "minimal"  # Bare minimum, single-AZ
    DEVELOPMENT = "development"  # Development environment
    PRODUCTION = "production"  # Production with HA
    ENTERPRISE = "enterprise"  # Multi-region, full HA


class Region(Enum):
    """AWS regions with different pricing."""

    US_EAST_1 = "us-east-1"  # Virginia (commercial)
    US_GOV_WEST_1 = "us-gov-west-1"  # GovCloud West
    US_GOV_EAST_1 = "us-gov-east-1"  # GovCloud East


@dataclass
class AWSPricing:
    """AWS service pricing (per month, unless noted)."""

    # Compute
    eks_control_plane: float = 72.00  # Per cluster
    ec2_t3_medium_hourly: float = 0.0416  # $30/month per instance
    ec2_t3_large_hourly: float = 0.0832  # $60/month per instance
    fargate_vcpu_hourly: float = 0.04048  # Per vCPU-hour
    fargate_gb_hourly: float = 0.004445  # Per GB-hour

    # Databases
    neptune_t3_medium_hourly: float = 0.113  # ~$82/month
    neptune_r5_large_hourly: float = 0.348  # ~$252/month
    opensearch_t3_small_hourly: float = 0.047  # ~$34/month
    opensearch_r6g_large_hourly: float = 0.173  # ~$125/month

    # Storage
    dynamodb_on_demand_write: float = 1.25  # Per million writes
    dynamodb_on_demand_read: float = 0.25  # Per million reads
    dynamodb_storage_gb: float = 0.25  # Per GB-month
    s3_standard_gb: float = 0.023  # Per GB-month
    s3_requests_get_per_1000: float = 0.0004
    s3_requests_put_per_1000: float = 0.005
    ebs_gp3_gb: float = 0.08  # Per GB-month

    # Caching
    elasticache_r6g_large_hourly: float = 0.151  # ~$110/month
    elasticache_r6g_xlarge_hourly: float = 0.302  # ~$220/month

    # Networking
    nat_gateway_hourly: float = 0.045  # ~$32/month
    nat_gateway_data_processing_gb: float = 0.045  # Per GB
    alb_hourly: float = 0.0225  # ~$16/month
    alb_lcu_hourly: float = 0.008  # Load Balancer Capacity Units
    data_transfer_out_gb: float = 0.09  # First 10TB

    # Monitoring & Security
    cloudwatch_logs_ingestion_gb: float = 0.50
    cloudwatch_logs_storage_gb: float = 0.03
    cloudwatch_custom_metrics: float = 0.30  # Per metric
    cloudwatch_alarms: float = 0.10  # Per alarm
    secrets_manager_secret: float = 0.40  # Per secret per month
    cloudtrail_trail: float = 2.00  # First trail free, additional $2
    config_rule: float = 2.00  # Per rule per month

    # AI/ML
    bedrock_claude_sonnet_input_per_1k: float = 0.003  # $3 per 1M tokens
    bedrock_claude_sonnet_output_per_1k: float = 0.015  # $15 per 1M tokens
    bedrock_claude_haiku_input_per_1k: float = 0.00025  # $0.25 per 1M tokens
    bedrock_claude_haiku_output_per_1k: float = 0.00125  # $1.25 per 1M tokens


@dataclass
class InfrastructureConfig:
    """Infrastructure configuration for cost calculation."""

    scenario: DeploymentScenario
    region: Region

    # Compute
    eks_clusters: int = 1
    ec2_t3_medium_count: int = 3
    ec2_t3_large_count: int = 0
    use_fargate: bool = False
    fargate_vcpu_hours: float = 0
    fargate_gb_hours: float = 0

    # Databases
    neptune_instances: int = 1
    neptune_instance_type: str = "t3.medium"
    opensearch_nodes: int = 1
    opensearch_node_type: str = "t3.small"

    # Storage
    s3_storage_gb: float = 100
    s3_get_requests_per_month: int = 10000
    s3_put_requests_per_month: int = 1000
    ebs_volumes_gb: float = 150

    # Caching
    use_elasticache: bool = False
    elasticache_node_type: str = "r6g.large"
    elasticache_nodes: int = 1

    # Networking
    nat_gateways: int = 1
    use_alb: bool = False
    data_transfer_out_gb: float = 10

    # Monitoring
    cloudwatch_log_ingestion_gb: float = 5
    cloudwatch_custom_metrics: int = 20
    cloudwatch_alarms: int = 5
    secrets_count: int = 2
    cloudtrail_enabled: bool = True
    config_rules: int = 5

    # Usage (monthly)
    bedrock_requests_per_month: int = 0
    avg_input_tokens_per_request: int = 3000
    avg_output_tokens_per_request: int = 1500
    bedrock_model: str = "sonnet"  # or "haiku"


class AWSCostCalculator:
    """Calculate AWS costs for Aura infrastructure."""

    def __init__(
        self, config: InfrastructureConfig, pricing: Optional[AWSPricing] = None
    ):
        self.config = config
        self.pricing = pricing or AWSPricing()

        # Apply GovCloud pricing adjustments (typically 10-15% higher)
        if config.region in [Region.US_GOV_WEST_1, Region.US_GOV_EAST_1]:
            self._apply_govcloud_pricing()

    def _apply_govcloud_pricing(self):
        """Apply GovCloud pricing multiplier (10-15% higher than commercial)."""
        multiplier = 1.12  # 12% higher on average

        # Apply to compute and database services
        self.pricing.ec2_t3_medium_hourly *= multiplier
        self.pricing.ec2_t3_large_hourly *= multiplier
        self.pricing.neptune_t3_medium_hourly *= multiplier
        self.pricing.neptune_r5_large_hourly *= multiplier
        self.pricing.opensearch_t3_small_hourly *= multiplier
        self.pricing.opensearch_r6g_large_hourly *= multiplier
        self.pricing.elasticache_r6g_large_hourly *= multiplier
        self.pricing.elasticache_r6g_xlarge_hourly *= multiplier

    def calculate_compute_costs(self) -> Dict[str, float]:
        """Calculate compute (EKS, EC2, Fargate) costs."""
        costs = {}

        # EKS control plane
        costs["eks_control_plane"] = (
            self.config.eks_clusters * self.pricing.eks_control_plane
        )

        # EC2 instances
        hours_per_month = 730
        if self.config.ec2_t3_medium_count > 0:
            costs["ec2_t3_medium"] = (
                self.config.ec2_t3_medium_count
                * self.pricing.ec2_t3_medium_hourly
                * hours_per_month
            )

        if self.config.ec2_t3_large_count > 0:
            costs["ec2_t3_large"] = (
                self.config.ec2_t3_large_count
                * self.pricing.ec2_t3_large_hourly
                * hours_per_month
            )

        # Fargate (if used)
        if self.config.use_fargate:
            costs["fargate_vcpu"] = (
                self.config.fargate_vcpu_hours * self.pricing.fargate_vcpu_hourly
            )
            costs["fargate_memory"] = (
                self.config.fargate_gb_hours * self.pricing.fargate_gb_hourly
            )

        return costs

    def calculate_database_costs(self) -> Dict[str, float]:
        """Calculate database (Neptune, OpenSearch) costs."""
        costs = {}

        hours_per_month = 730

        # Neptune
        if self.config.neptune_instance_type == "t3.medium":
            neptune_hourly = self.pricing.neptune_t3_medium_hourly
        else:
            neptune_hourly = self.pricing.neptune_r5_large_hourly

        costs["neptune"] = (
            self.config.neptune_instances * neptune_hourly * hours_per_month
        )

        # OpenSearch
        if self.config.opensearch_node_type == "t3.small":
            opensearch_hourly = self.pricing.opensearch_t3_small_hourly
        else:
            opensearch_hourly = self.pricing.opensearch_r6g_large_hourly

        costs["opensearch"] = (
            self.config.opensearch_nodes * opensearch_hourly * hours_per_month
        )

        return costs

    def calculate_storage_costs(self) -> Dict[str, float]:
        """Calculate storage (S3, EBS, DynamoDB) costs."""
        costs = {}

        # S3
        costs["s3_storage"] = self.config.s3_storage_gb * self.pricing.s3_standard_gb
        costs["s3_get_requests"] = (
            self.config.s3_get_requests_per_month
            / 1000
            * self.pricing.s3_requests_get_per_1000
        )
        costs["s3_put_requests"] = (
            self.config.s3_put_requests_per_month
            / 1000
            * self.pricing.s3_requests_put_per_1000
        )

        # EBS
        costs["ebs"] = self.config.ebs_volumes_gb * self.pricing.ebs_gp3_gb

        # DynamoDB (minimal for cost tracking table when idle)
        costs["dynamodb"] = 1.00  # Storage cost, minimal reads/writes when idle

        return costs

    def calculate_caching_costs(self) -> Dict[str, float]:
        """Calculate ElastiCache costs."""
        costs = {}

        if self.config.use_elasticache:
            hours_per_month = 730

            if self.config.elasticache_node_type == "r6g.large":
                hourly_rate = self.pricing.elasticache_r6g_large_hourly
            else:
                hourly_rate = self.pricing.elasticache_r6g_xlarge_hourly

            costs["elasticache"] = (
                self.config.elasticache_nodes * hourly_rate * hours_per_month
            )

        return costs

    def calculate_networking_costs(self) -> Dict[str, float]:
        """Calculate networking (NAT, ALB, data transfer) costs."""
        costs = {}

        hours_per_month = 730

        # NAT Gateway
        costs["nat_gateway_hourly"] = (
            self.config.nat_gateways * self.pricing.nat_gateway_hourly * hours_per_month
        )
        costs["nat_gateway_data"] = (
            self.config.data_transfer_out_gb
            * self.pricing.nat_gateway_data_processing_gb
        )

        # ALB (if used)
        if self.config.use_alb:
            costs["alb_hourly"] = self.pricing.alb_hourly * hours_per_month
            costs["alb_lcu"] = (
                self.pricing.alb_lcu_hourly * hours_per_month * 2
            )  # ~2 LCUs

        # Data transfer out
        costs["data_transfer_out"] = (
            self.config.data_transfer_out_gb * self.pricing.data_transfer_out_gb
        )

        return costs

    def calculate_monitoring_costs(self) -> Dict[str, float]:
        """Calculate monitoring and security costs."""
        costs = {}

        # CloudWatch Logs
        costs["cloudwatch_logs_ingestion"] = (
            self.config.cloudwatch_log_ingestion_gb
            * self.pricing.cloudwatch_logs_ingestion_gb
        )
        costs["cloudwatch_logs_storage"] = (
            self.config.cloudwatch_log_ingestion_gb
            * self.pricing.cloudwatch_logs_storage_gb
        )

        # CloudWatch Metrics & Alarms
        costs["cloudwatch_metrics"] = (
            self.config.cloudwatch_custom_metrics
            * self.pricing.cloudwatch_custom_metrics
        )
        costs["cloudwatch_alarms"] = (
            self.config.cloudwatch_alarms * self.pricing.cloudwatch_alarms
        )

        # Secrets Manager
        costs["secrets_manager"] = (
            self.config.secrets_count * self.pricing.secrets_manager_secret
        )

        # CloudTrail
        if self.config.cloudtrail_enabled:
            costs["cloudtrail"] = self.pricing.cloudtrail_trail

        # AWS Config
        costs["aws_config"] = self.config.config_rules * self.pricing.config_rule

        return costs

    def calculate_bedrock_costs(self) -> Dict[str, float]:
        """Calculate Bedrock API costs."""
        costs = {}

        if self.config.bedrock_requests_per_month == 0:
            costs["bedrock"] = 0.0
            return costs

        # Calculate total tokens
        total_input_tokens = (
            self.config.bedrock_requests_per_month
            * self.config.avg_input_tokens_per_request
        )
        total_output_tokens = (
            self.config.bedrock_requests_per_month
            * self.config.avg_output_tokens_per_request
        )

        # Get pricing based on model
        if self.config.bedrock_model == "sonnet":
            input_cost_per_1k = self.pricing.bedrock_claude_sonnet_input_per_1k
            output_cost_per_1k = self.pricing.bedrock_claude_sonnet_output_per_1k
        else:  # haiku
            input_cost_per_1k = self.pricing.bedrock_claude_haiku_input_per_1k
            output_cost_per_1k = self.pricing.bedrock_claude_haiku_output_per_1k

        # Calculate costs
        costs["bedrock_input"] = (total_input_tokens / 1000) * input_cost_per_1k
        costs["bedrock_output"] = (total_output_tokens / 1000) * output_cost_per_1k
        costs["bedrock_total"] = costs["bedrock_input"] + costs["bedrock_output"]

        return costs

    def calculate_total(self) -> Dict[str, Any]:
        """Calculate total costs with breakdown."""

        compute = self.calculate_compute_costs()
        database = self.calculate_database_costs()
        storage = self.calculate_storage_costs()
        caching = self.calculate_caching_costs()
        networking = self.calculate_networking_costs()
        monitoring = self.calculate_monitoring_costs()
        bedrock = self.calculate_bedrock_costs()

        # Calculate category totals
        compute_total = sum(compute.values())
        database_total = sum(database.values())
        storage_total = sum(storage.values())
        caching_total = sum(caching.values())
        networking_total = sum(networking.values())
        monitoring_total = sum(monitoring.values())
        bedrock_total = bedrock.get("bedrock_total", 0)

        # Calculate grand total
        infrastructure_total = (
            compute_total
            + database_total
            + storage_total
            + caching_total
            + networking_total
            + monitoring_total
        )
        grand_total = infrastructure_total + bedrock_total

        return {
            "summary": {
                "scenario": self.config.scenario.value,
                "region": self.config.region.value,
                "infrastructure_total": infrastructure_total,
                "bedrock_total": bedrock_total,
                "grand_total": grand_total,
                "bedrock_requests": self.config.bedrock_requests_per_month,
                "cost_per_request": (
                    bedrock_total / self.config.bedrock_requests_per_month
                    if self.config.bedrock_requests_per_month > 0
                    else 0
                ),
            },
            "breakdown": {
                "compute": {"total": compute_total, "items": compute},
                "database": {"total": database_total, "items": database},
                "storage": {"total": storage_total, "items": storage},
                "caching": {"total": caching_total, "items": caching},
                "networking": {"total": networking_total, "items": networking},
                "monitoring": {"total": monitoring_total, "items": monitoring},
                "bedrock": {"total": bedrock_total, "items": bedrock},
            },
        }

    def generate_report(self, format: str = "text") -> str:
        """Generate cost report in specified format."""

        results = self.calculate_total()

        if format == "json":
            return json.dumps(results, indent=2)
        elif format == "text":
            return self._generate_text_report(results)
        elif format == "markdown":
            return self._generate_markdown_report(results)
        else:
            raise ValueError(f"Unsupported format: {format}")

    def _generate_text_report(self, results: Dict[str, Any]) -> str:
        """Generate text report."""

        summary = results["summary"]
        breakdown = results["breakdown"]

        lines = []
        lines.append("=" * 80)
        lines.append("AWS COST CALCULATOR - PROJECT AURA")
        lines.append("=" * 80)
        lines.append(f"\nScenario: {summary['scenario'].upper()}")
        lines.append(f"Region: {summary['region']}")
        lines.append(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        lines.append("\n" + "-" * 80)
        lines.append("MONTHLY COST SUMMARY")
        lines.append("-" * 80)
        lines.append(
            f"Infrastructure (Idle):       ${summary['infrastructure_total']:,.2f}"
        )
        lines.append(
            f"Bedrock API ({summary['bedrock_requests']:,} requests):  ${summary['bedrock_total']:,.2f}"
        )
        lines.append(f"{'TOTAL MONTHLY COST':.>40} ${summary['grand_total']:,.2f}")

        if summary["bedrock_requests"] > 0:
            lines.append(
                f"\nCost per API request:        ${summary['cost_per_request']:.4f}"
            )

        lines.append("\n" + "-" * 80)
        lines.append("COST BREAKDOWN BY CATEGORY")
        lines.append("-" * 80)

        for category, data in breakdown.items():
            if data["total"] > 0:
                lines.append(f"\n{category.upper()}: ${data['total']:,.2f}")
                for item, cost in data["items"].items():
                    if cost > 0:
                        lines.append(
                            f"  {item.replace('_', ' ').title():.<40} ${cost:,.2f}"
                        )

        lines.append("\n" + "=" * 80)

        return "\n".join(lines)

    def _generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Generate markdown report."""

        summary = results["summary"]
        breakdown = results["breakdown"]

        md = []
        md.append("# AWS Cost Report - Project Aura\n")
        md.append(f"**Scenario:** {summary['scenario'].upper()}  ")
        md.append(f"**Region:** {summary['region']}  ")
        md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}\n")

        md.append("## Monthly Cost Summary\n")
        md.append("| Category | Cost |")
        md.append("|----------|------|")
        md.append(
            f"| Infrastructure (Idle) | ${summary['infrastructure_total']:,.2f} |"
        )
        md.append(
            f"| Bedrock API ({summary['bedrock_requests']:,} requests) | ${summary['bedrock_total']:,.2f} |"
        )
        md.append(f"| **TOTAL** | **${summary['grand_total']:,.2f}** |\n")

        md.append("## Detailed Breakdown\n")

        for category, data in breakdown.items():
            if data["total"] > 0:
                md.append(f"### {category.title()}: ${data['total']:,.2f}\n")
                md.append("| Service | Cost |")
                md.append("|---------|------|")
                for item, cost in data["items"].items():
                    if cost > 0:
                        md.append(
                            f"| {item.replace('_', ' ').title()} | ${cost:,.2f} |"
                        )
                md.append("")

        return "\n".join(md)

    def export_csv(self, filename: str):
        """Export cost breakdown to CSV."""

        results = self.calculate_total()

        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Service", "Monthly Cost"])

            for category, data in results["breakdown"].items():
                for item, cost in data["items"].items():
                    if cost > 0:
                        writer.writerow(
                            [
                                category.title(),
                                item.replace("_", " ").title(),
                                f"${cost:.2f}",
                            ]
                        )

            writer.writerow([])
            writer.writerow(
                [
                    "TOTAL",
                    "Infrastructure",
                    f"${results['summary']['infrastructure_total']:.2f}",
                ]
            )
            writer.writerow(
                ["TOTAL", "Bedrock API", f"${results['summary']['bedrock_total']:.2f}"]
            )
            writer.writerow(
                ["TOTAL", "Grand Total", f"${results['summary']['grand_total']:.2f}"]
            )


def get_preset_config(
    scenario: DeploymentScenario, region: Region = Region.US_GOV_WEST_1
) -> InfrastructureConfig:
    """Get preset configuration for common scenarios."""

    if scenario == DeploymentScenario.MINIMAL:
        return InfrastructureConfig(
            scenario=scenario,
            region=region,
            eks_clusters=1,
            ec2_t3_medium_count=2,
            neptune_instances=1,
            neptune_instance_type="t3.medium",
            opensearch_nodes=1,
            opensearch_node_type="t3.small",
            use_elasticache=False,
            use_alb=False,
            nat_gateways=1,
            cloudwatch_alarms=3,
        )

    elif scenario == DeploymentScenario.DEVELOPMENT:
        return InfrastructureConfig(
            scenario=scenario,
            region=region,
            eks_clusters=1,
            ec2_t3_medium_count=3,
            neptune_instances=1,
            neptune_instance_type="t3.medium",
            opensearch_nodes=1,
            opensearch_node_type="t3.small",
            use_elasticache=False,
            use_alb=False,
            nat_gateways=1,
            cloudwatch_alarms=5,
            bedrock_requests_per_month=3000,  # Light testing
            bedrock_model="sonnet",
        )

    elif scenario == DeploymentScenario.PRODUCTION:
        return InfrastructureConfig(
            scenario=scenario,
            region=region,
            eks_clusters=1,
            ec2_t3_medium_count=5,
            neptune_instances=2,  # HA
            neptune_instance_type="r5.large",
            opensearch_nodes=3,  # HA
            opensearch_node_type="r6g.large",
            use_elasticache=True,
            elasticache_node_type="r6g.large",
            elasticache_nodes=2,
            use_alb=True,
            nat_gateways=2,
            cloudwatch_alarms=10,
            s3_storage_gb=500,
            bedrock_requests_per_month=30000,  # Medium usage
            bedrock_model="sonnet",
        )

    elif scenario == DeploymentScenario.ENTERPRISE:
        return InfrastructureConfig(
            scenario=scenario,
            region=region,
            eks_clusters=2,  # Multi-region
            ec2_t3_large_count=10,
            neptune_instances=3,  # Multi-AZ
            neptune_instance_type="r5.large",
            opensearch_nodes=5,
            opensearch_node_type="r6g.large",
            use_elasticache=True,
            elasticache_node_type="r6g.xlarge",
            elasticache_nodes=3,
            use_alb=True,
            nat_gateways=3,
            cloudwatch_alarms=20,
            config_rules=15,
            s3_storage_gb=2000,
            data_transfer_out_gb=200,
            bedrock_requests_per_month=150000,  # Heavy usage
            bedrock_model="sonnet",
        )


def interactive_mode():
    """Run calculator in interactive mode."""

    print("\n" + "=" * 80)
    print("AWS COST CALCULATOR - PROJECT AURA (INTERACTIVE MODE)")
    print("=" * 80 + "\n")

    # Select scenario
    print("Available scenarios:")
    print("1. Minimal (bare minimum, single-AZ)")
    print("2. Development (testing environment)")
    print("3. Production (HA, multi-AZ)")
    print("4. Enterprise (multi-region, full HA)")
    print("5. Custom (manual configuration)")

    choice = input("\nSelect scenario [1-5]: ").strip()

    scenario_map = {
        "1": DeploymentScenario.MINIMAL,
        "2": DeploymentScenario.DEVELOPMENT,
        "3": DeploymentScenario.PRODUCTION,
        "4": DeploymentScenario.ENTERPRISE,
    }

    if choice in scenario_map:
        scenario = scenario_map[choice]
        config = get_preset_config(scenario)

        # Ask about usage
        usage = input("\nExpected monthly Bedrock API requests [0]: ").strip()
        if usage:
            config.bedrock_requests_per_month = int(usage)

    else:
        print("\nCustom configuration not yet implemented. Using DEVELOPMENT preset.")
        config = get_preset_config(DeploymentScenario.DEVELOPMENT)

    # Calculate and display
    calculator = AWSCostCalculator(config)
    report = calculator.generate_report(format="text")
    print("\n" + report)

    # Export options
    export = (
        input("\nExport report? (text/markdown/csv/json/no) [no]: ").strip().lower()
        or "no"
    )

    if export != "no":
        if export == "csv":
            filename = "aws_costs.csv"
            calculator.export_csv(filename)
            print(f"\n✓ Report exported to: {filename}")
        else:
            filename = f"aws_costs.{export}"
            report_content = calculator.generate_report(format=export)
            with open(filename, "w") as f:
                f.write(report_content)
            print(f"\n✓ Report exported to: {filename}")


def main():
    """Main entry point."""

    parser = argparse.ArgumentParser(
        description="Calculate AWS costs for Project Aura",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--interactive", "-i", action="store_true", help="Run in interactive mode"
    )
    parser.add_argument(
        "--scenario",
        type=str,
        choices=["minimal", "development", "production", "enterprise"],
        default="development",
        help="Deployment scenario",
    )
    parser.add_argument(
        "--region",
        type=str,
        choices=["us-east-1", "us-gov-west-1", "us-gov-east-1"],
        default="us-gov-west-1",
        help="AWS region",
    )
    parser.add_argument(
        "--bedrock-requests",
        type=int,
        default=0,
        help="Expected monthly Bedrock API requests",
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format",
    )
    parser.add_argument("--output", "-o", type=str, help="Export report to file")
    parser.add_argument("--csv", type=str, help="Export to CSV file")

    args = parser.parse_args()

    if args.interactive:
        interactive_mode()
        return

    # Non-interactive mode
    scenario = DeploymentScenario(args.scenario)
    region = Region(args.region)
    config = get_preset_config(scenario, region)
    config.bedrock_requests_per_month = args.bedrock_requests

    calculator = AWSCostCalculator(config)

    if args.csv:
        calculator.export_csv(args.csv)
        print(f"✓ CSV exported to: {args.csv}")
    elif args.output:
        report = calculator.generate_report(format=args.format)
        with open(args.output, "w") as f:
            f.write(report)
        print(f"✓ Report exported to: {args.output}")
    else:
        report = calculator.generate_report(format=args.format)
        print(report)


if __name__ == "__main__":
    main()
