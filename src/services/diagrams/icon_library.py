"""
Cloud Provider Icon Library for Enterprise Diagram Generation (ADR-060).

Provides official AWS, Azure, GCP, and Kubernetes icons with multiple
color rendering modes:
- NATIVE: Official cloud provider colors
- AURA_SEMANTIC: Mapped to Aura design system palette
- MONOCHROME: Single color with opacity variations

Icon Sources:
- AWS: https://aws.amazon.com/architecture/icons/
- Azure: https://learn.microsoft.com/azure/architecture/icons/
- GCP: https://cloud.google.com/icons
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CloudProvider(Enum):
    """Supported cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    KUBERNETES = "kubernetes"
    GENERIC = "generic"


class IconCategory(Enum):
    """Icon categories aligned with cloud service types."""

    COMPUTE = "compute"
    DATABASE = "database"
    STORAGE = "storage"
    NETWORKING = "networking"
    SECURITY = "security"
    ANALYTICS = "analytics"
    ML = "ml"
    INTEGRATION = "integration"
    MANAGEMENT = "management"
    DEVTOOLS = "devtools"
    CONTAINERS = "containers"


class IconColorMode(Enum):
    """Icon color rendering modes (design review)."""

    NATIVE = "native"  # Official cloud provider colors
    AURA_SEMANTIC = "aura"  # Map to Aura's design system palette
    MONOCHROME = "monochrome"  # Single color with opacity variations


# Aura semantic color mapping by category (the design system alignment)
AURA_CATEGORY_COLORS: dict[IconCategory, str] = {
    IconCategory.COMPUTE: "#3B82F6",  # Primary blue
    IconCategory.DATABASE: "#8B5CF6",  # Violet-500
    IconCategory.STORAGE: "#10B981",  # Success green
    IconCategory.NETWORKING: "#6366F1",  # Indigo-500
    IconCategory.SECURITY: "#DC2626",  # Critical red
    IconCategory.ANALYTICS: "#06B6D4",  # Cyan-500
    IconCategory.ML: "#14B8A6",  # Teal-500
    IconCategory.INTEGRATION: "#F59E0B",  # Medium amber
    IconCategory.MANAGEMENT: "#8B5CF6",  # Violet-500
    IconCategory.DEVTOOLS: "#6B7280",  # Gray-500
    IconCategory.CONTAINERS: "#3B82F6",  # Primary blue
}

# Monochrome base color
MONOCHROME_COLOR = "#3B82F6"  # Primary blue


@dataclass
class DiagramIcon:
    """
    Icon metadata for diagram rendering.

    Attributes:
        id: Unique identifier in format 'provider:name' (e.g., 'aws:ec2')
        provider: Cloud provider
        category: Service category
        name: Short name
        svg_path: Relative path to SVG file
        display_name: Human-readable display name
        aliases: Alternative names for fuzzy matching
        native_color: Original provider brand color
        width: Default icon width
        height: Default icon height
    """

    id: str
    provider: CloudProvider
    category: IconCategory
    name: str
    svg_path: str
    display_name: str
    aliases: list[str] = field(default_factory=list)
    native_color: str = "#3B82F6"
    width: int = 48
    height: int = 48

    def get_color(self, mode: IconColorMode) -> str:
        """Get icon color based on rendering mode."""
        if mode == IconColorMode.NATIVE:
            return self.native_color
        elif mode == IconColorMode.AURA_SEMANTIC:
            return AURA_CATEGORY_COLORS.get(self.category, "#3B82F6")
        elif mode == IconColorMode.MONOCHROME:
            return MONOCHROME_COLOR
        return self.native_color


# AWS Architecture Icons (Official)
# Source: https://aws.amazon.com/architecture/icons/
AWS_ICONS: dict[str, DiagramIcon] = {
    # Compute
    "aws:ec2": DiagramIcon(
        id="aws:ec2",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="ec2",
        svg_path="icons/aws/compute/ec2.svg",
        display_name="Amazon EC2",
        aliases=["ec2", "instance", "vm", "virtual-machine"],
        native_color="#FF9900",
    ),
    "aws:lambda": DiagramIcon(
        id="aws:lambda",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="lambda",
        svg_path="icons/aws/compute/lambda.svg",
        display_name="AWS Lambda",
        aliases=["lambda", "function", "serverless", "faas"],
        native_color="#FF9900",
    ),
    "aws:ecs": DiagramIcon(
        id="aws:ecs",
        provider=CloudProvider.AWS,
        category=IconCategory.CONTAINERS,
        name="ecs",
        svg_path="icons/aws/compute/ecs.svg",
        display_name="Amazon ECS",
        aliases=["ecs", "container", "fargate", "docker"],
        native_color="#FF9900",
    ),
    "aws:eks": DiagramIcon(
        id="aws:eks",
        provider=CloudProvider.AWS,
        category=IconCategory.CONTAINERS,
        name="eks",
        svg_path="icons/aws/compute/eks.svg",
        display_name="Amazon EKS",
        aliases=["eks", "kubernetes", "k8s"],
        native_color="#FF9900",
    ),
    "aws:batch": DiagramIcon(
        id="aws:batch",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="batch",
        svg_path="icons/aws/compute/batch.svg",
        display_name="AWS Batch",
        aliases=["batch", "job", "hpc"],
        native_color="#FF9900",
    ),
    # Database
    "aws:rds": DiagramIcon(
        id="aws:rds",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="rds",
        svg_path="icons/aws/database/rds.svg",
        display_name="Amazon RDS",
        aliases=["rds", "database", "mysql", "postgres", "aurora"],
        native_color="#3B48CC",
    ),
    "aws:dynamodb": DiagramIcon(
        id="aws:dynamodb",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="dynamodb",
        svg_path="icons/aws/database/dynamodb.svg",
        display_name="Amazon DynamoDB",
        aliases=["dynamodb", "nosql", "table", "ddb"],
        native_color="#3B48CC",
    ),
    "aws:elasticache": DiagramIcon(
        id="aws:elasticache",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="elasticache",
        svg_path="icons/aws/database/elasticache.svg",
        display_name="Amazon ElastiCache",
        aliases=["elasticache", "redis", "memcached", "cache"],
        native_color="#3B48CC",
    ),
    "aws:neptune": DiagramIcon(
        id="aws:neptune",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="neptune",
        svg_path="icons/aws/database/neptune.svg",
        display_name="Amazon Neptune",
        aliases=["neptune", "graph", "graphdb", "gremlin"],
        native_color="#3B48CC",
    ),
    "aws:opensearch": DiagramIcon(
        id="aws:opensearch",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="opensearch",
        svg_path="icons/aws/database/opensearch.svg",
        display_name="Amazon OpenSearch",
        aliases=["opensearch", "elasticsearch", "search", "vector"],
        native_color="#3B48CC",
    ),
    "aws:documentdb": DiagramIcon(
        id="aws:documentdb",
        provider=CloudProvider.AWS,
        category=IconCategory.DATABASE,
        name="documentdb",
        svg_path="icons/aws/database/documentdb.svg",
        display_name="Amazon DocumentDB",
        aliases=["documentdb", "mongodb", "document"],
        native_color="#3B48CC",
    ),
    # Storage
    "aws:s3": DiagramIcon(
        id="aws:s3",
        provider=CloudProvider.AWS,
        category=IconCategory.STORAGE,
        name="s3",
        svg_path="icons/aws/storage/s3.svg",
        display_name="Amazon S3",
        aliases=["s3", "bucket", "storage", "object"],
        native_color="#3F8624",
    ),
    "aws:efs": DiagramIcon(
        id="aws:efs",
        provider=CloudProvider.AWS,
        category=IconCategory.STORAGE,
        name="efs",
        svg_path="icons/aws/storage/efs.svg",
        display_name="Amazon EFS",
        aliases=["efs", "file-storage", "nfs"],
        native_color="#3F8624",
    ),
    "aws:ebs": DiagramIcon(
        id="aws:ebs",
        provider=CloudProvider.AWS,
        category=IconCategory.STORAGE,
        name="ebs",
        svg_path="icons/aws/storage/ebs.svg",
        display_name="Amazon EBS",
        aliases=["ebs", "block-storage", "volume"],
        native_color="#3F8624",
    ),
    # Networking
    "aws:vpc": DiagramIcon(
        id="aws:vpc",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="vpc",
        svg_path="icons/aws/networking/vpc.svg",
        display_name="Amazon VPC",
        aliases=["vpc", "network", "virtual-network"],
        native_color="#8C4FFF",
    ),
    "aws:alb": DiagramIcon(
        id="aws:alb",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="alb",
        svg_path="icons/aws/networking/elb-alb.svg",
        display_name="Application Load Balancer",
        aliases=["alb", "elb", "load-balancer", "lb"],
        native_color="#8C4FFF",
    ),
    "aws:nlb": DiagramIcon(
        id="aws:nlb",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="nlb",
        svg_path="icons/aws/networking/elb-nlb.svg",
        display_name="Network Load Balancer",
        aliases=["nlb", "network-load-balancer"],
        native_color="#8C4FFF",
    ),
    "aws:cloudfront": DiagramIcon(
        id="aws:cloudfront",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="cloudfront",
        svg_path="icons/aws/networking/cloudfront.svg",
        display_name="Amazon CloudFront",
        aliases=["cloudfront", "cdn"],
        native_color="#8C4FFF",
    ),
    "aws:api-gateway": DiagramIcon(
        id="aws:api-gateway",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="api-gateway",
        svg_path="icons/aws/networking/api-gateway.svg",
        display_name="Amazon API Gateway",
        aliases=["api-gateway", "apigw", "api"],
        native_color="#FF4F8B",
    ),
    "aws:route53": DiagramIcon(
        id="aws:route53",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="route53",
        svg_path="icons/aws/networking/route53.svg",
        display_name="Amazon Route 53",
        aliases=["route53", "dns"],
        native_color="#8C4FFF",
    ),
    "aws:internet-gateway": DiagramIcon(
        id="aws:internet-gateway",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="internet-gateway",
        svg_path="icons/aws/networking/internet-gateway.svg",
        display_name="Internet Gateway",
        aliases=["internet-gateway", "igw", "internet"],
        native_color="#8C4FFF",
    ),
    "aws:nat-gateway": DiagramIcon(
        id="aws:nat-gateway",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="nat-gateway",
        svg_path="icons/aws/networking/nat-gateway.svg",
        display_name="NAT Gateway",
        aliases=["nat-gateway", "nat", "natgw"],
        native_color="#8C4FFF",
    ),
    "aws:security-group": DiagramIcon(
        id="aws:security-group",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="security-group",
        svg_path="icons/aws/security/security-group.svg",
        display_name="Security Group",
        aliases=["security-group", "sg", "firewall"],
        native_color="#DD344C",
    ),
    "aws:auto-scaling": DiagramIcon(
        id="aws:auto-scaling",
        provider=CloudProvider.AWS,
        category=IconCategory.COMPUTE,
        name="auto-scaling",
        svg_path="icons/aws/compute/auto-scaling.svg",
        display_name="Auto Scaling Group",
        aliases=["auto-scaling", "asg", "autoscaling", "scaling"],
        native_color="#FF9900",
    ),
    "aws:subnet": DiagramIcon(
        id="aws:subnet",
        provider=CloudProvider.AWS,
        category=IconCategory.NETWORKING,
        name="subnet",
        svg_path="icons/aws/networking/subnet.svg",
        display_name="Subnet",
        aliases=["subnet", "subnets"],
        native_color="#8C4FFF",
    ),
    # Security
    "aws:cognito": DiagramIcon(
        id="aws:cognito",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="cognito",
        svg_path="icons/aws/security/cognito.svg",
        display_name="Amazon Cognito",
        aliases=["cognito", "auth", "identity", "idp"],
        native_color="#DD344C",
    ),
    "aws:iam": DiagramIcon(
        id="aws:iam",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="iam",
        svg_path="icons/aws/security/iam.svg",
        display_name="AWS IAM",
        aliases=["iam", "identity", "access"],
        native_color="#DD344C",
    ),
    "aws:secrets-manager": DiagramIcon(
        id="aws:secrets-manager",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="secrets-manager",
        svg_path="icons/aws/security/secrets-manager.svg",
        display_name="AWS Secrets Manager",
        aliases=["secrets-manager", "secrets"],
        native_color="#DD344C",
    ),
    "aws:kms": DiagramIcon(
        id="aws:kms",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="kms",
        svg_path="icons/aws/security/kms.svg",
        display_name="AWS KMS",
        aliases=["kms", "key", "encryption"],
        native_color="#DD344C",
    ),
    "aws:waf": DiagramIcon(
        id="aws:waf",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="waf",
        svg_path="icons/aws/security/waf.svg",
        display_name="AWS WAF",
        aliases=["waf", "firewall", "web-firewall"],
        native_color="#DD344C",
    ),
    "aws:guardduty": DiagramIcon(
        id="aws:guardduty",
        provider=CloudProvider.AWS,
        category=IconCategory.SECURITY,
        name="guardduty",
        svg_path="icons/aws/security/guardduty.svg",
        display_name="Amazon GuardDuty",
        aliases=["guardduty", "threat-detection"],
        native_color="#DD344C",
    ),
    # Management
    "aws:cloudwatch": DiagramIcon(
        id="aws:cloudwatch",
        provider=CloudProvider.AWS,
        category=IconCategory.MANAGEMENT,
        name="cloudwatch",
        svg_path="icons/aws/management/cloudwatch.svg",
        display_name="Amazon CloudWatch",
        aliases=["cloudwatch", "monitoring", "logs", "metrics"],
        native_color="#FF4F8B",
    ),
    "aws:cloudformation": DiagramIcon(
        id="aws:cloudformation",
        provider=CloudProvider.AWS,
        category=IconCategory.MANAGEMENT,
        name="cloudformation",
        svg_path="icons/aws/management/cloudformation.svg",
        display_name="AWS CloudFormation",
        aliases=["cloudformation", "cfn", "iac"],
        native_color="#FF4F8B",
    ),
    "aws:ssm": DiagramIcon(
        id="aws:ssm",
        provider=CloudProvider.AWS,
        category=IconCategory.MANAGEMENT,
        name="ssm",
        svg_path="icons/aws/management/ssm.svg",
        display_name="AWS Systems Manager",
        aliases=["ssm", "systems-manager", "parameter-store"],
        native_color="#FF4F8B",
    ),
    # ML
    "aws:bedrock": DiagramIcon(
        id="aws:bedrock",
        provider=CloudProvider.AWS,
        category=IconCategory.ML,
        name="bedrock",
        svg_path="icons/aws/ml/bedrock.svg",
        display_name="Amazon Bedrock",
        aliases=["bedrock", "llm", "ai", "claude", "foundation-model"],
        native_color="#01A88D",
    ),
    "aws:sagemaker": DiagramIcon(
        id="aws:sagemaker",
        provider=CloudProvider.AWS,
        category=IconCategory.ML,
        name="sagemaker",
        svg_path="icons/aws/ml/sagemaker.svg",
        display_name="Amazon SageMaker",
        aliases=["sagemaker", "ml", "training", "inference"],
        native_color="#01A88D",
    ),
    # Integration
    "aws:sqs": DiagramIcon(
        id="aws:sqs",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="sqs",
        svg_path="icons/aws/integration/sqs.svg",
        display_name="Amazon SQS",
        aliases=["sqs", "queue", "message"],
        native_color="#FF4F8B",
    ),
    "aws:sns": DiagramIcon(
        id="aws:sns",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="sns",
        svg_path="icons/aws/integration/sns.svg",
        display_name="Amazon SNS",
        aliases=["sns", "notification", "topic", "pub-sub"],
        native_color="#FF4F8B",
    ),
    "aws:eventbridge": DiagramIcon(
        id="aws:eventbridge",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="eventbridge",
        svg_path="icons/aws/integration/eventbridge.svg",
        display_name="Amazon EventBridge",
        aliases=["eventbridge", "events", "bus", "event-bus"],
        native_color="#FF4F8B",
    ),
    "aws:step-functions": DiagramIcon(
        id="aws:step-functions",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="step-functions",
        svg_path="icons/aws/integration/step-functions.svg",
        display_name="AWS Step Functions",
        aliases=["step-functions", "workflow", "state-machine", "sfn"],
        native_color="#FF4F8B",
    ),
    "aws:kinesis": DiagramIcon(
        id="aws:kinesis",
        provider=CloudProvider.AWS,
        category=IconCategory.INTEGRATION,
        name="kinesis",
        svg_path="icons/aws/integration/kinesis.svg",
        display_name="Amazon Kinesis",
        aliases=["kinesis", "stream", "streaming"],
        native_color="#FF4F8B",
    ),
    # DevTools
    "aws:codebuild": DiagramIcon(
        id="aws:codebuild",
        provider=CloudProvider.AWS,
        category=IconCategory.DEVTOOLS,
        name="codebuild",
        svg_path="icons/aws/devtools/codebuild.svg",
        display_name="AWS CodeBuild",
        aliases=["codebuild", "build", "ci"],
        native_color="#3B82F6",
    ),
    "aws:codepipeline": DiagramIcon(
        id="aws:codepipeline",
        provider=CloudProvider.AWS,
        category=IconCategory.DEVTOOLS,
        name="codepipeline",
        svg_path="icons/aws/devtools/codepipeline.svg",
        display_name="AWS CodePipeline",
        aliases=["codepipeline", "pipeline", "cd"],
        native_color="#3B82F6",
    ),
    "aws:ecr": DiagramIcon(
        id="aws:ecr",
        provider=CloudProvider.AWS,
        category=IconCategory.CONTAINERS,
        name="ecr",
        svg_path="icons/aws/containers/ecr.svg",
        display_name="Amazon ECR",
        aliases=["ecr", "registry", "container-registry"],
        native_color="#FF9900",
    ),
}

# Azure Icons (Official)
# Source: https://learn.microsoft.com/azure/architecture/icons/
AZURE_ICONS: dict[str, DiagramIcon] = {
    "azure:vm": DiagramIcon(
        id="azure:vm",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="vm",
        svg_path="icons/azure/compute/virtual-machine.svg",
        display_name="Azure Virtual Machine",
        aliases=["vm", "virtual-machine"],
        native_color="#0078D4",
    ),
    "azure:aks": DiagramIcon(
        id="azure:aks",
        provider=CloudProvider.AZURE,
        category=IconCategory.CONTAINERS,
        name="aks",
        svg_path="icons/azure/compute/aks.svg",
        display_name="Azure Kubernetes Service",
        aliases=["aks", "kubernetes", "k8s"],
        native_color="#0078D4",
    ),
    "azure:app-service": DiagramIcon(
        id="azure:app-service",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="app-service",
        svg_path="icons/azure/compute/app-service.svg",
        display_name="Azure App Service",
        aliases=["app-service", "webapp"],
        native_color="#0078D4",
    ),
    "azure:functions": DiagramIcon(
        id="azure:functions",
        provider=CloudProvider.AZURE,
        category=IconCategory.COMPUTE,
        name="functions",
        svg_path="icons/azure/compute/functions.svg",
        display_name="Azure Functions",
        aliases=["functions", "serverless", "faas"],
        native_color="#0078D4",
    ),
    "azure:sql-database": DiagramIcon(
        id="azure:sql-database",
        provider=CloudProvider.AZURE,
        category=IconCategory.DATABASE,
        name="sql-database",
        svg_path="icons/azure/database/sql-database.svg",
        display_name="Azure SQL Database",
        aliases=["sql", "database", "sql-server"],
        native_color="#0078D4",
    ),
    "azure:cosmos-db": DiagramIcon(
        id="azure:cosmos-db",
        provider=CloudProvider.AZURE,
        category=IconCategory.DATABASE,
        name="cosmos-db",
        svg_path="icons/azure/database/cosmos-db.svg",
        display_name="Azure Cosmos DB",
        aliases=["cosmos", "cosmosdb", "nosql"],
        native_color="#0078D4",
    ),
    "azure:storage": DiagramIcon(
        id="azure:storage",
        provider=CloudProvider.AZURE,
        category=IconCategory.STORAGE,
        name="storage",
        svg_path="icons/azure/storage/storage-account.svg",
        display_name="Azure Storage",
        aliases=["storage", "blob", "storage-account"],
        native_color="#0078D4",
    ),
    "azure:key-vault": DiagramIcon(
        id="azure:key-vault",
        provider=CloudProvider.AZURE,
        category=IconCategory.SECURITY,
        name="key-vault",
        svg_path="icons/azure/security/key-vault.svg",
        display_name="Azure Key Vault",
        aliases=["key-vault", "secrets", "keys"],
        native_color="#0078D4",
    ),
    "azure:monitor": DiagramIcon(
        id="azure:monitor",
        provider=CloudProvider.AZURE,
        category=IconCategory.MANAGEMENT,
        name="monitor",
        svg_path="icons/azure/management/monitor.svg",
        display_name="Azure Monitor",
        aliases=["monitor", "monitoring", "logs"],
        native_color="#0078D4",
    ),
    "azure:openai": DiagramIcon(
        id="azure:openai",
        provider=CloudProvider.AZURE,
        category=IconCategory.ML,
        name="openai",
        svg_path="icons/azure/ml/openai.svg",
        display_name="Azure OpenAI",
        aliases=["openai", "gpt", "llm", "ai"],
        native_color="#0078D4",
    ),
    "azure:service-bus": DiagramIcon(
        id="azure:service-bus",
        provider=CloudProvider.AZURE,
        category=IconCategory.INTEGRATION,
        name="service-bus",
        svg_path="icons/azure/integration/service-bus.svg",
        display_name="Azure Service Bus",
        aliases=["service-bus", "queue", "messaging"],
        native_color="#0078D4",
    ),
    "azure:event-hub": DiagramIcon(
        id="azure:event-hub",
        provider=CloudProvider.AZURE,
        category=IconCategory.INTEGRATION,
        name="event-hub",
        svg_path="icons/azure/integration/event-hub.svg",
        display_name="Azure Event Hubs",
        aliases=["event-hub", "streaming", "events"],
        native_color="#0078D4",
    ),
}

# GCP Icons (Official)
# Source: https://cloud.google.com/icons
GCP_ICONS: dict[str, DiagramIcon] = {
    "gcp:compute-engine": DiagramIcon(
        id="gcp:compute-engine",
        provider=CloudProvider.GCP,
        category=IconCategory.COMPUTE,
        name="compute-engine",
        svg_path="icons/gcp/compute/compute-engine.svg",
        display_name="Google Compute Engine",
        aliases=["gce", "compute-engine", "vm"],
        native_color="#4285F4",
    ),
    "gcp:gke": DiagramIcon(
        id="gcp:gke",
        provider=CloudProvider.GCP,
        category=IconCategory.CONTAINERS,
        name="gke",
        svg_path="icons/gcp/compute/gke.svg",
        display_name="Google Kubernetes Engine",
        aliases=["gke", "kubernetes", "k8s"],
        native_color="#4285F4",
    ),
    "gcp:cloud-run": DiagramIcon(
        id="gcp:cloud-run",
        provider=CloudProvider.GCP,
        category=IconCategory.COMPUTE,
        name="cloud-run",
        svg_path="icons/gcp/compute/cloud-run.svg",
        display_name="Cloud Run",
        aliases=["cloud-run", "serverless", "container"],
        native_color="#4285F4",
    ),
    "gcp:cloud-functions": DiagramIcon(
        id="gcp:cloud-functions",
        provider=CloudProvider.GCP,
        category=IconCategory.COMPUTE,
        name="cloud-functions",
        svg_path="icons/gcp/compute/cloud-functions.svg",
        display_name="Cloud Functions",
        aliases=["cloud-functions", "functions", "faas"],
        native_color="#4285F4",
    ),
    "gcp:cloud-sql": DiagramIcon(
        id="gcp:cloud-sql",
        provider=CloudProvider.GCP,
        category=IconCategory.DATABASE,
        name="cloud-sql",
        svg_path="icons/gcp/database/cloud-sql.svg",
        display_name="Cloud SQL",
        aliases=["cloud-sql", "sql", "database"],
        native_color="#4285F4",
    ),
    "gcp:firestore": DiagramIcon(
        id="gcp:firestore",
        provider=CloudProvider.GCP,
        category=IconCategory.DATABASE,
        name="firestore",
        svg_path="icons/gcp/database/firestore.svg",
        display_name="Firestore",
        aliases=["firestore", "nosql", "document"],
        native_color="#4285F4",
    ),
    "gcp:bigtable": DiagramIcon(
        id="gcp:bigtable",
        provider=CloudProvider.GCP,
        category=IconCategory.DATABASE,
        name="bigtable",
        svg_path="icons/gcp/database/bigtable.svg",
        display_name="Cloud Bigtable",
        aliases=["bigtable", "nosql", "wide-column"],
        native_color="#4285F4",
    ),
    "gcp:cloud-storage": DiagramIcon(
        id="gcp:cloud-storage",
        provider=CloudProvider.GCP,
        category=IconCategory.STORAGE,
        name="cloud-storage",
        svg_path="icons/gcp/storage/cloud-storage.svg",
        display_name="Cloud Storage",
        aliases=["gcs", "cloud-storage", "bucket"],
        native_color="#4285F4",
    ),
    "gcp:vertex-ai": DiagramIcon(
        id="gcp:vertex-ai",
        provider=CloudProvider.GCP,
        category=IconCategory.ML,
        name="vertex-ai",
        svg_path="icons/gcp/ml/vertex-ai.svg",
        display_name="Vertex AI",
        aliases=["vertex", "vertex-ai", "ml", "gemini"],
        native_color="#4285F4",
    ),
    "gcp:pubsub": DiagramIcon(
        id="gcp:pubsub",
        provider=CloudProvider.GCP,
        category=IconCategory.INTEGRATION,
        name="pubsub",
        svg_path="icons/gcp/integration/pubsub.svg",
        display_name="Cloud Pub/Sub",
        aliases=["pubsub", "pub-sub", "messaging"],
        native_color="#4285F4",
    ),
}

# Kubernetes Icons
KUBERNETES_ICONS: dict[str, DiagramIcon] = {
    "k8s:pod": DiagramIcon(
        id="k8s:pod",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.CONTAINERS,
        name="pod",
        svg_path="icons/kubernetes/pod.svg",
        display_name="Pod",
        aliases=["pod"],
        native_color="#326CE5",
    ),
    "k8s:deployment": DiagramIcon(
        id="k8s:deployment",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.CONTAINERS,
        name="deployment",
        svg_path="icons/kubernetes/deployment.svg",
        display_name="Deployment",
        aliases=["deployment", "deploy"],
        native_color="#326CE5",
    ),
    "k8s:service": DiagramIcon(
        id="k8s:service",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.NETWORKING,
        name="service",
        svg_path="icons/kubernetes/service.svg",
        display_name="Service",
        aliases=["service", "svc"],
        native_color="#326CE5",
    ),
    "k8s:configmap": DiagramIcon(
        id="k8s:configmap",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.MANAGEMENT,
        name="configmap",
        svg_path="icons/kubernetes/configmap.svg",
        display_name="ConfigMap",
        aliases=["configmap", "config"],
        native_color="#326CE5",
    ),
    "k8s:secret": DiagramIcon(
        id="k8s:secret",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.SECURITY,
        name="secret",
        svg_path="icons/kubernetes/secret.svg",
        display_name="Secret",
        aliases=["secret"],
        native_color="#326CE5",
    ),
    "k8s:ingress": DiagramIcon(
        id="k8s:ingress",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.NETWORKING,
        name="ingress",
        svg_path="icons/kubernetes/ingress.svg",
        display_name="Ingress",
        aliases=["ingress"],
        native_color="#326CE5",
    ),
    "k8s:namespace": DiagramIcon(
        id="k8s:namespace",
        provider=CloudProvider.KUBERNETES,
        category=IconCategory.MANAGEMENT,
        name="namespace",
        svg_path="icons/kubernetes/namespace.svg",
        display_name="Namespace",
        aliases=["namespace", "ns"],
        native_color="#326CE5",
    ),
}

# Generic icons for non-cloud-specific components
GENERIC_ICONS: dict[str, DiagramIcon] = {
    "generic:user": DiagramIcon(
        id="generic:user",
        provider=CloudProvider.GENERIC,
        category=(
            IconCategory.GENERIC
            if hasattr(IconCategory, "GENERIC")
            else IconCategory.MANAGEMENT
        ),
        name="user",
        svg_path="icons/generic/user.svg",
        display_name="User",
        aliases=["user", "person", "actor"],
        native_color="#6B7280",
    ),
    "generic:browser": DiagramIcon(
        id="generic:browser",
        provider=CloudProvider.GENERIC,
        category=IconCategory.MANAGEMENT,
        name="browser",
        svg_path="icons/generic/browser.svg",
        display_name="Browser",
        aliases=["browser", "web", "client"],
        native_color="#6B7280",
    ),
    "generic:database": DiagramIcon(
        id="generic:database",
        provider=CloudProvider.GENERIC,
        category=IconCategory.DATABASE,
        name="database",
        svg_path="icons/generic/database.svg",
        display_name="Database",
        aliases=["database", "db"],
        native_color="#6B7280",
    ),
    "generic:server": DiagramIcon(
        id="generic:server",
        provider=CloudProvider.GENERIC,
        category=IconCategory.COMPUTE,
        name="server",
        svg_path="icons/generic/server.svg",
        display_name="Server",
        aliases=["server", "host"],
        native_color="#6B7280",
    ),
    "generic:api": DiagramIcon(
        id="generic:api",
        provider=CloudProvider.GENERIC,
        category=IconCategory.INTEGRATION,
        name="api",
        svg_path="icons/generic/api.svg",
        display_name="API",
        aliases=["api", "rest", "endpoint"],
        native_color="#6B7280",
    ),
}


# =============================================================================
# EMBEDDED SVG ICONS - Professional AWS Architecture Icon Representations
# =============================================================================
# These are high-quality SVG paths that follow AWS architecture icon styling.
# Icons use the official AWS orange (#FF9900) and service-specific colors.
# Each icon is designed to render at 48x48 pixels with proper scaling.

EMBEDDED_ICONS: dict[str, str] = {
    # -------------------------------------------------------------------------
    # AWS COMPUTE ICONS
    # -------------------------------------------------------------------------
    "aws:ec2": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ec2-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ec2-grad)"/>
  <rect x="10" y="12" width="28" height="24" rx="2" fill="white" opacity="0.95"/>
  <rect x="14" y="16" width="20" height="4" rx="1" fill="#232F3E"/>
  <rect x="14" y="22" width="20" height="4" rx="1" fill="#232F3E"/>
  <rect x="14" y="28" width="12" height="4" rx="1" fill="#232F3E"/>
  <circle cx="34" cy="30" r="3" fill="#FF9900"/>
</svg>""",
    "aws:lambda": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="lambda-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#lambda-grad)"/>
  <path d="M14 36L20 24L14 12H20L28 24L20 36H14Z" fill="white"/>
  <path d="M24 36L30 24L24 12H30L38 24L30 36H24Z" fill="white" opacity="0.7"/>
</svg>""",
    "aws:ecs": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ecs-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ecs-grad)"/>
  <rect x="10" y="10" width="12" height="12" rx="2" fill="white"/>
  <rect x="26" y="10" width="12" height="12" rx="2" fill="white"/>
  <rect x="10" y="26" width="12" height="12" rx="2" fill="white"/>
  <rect x="26" y="26" width="12" height="12" rx="2" fill="white" opacity="0.6"/>
  <circle cx="16" cy="16" r="3" fill="#232F3E"/>
  <circle cx="32" cy="16" r="3" fill="#232F3E"/>
  <circle cx="16" cy="32" r="3" fill="#232F3E"/>
</svg>""",
    "aws:eks": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="eks-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#eks-grad)"/>
  <polygon points="24,10 38,20 38,32 24,42 10,32 10,20" fill="white" opacity="0.95"/>
  <polygon points="24,14 34,21 34,31 24,38 14,31 14,21" fill="#326CE5"/>
  <polygon points="24,18 29,22 29,28 24,32 19,28 19,22" fill="white"/>
</svg>""",
    "aws:batch": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="batch-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#batch-grad)"/>
  <rect x="10" y="12" width="28" height="6" rx="1" fill="white"/>
  <rect x="10" y="21" width="28" height="6" rx="1" fill="white" opacity="0.85"/>
  <rect x="10" y="30" width="28" height="6" rx="1" fill="white" opacity="0.7"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS DATABASE ICONS
    # -------------------------------------------------------------------------
    "aws:rds": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="rds-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#rds-grad)"/>
  <ellipse cx="24" cy="14" rx="14" ry="5" fill="white"/>
  <path d="M10 14v20c0 2.8 6.3 5 14 5s14-2.2 14-5V14" fill="none" stroke="white" stroke-width="2"/>
  <ellipse cx="24" cy="24" rx="14" ry="5" fill="none" stroke="white" stroke-width="1.5"/>
  <ellipse cx="24" cy="34" rx="14" ry="5" fill="none" stroke="white" stroke-width="1.5"/>
</svg>""",
    "aws:dynamodb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ddb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ddb-grad)"/>
  <path d="M12 16L24 10L36 16V32L24 38L12 32V16Z" fill="white"/>
  <path d="M24 10V38" stroke="#3B48CC" stroke-width="1.5"/>
  <path d="M12 16L36 32" stroke="#3B48CC" stroke-width="1"/>
  <path d="M36 16L12 32" stroke="#3B48CC" stroke-width="1"/>
  <path d="M12 24H36" stroke="#3B48CC" stroke-width="1.5"/>
</svg>""",
    "aws:neptune": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="neptune-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#neptune-grad)"/>
  <circle cx="24" cy="24" r="12" fill="none" stroke="white" stroke-width="2"/>
  <circle cx="24" cy="14" r="3" fill="white"/>
  <circle cx="14" cy="29" r="3" fill="white"/>
  <circle cx="34" cy="29" r="3" fill="white"/>
  <line x1="24" y1="17" x2="16" y2="27" stroke="white" stroke-width="2"/>
  <line x1="24" y1="17" x2="32" y2="27" stroke="white" stroke-width="2"/>
  <line x1="17" y1="29" x2="31" y2="29" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:opensearch": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="os-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#os-grad)"/>
  <circle cx="22" cy="22" r="10" fill="none" stroke="white" stroke-width="3"/>
  <line x1="29" y1="29" x2="38" y2="38" stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="22" cy="22" r="4" fill="white" opacity="0.5"/>
</svg>""",
    "aws:elasticache": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cache-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cache-grad)"/>
  <polygon points="24,10 38,24 24,38 10,24" fill="white"/>
  <polygon points="24,16 32,24 24,32 16,24" fill="#3B48CC"/>
  <circle cx="24" cy="24" r="4" fill="white"/>
</svg>""",
    "aws:documentdb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="docdb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B48CC"/>
      <stop offset="100%" style="stop-color:#2D3A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#docdb-grad)"/>
  <rect x="12" y="10" width="24" height="28" rx="2" fill="white"/>
  <rect x="16" y="14" width="16" height="3" fill="#3B48CC"/>
  <rect x="16" y="20" width="12" height="2" fill="#3B48CC" opacity="0.6"/>
  <rect x="16" y="25" width="14" height="2" fill="#3B48CC" opacity="0.6"/>
  <rect x="16" y="30" width="10" height="2" fill="#3B48CC" opacity="0.6"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS STORAGE ICONS
    # -------------------------------------------------------------------------
    "aws:s3": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="s3-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3F8624"/>
      <stop offset="100%" style="stop-color:#2E6319"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#s3-grad)"/>
  <path d="M10 30L24 36L38 30V18L24 12L10 18V30Z" fill="white"/>
  <path d="M24 24L38 18M24 24L10 18M24 24V36" stroke="#3F8624" stroke-width="1.5"/>
  <ellipse cx="24" cy="18" rx="8" ry="3" fill="#3F8624" opacity="0.3"/>
</svg>""",
    "aws:efs": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="efs-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3F8624"/>
      <stop offset="100%" style="stop-color:#2E6319"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#efs-grad)"/>
  <rect x="12" y="14" width="24" height="20" rx="2" fill="white"/>
  <rect x="16" y="18" width="16" height="4" fill="#3F8624"/>
  <rect x="16" y="24" width="16" height="4" fill="#3F8624" opacity="0.7"/>
  <rect x="16" y="30" width="8" height="2" fill="#3F8624" opacity="0.5"/>
</svg>""",
    "aws:ebs": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ebs-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3F8624"/>
      <stop offset="100%" style="stop-color:#2E6319"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ebs-grad)"/>
  <rect x="14" y="10" width="20" height="28" rx="3" fill="white"/>
  <rect x="18" y="14" width="12" height="8" rx="1" fill="#3F8624"/>
  <rect x="18" y="26" width="12" height="2" fill="#3F8624" opacity="0.5"/>
  <rect x="18" y="30" width="8" height="2" fill="#3F8624" opacity="0.5"/>
  <circle cx="24" cy="36" r="2" fill="#3F8624"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS NETWORKING ICONS
    # -------------------------------------------------------------------------
    "aws:vpc": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="vpc-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#vpc-grad)"/>
  <rect x="10" y="10" width="28" height="28" rx="3" fill="none" stroke="white" stroke-width="2" stroke-dasharray="4,2"/>
  <rect x="14" y="14" width="8" height="8" rx="1" fill="white"/>
  <rect x="26" y="14" width="8" height="8" rx="1" fill="white"/>
  <rect x="14" y="26" width="8" height="8" rx="1" fill="white"/>
  <rect x="26" y="26" width="8" height="8" rx="1" fill="white" opacity="0.6"/>
</svg>""",
    "aws:alb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="alb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#alb-grad)"/>
  <circle cx="24" cy="24" r="14" fill="white"/>
  <circle cx="24" cy="24" r="10" fill="none" stroke="#8C4FFF" stroke-width="2"/>
  <line x1="14" y1="24" x2="34" y2="24" stroke="#8C4FFF" stroke-width="2"/>
  <line x1="24" y1="14" x2="24" y2="34" stroke="#8C4FFF" stroke-width="2"/>
  <circle cx="24" cy="24" r="4" fill="#8C4FFF"/>
</svg>""",
    "aws:nlb": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="nlb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#nlb-grad)"/>
  <polygon points="24,10 38,24 24,38 10,24" fill="white"/>
  <polygon points="24,16 32,24 24,32 16,24" fill="#8C4FFF"/>
</svg>""",
    "aws:cloudfront": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cf-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cf-grad)"/>
  <circle cx="24" cy="24" r="14" fill="white"/>
  <circle cx="24" cy="24" r="10" fill="none" stroke="#8C4FFF" stroke-width="1.5"/>
  <circle cx="24" cy="24" r="6" fill="none" stroke="#8C4FFF" stroke-width="1.5"/>
  <path d="M10 24 Q17 18 24 24 Q31 30 38 24" fill="none" stroke="#8C4FFF" stroke-width="1.5"/>
</svg>""",
    "aws:api-gateway": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="apigw-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#apigw-grad)"/>
  <rect x="12" y="18" width="8" height="12" rx="1" fill="white"/>
  <rect x="28" y="12" width="8" height="8" rx="1" fill="white"/>
  <rect x="28" y="22" width="8" height="8" rx="1" fill="white"/>
  <rect x="28" y="32" width="8" height="6" rx="1" fill="white" opacity="0.7"/>
  <line x1="20" y1="24" x2="28" y2="16" stroke="white" stroke-width="2"/>
  <line x1="20" y1="24" x2="28" y2="26" stroke="white" stroke-width="2"/>
  <line x1="20" y1="24" x2="28" y2="35" stroke="white" stroke-width="1.5" opacity="0.7"/>
</svg>""",
    "aws:route53": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="r53-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#r53-grad)"/>
  <text x="24" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="16" font-weight="bold" fill="white">53</text>
  <path d="M12 16 Q24 10 36 16" fill="none" stroke="white" stroke-width="2"/>
  <path d="M12 34 Q24 40 36 34" fill="none" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:internet-gateway": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="igw-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#igw-grad)"/>
  <circle cx="24" cy="16" r="6" fill="white"/>
  <rect x="20" y="22" width="8" height="16" rx="1" fill="white"/>
  <path d="M14 36 L24 42 L34 36" fill="none" stroke="white" stroke-width="2"/>
  <circle cx="24" cy="16" r="3" fill="#8C4FFF"/>
  <path d="M18 28 L24 22 L30 28" fill="none" stroke="#8C4FFF" stroke-width="2"/>
</svg>""",
    "aws:nat-gateway": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="nat-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#nat-grad)"/>
  <rect x="10" y="14" width="28" height="20" rx="2" fill="white"/>
  <path d="M16 24 L20 20 L20 28 Z" fill="#8C4FFF"/>
  <path d="M32 24 L28 20 L28 28 Z" fill="#8C4FFF"/>
  <line x1="20" y1="24" x2="28" y2="24" stroke="#8C4FFF" stroke-width="2"/>
  <circle cx="24" cy="24" r="3" fill="none" stroke="#8C4FFF" stroke-width="1.5"/>
</svg>""",
    "aws:security-group": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sg-grad)"/>
  <path d="M24 8L38 14V26C38 34 31 40 24 42C17 40 10 34 10 26V14L24 8Z" fill="white"/>
  <path d="M24 12L34 16V26C34 32 29 36 24 38C19 36 14 32 14 26V16L24 12Z" fill="none" stroke="#DD344C" stroke-width="2"/>
  <circle cx="24" cy="24" r="4" fill="#DD344C"/>
  <path d="M20 24 H18 M28 24 H30 M24 20 V18 M24 28 V30" stroke="#DD344C" stroke-width="2" stroke-linecap="round"/>
</svg>""",
    "aws:auto-scaling": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="asg-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#asg-grad)"/>
  <rect x="10" y="18" width="10" height="12" rx="1" fill="white"/>
  <rect x="19" y="14" width="10" height="16" rx="1" fill="white" opacity="0.85"/>
  <rect x="28" y="18" width="10" height="12" rx="1" fill="white" opacity="0.7"/>
  <path d="M14 36 L24 40 L34 36" fill="none" stroke="white" stroke-width="2"/>
  <path d="M14 12 L24 8 L34 12" fill="none" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:subnet": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="subnet-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#8C4FFF"/>
      <stop offset="100%" style="stop-color:#6B35CC"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#subnet-grad)"/>
  <rect x="10" y="10" width="28" height="28" rx="2" fill="none" stroke="white" stroke-width="2"/>
  <line x1="10" y1="20" x2="38" y2="20" stroke="white" stroke-width="1.5" stroke-dasharray="3,2"/>
  <line x1="10" y1="30" x2="38" y2="30" stroke="white" stroke-width="1.5" stroke-dasharray="3,2"/>
  <circle cx="18" cy="15" r="2" fill="white"/>
  <circle cx="30" cy="15" r="2" fill="white"/>
  <circle cx="18" cy="25" r="2" fill="white"/>
  <circle cx="30" cy="25" r="2" fill="white" opacity="0.7"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS SECURITY ICONS
    # -------------------------------------------------------------------------
    "aws:cognito": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cognito-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cognito-grad)"/>
  <circle cx="24" cy="18" r="6" fill="white"/>
  <path d="M14 38 C14 30 18 26 24 26 C30 26 34 30 34 38" fill="white"/>
</svg>""",
    "aws:iam": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="iam-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#iam-grad)"/>
  <path d="M24 10L36 16V28C36 34 30 38 24 40C18 38 12 34 12 28V16L24 10Z" fill="white"/>
  <path d="M24 14L32 18V28C32 32 28 35 24 36C20 35 16 32 16 28V18L24 14Z" fill="#DD344C"/>
  <path d="M20 26L23 29L30 22" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
</svg>""",
    "aws:secrets-manager": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sm-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sm-grad)"/>
  <rect x="14" y="20" width="20" height="18" rx="2" fill="white"/>
  <circle cx="24" cy="16" r="6" fill="none" stroke="white" stroke-width="3"/>
  <circle cx="24" cy="28" r="3" fill="#DD344C"/>
  <line x1="24" y1="31" x2="24" y2="35" stroke="#DD344C" stroke-width="2"/>
</svg>""",
    "aws:kms": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="kms-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#kms-grad)"/>
  <circle cx="20" cy="24" r="8" fill="white"/>
  <rect x="26" y="22" width="12" height="4" fill="white"/>
  <rect x="32" y="18" width="4" height="4" fill="white"/>
  <rect x="36" y="22" width="4" height="4" fill="white"/>
  <circle cx="20" cy="24" r="3" fill="#DD344C"/>
</svg>""",
    "aws:waf": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="waf-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#waf-grad)"/>
  <rect x="10" y="12" width="28" height="24" rx="2" fill="white"/>
  <rect x="14" y="16" width="20" height="3" fill="#DD344C"/>
  <rect x="14" y="22" width="20" height="3" fill="#DD344C" opacity="0.7"/>
  <rect x="14" y="28" width="12" height="3" fill="#DD344C" opacity="0.5"/>
  <circle cx="32" cy="29" r="4" fill="#10B981"/>
  <path d="M30 29L31.5 30.5L34 28" fill="none" stroke="white" stroke-width="1.5"/>
</svg>""",
    "aws:guardduty": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="gd-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#DD344C"/>
      <stop offset="100%" style="stop-color:#B32A3E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#gd-grad)"/>
  <circle cx="24" cy="24" r="12" fill="white"/>
  <circle cx="24" cy="24" r="8" fill="none" stroke="#DD344C" stroke-width="2"/>
  <circle cx="24" cy="24" r="4" fill="#DD344C"/>
  <line x1="24" y1="8" x2="24" y2="14" stroke="white" stroke-width="2"/>
  <line x1="24" y1="34" x2="24" y2="40" stroke="white" stroke-width="2"/>
  <line x1="8" y1="24" x2="14" y2="24" stroke="white" stroke-width="2"/>
  <line x1="34" y1="24" x2="40" y2="24" stroke="white" stroke-width="2"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS MANAGEMENT ICONS
    # -------------------------------------------------------------------------
    "aws:cloudwatch": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cw-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cw-grad)"/>
  <circle cx="24" cy="24" r="12" fill="white"/>
  <line x1="24" y1="24" x2="24" y2="16" stroke="#FF4F8B" stroke-width="2" stroke-linecap="round"/>
  <line x1="24" y1="24" x2="30" y2="28" stroke="#FF4F8B" stroke-width="2" stroke-linecap="round"/>
  <circle cx="24" cy="24" r="2" fill="#FF4F8B"/>
</svg>""",
    "aws:cloudformation": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cfn-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cfn-grad)"/>
  <rect x="18" y="10" width="12" height="8" rx="1" fill="white"/>
  <rect x="10" y="20" width="12" height="8" rx="1" fill="white"/>
  <rect x="26" y="20" width="12" height="8" rx="1" fill="white"/>
  <rect x="18" y="30" width="12" height="8" rx="1" fill="white"/>
  <line x1="24" y1="18" x2="16" y2="20" stroke="white" stroke-width="1.5"/>
  <line x1="24" y1="18" x2="32" y2="20" stroke="white" stroke-width="1.5"/>
  <line x1="16" y1="28" x2="24" y2="30" stroke="white" stroke-width="1.5"/>
  <line x1="32" y1="28" x2="24" y2="30" stroke="white" stroke-width="1.5"/>
</svg>""",
    "aws:ssm": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ssm-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ssm-grad)"/>
  <rect x="12" y="12" width="24" height="24" rx="2" fill="white"/>
  <rect x="16" y="16" width="16" height="3" fill="#FF4F8B"/>
  <rect x="16" y="22" width="12" height="2" fill="#FF4F8B" opacity="0.6"/>
  <rect x="16" y="27" width="14" height="2" fill="#FF4F8B" opacity="0.6"/>
  <rect x="16" y="32" width="8" height="2" fill="#FF4F8B" opacity="0.6"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS ML ICONS
    # -------------------------------------------------------------------------
    "aws:bedrock": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="bedrock-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#01A88D"/>
      <stop offset="100%" style="stop-color:#018571"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#bedrock-grad)"/>
  <circle cx="24" cy="16" r="4" fill="white"/>
  <circle cx="14" cy="28" r="4" fill="white"/>
  <circle cx="34" cy="28" r="4" fill="white"/>
  <circle cx="24" cy="36" r="4" fill="white"/>
  <line x1="24" y1="20" x2="16" y2="25" stroke="white" stroke-width="2"/>
  <line x1="24" y1="20" x2="32" y2="25" stroke="white" stroke-width="2"/>
  <line x1="14" y1="32" x2="21" y2="34" stroke="white" stroke-width="2"/>
  <line x1="34" y1="32" x2="27" y2="34" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:sagemaker": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sm2-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#01A88D"/>
      <stop offset="100%" style="stop-color:#018571"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sm2-grad)"/>
  <rect x="10" y="20" width="28" height="16" rx="2" fill="white"/>
  <path d="M14 32L20 24L26 28L34 22" fill="none" stroke="#01A88D" stroke-width="2" stroke-linecap="round"/>
  <rect x="16" y="10" width="16" height="8" rx="1" fill="white"/>
  <circle cx="24" cy="14" r="2" fill="#01A88D"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS INTEGRATION ICONS
    # -------------------------------------------------------------------------
    "aws:sqs": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sqs-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sqs-grad)"/>
  <rect x="10" y="16" width="28" height="16" rx="2" fill="white"/>
  <rect x="14" y="20" width="6" height="8" rx="1" fill="#FF4F8B"/>
  <rect x="22" y="20" width="6" height="8" rx="1" fill="#FF4F8B" opacity="0.7"/>
  <rect x="30" y="20" width="6" height="8" rx="1" fill="#FF4F8B" opacity="0.4"/>
</svg>""",
    "aws:sns": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sns-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sns-grad)"/>
  <circle cx="24" cy="24" r="8" fill="white"/>
  <circle cx="24" cy="24" r="4" fill="#FF4F8B"/>
  <line x1="24" y1="8" x2="24" y2="14" stroke="white" stroke-width="2"/>
  <line x1="24" y1="34" x2="24" y2="40" stroke="white" stroke-width="2"/>
  <line x1="8" y1="24" x2="14" y2="24" stroke="white" stroke-width="2"/>
  <line x1="34" y1="24" x2="40" y2="24" stroke="white" stroke-width="2"/>
  <line x1="12" y1="12" x2="17" y2="17" stroke="white" stroke-width="2"/>
  <line x1="31" y1="31" x2="36" y2="36" stroke="white" stroke-width="2"/>
  <line x1="12" y1="36" x2="17" y2="31" stroke="white" stroke-width="2"/>
  <line x1="31" y1="17" x2="36" y2="12" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:eventbridge": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="eb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#eb-grad)"/>
  <rect x="18" y="10" width="12" height="28" rx="2" fill="white"/>
  <line x1="8" y1="18" x2="18" y2="18" stroke="white" stroke-width="2"/>
  <line x1="8" y1="24" x2="18" y2="24" stroke="white" stroke-width="2"/>
  <line x1="8" y1="30" x2="18" y2="30" stroke="white" stroke-width="2"/>
  <line x1="30" y1="18" x2="40" y2="18" stroke="white" stroke-width="2"/>
  <line x1="30" y1="24" x2="40" y2="24" stroke="white" stroke-width="2"/>
  <line x1="30" y1="30" x2="40" y2="30" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:step-functions": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="sfn-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#sfn-grad)"/>
  <rect x="18" y="8" width="12" height="8" rx="2" fill="white"/>
  <rect x="10" y="20" width="12" height="8" rx="2" fill="white"/>
  <rect x="26" y="20" width="12" height="8" rx="2" fill="white"/>
  <rect x="18" y="32" width="12" height="8" rx="2" fill="white"/>
  <line x1="24" y1="16" x2="16" y2="20" stroke="white" stroke-width="2"/>
  <line x1="24" y1="16" x2="32" y2="20" stroke="white" stroke-width="2"/>
  <line x1="16" y1="28" x2="24" y2="32" stroke="white" stroke-width="2"/>
  <line x1="32" y1="28" x2="24" y2="32" stroke="white" stroke-width="2"/>
</svg>""",
    "aws:kinesis": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="kinesis-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF4F8B"/>
      <stop offset="100%" style="stop-color:#CC3F6F"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#kinesis-grad)"/>
  <path d="M10 16 Q24 10 38 16" fill="none" stroke="white" stroke-width="3"/>
  <path d="M10 24 Q24 18 38 24" fill="none" stroke="white" stroke-width="3"/>
  <path d="M10 32 Q24 26 38 32" fill="none" stroke="white" stroke-width="3"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AWS DEVTOOLS ICONS
    # -------------------------------------------------------------------------
    "aws:codebuild": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cb-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B82F6"/>
      <stop offset="100%" style="stop-color:#2563EB"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cb-grad)"/>
  <rect x="12" y="12" width="24" height="24" rx="2" fill="white"/>
  <polygon points="20,18 20,30 30,24" fill="#3B82F6"/>
</svg>""",
    "aws:codepipeline": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="cp-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#3B82F6"/>
      <stop offset="100%" style="stop-color:#2563EB"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#cp-grad)"/>
  <circle cx="12" cy="24" r="5" fill="white"/>
  <circle cx="24" cy="24" r="5" fill="white"/>
  <circle cx="36" cy="24" r="5" fill="white"/>
  <line x1="17" y1="24" x2="19" y2="24" stroke="white" stroke-width="2"/>
  <line x1="29" y1="24" x2="31" y2="24" stroke="white" stroke-width="2"/>
  <polygon points="19,22 19,26 21,24" fill="white"/>
  <polygon points="31,22 31,26 33,24" fill="white"/>
</svg>""",
    "aws:ecr": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ecr-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#FF9900"/>
      <stop offset="100%" style="stop-color:#D86613"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ecr-grad)"/>
  <rect x="10" y="14" width="28" height="20" rx="2" fill="white"/>
  <rect x="14" y="18" width="8" height="12" rx="1" fill="#FF9900"/>
  <rect x="26" y="18" width="8" height="12" rx="1" fill="#FF9900" opacity="0.6"/>
  <circle cx="18" cy="24" r="2" fill="white"/>
  <circle cx="30" cy="24" r="2" fill="white"/>
</svg>""",
    # -------------------------------------------------------------------------
    # GENERIC ICONS
    # -------------------------------------------------------------------------
    "generic:user": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="user-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B7280"/>
      <stop offset="100%" style="stop-color:#4B5563"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#user-grad)"/>
  <circle cx="24" cy="18" r="8" fill="white"/>
  <path d="M10 42 C10 32 16 26 24 26 C32 26 38 32 38 42" fill="white"/>
</svg>""",
    "generic:browser": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="browser-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B7280"/>
      <stop offset="100%" style="stop-color:#4B5563"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#browser-grad)"/>
  <rect x="8" y="10" width="32" height="28" rx="2" fill="white"/>
  <rect x="8" y="10" width="32" height="8" fill="#E5E7EB"/>
  <circle cx="14" cy="14" r="2" fill="#EF4444"/>
  <circle cx="20" cy="14" r="2" fill="#F59E0B"/>
  <circle cx="26" cy="14" r="2" fill="#10B981"/>
</svg>""",
    "generic:database": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="db-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B7280"/>
      <stop offset="100%" style="stop-color:#4B5563"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#db-grad)"/>
  <ellipse cx="24" cy="14" rx="14" ry="5" fill="white"/>
  <path d="M10 14v20c0 2.8 6.3 5 14 5s14-2.2 14-5V14" fill="none" stroke="white" stroke-width="2"/>
  <ellipse cx="24" cy="24" rx="14" ry="5" fill="none" stroke="white" stroke-width="1.5"/>
</svg>""",
    "generic:server": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="server-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B7280"/>
      <stop offset="100%" style="stop-color:#4B5563"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#server-grad)"/>
  <rect x="10" y="10" width="28" height="10" rx="2" fill="white"/>
  <rect x="10" y="22" width="28" height="10" rx="2" fill="white"/>
  <rect x="10" y="34" width="28" height="6" rx="2" fill="white" opacity="0.7"/>
  <circle cx="32" cy="15" r="2" fill="#10B981"/>
  <circle cx="32" cy="27" r="2" fill="#10B981"/>
</svg>""",
    "generic:api": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="api-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#6B7280"/>
      <stop offset="100%" style="stop-color:#4B5563"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#api-grad)"/>
  <text x="24" y="30" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" font-weight="bold" fill="white">API</text>
  <path d="M12 16L24 10L36 16" fill="none" stroke="white" stroke-width="2"/>
  <path d="M12 34L24 40L36 34" fill="none" stroke="white" stroke-width="2"/>
</svg>""",
    # -------------------------------------------------------------------------
    # KUBERNETES ICONS
    # -------------------------------------------------------------------------
    "k8s:pod": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="pod-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#326CE5"/>
      <stop offset="100%" style="stop-color:#2756B8"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#pod-grad)"/>
  <polygon points="24,10 38,20 38,32 24,42 10,32 10,20" fill="white"/>
  <polygon points="24,14 34,22 34,30 24,38 14,30 14,22" fill="#326CE5"/>
</svg>""",
    "k8s:deployment": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="deploy-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#326CE5"/>
      <stop offset="100%" style="stop-color:#2756B8"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#deploy-grad)"/>
  <polygon points="24,8 36,16 36,26 24,34 12,26 12,16" fill="white"/>
  <polygon points="24,18 38,28 38,38 24,48 10,38 10,28" fill="white" opacity="0.5" transform="translate(0,-4)"/>
</svg>""",
    "k8s:service": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="svc-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#326CE5"/>
      <stop offset="100%" style="stop-color:#2756B8"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#svc-grad)"/>
  <circle cx="24" cy="24" r="14" fill="white"/>
  <circle cx="24" cy="24" r="10" fill="none" stroke="#326CE5" stroke-width="2"/>
  <circle cx="24" cy="24" r="5" fill="#326CE5"/>
</svg>""",
    "k8s:ingress": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="ing-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#326CE5"/>
      <stop offset="100%" style="stop-color:#2756B8"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#ing-grad)"/>
  <rect x="8" y="18" width="12" height="12" rx="2" fill="white"/>
  <rect x="28" y="10" width="12" height="8" rx="1" fill="white"/>
  <rect x="28" y="20" width="12" height="8" rx="1" fill="white"/>
  <rect x="28" y="30" width="12" height="8" rx="1" fill="white"/>
  <line x1="20" y1="24" x2="28" y2="14" stroke="white" stroke-width="2"/>
  <line x1="20" y1="24" x2="28" y2="24" stroke="white" stroke-width="2"/>
  <line x1="20" y1="24" x2="28" y2="34" stroke="white" stroke-width="2"/>
</svg>""",
    # -------------------------------------------------------------------------
    # AZURE ICONS
    # -------------------------------------------------------------------------
    "azure:vm": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="avm-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#0078D4"/>
      <stop offset="100%" style="stop-color:#005A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#avm-grad)"/>
  <rect x="10" y="12" width="28" height="20" rx="2" fill="white"/>
  <rect x="18" y="32" width="12" height="6" fill="white"/>
  <rect x="14" y="38" width="20" height="2" rx="1" fill="white"/>
</svg>""",
    "azure:functions": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="afn-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#0078D4"/>
      <stop offset="100%" style="stop-color:#005A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#afn-grad)"/>
  <path d="M14 36L22 24L14 12H22L28 20L22 28H28L20 36L28 24L20 12" fill="none" stroke="white" stroke-width="2.5"/>
</svg>""",
    "azure:aks": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="aaks-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#0078D4"/>
      <stop offset="100%" style="stop-color:#005A9E"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#aaks-grad)"/>
  <polygon points="24,10 38,20 38,32 24,42 10,32 10,20" fill="white"/>
  <polygon points="24,14 34,22 34,30 24,38 14,30 14,22" fill="#326CE5"/>
</svg>""",
    # -------------------------------------------------------------------------
    # GCP ICONS
    # -------------------------------------------------------------------------
    "gcp:compute-engine": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="gce-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4285F4"/>
      <stop offset="100%" style="stop-color:#3367D6"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#gce-grad)"/>
  <rect x="10" y="14" width="28" height="20" rx="2" fill="white"/>
  <rect x="14" y="18" width="8" height="12" fill="#4285F4"/>
  <rect x="26" y="18" width="8" height="12" fill="#4285F4" opacity="0.6"/>
</svg>""",
    "gcp:cloud-functions": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="gcf-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4285F4"/>
      <stop offset="100%" style="stop-color:#3367D6"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#gcf-grad)"/>
  <path d="M14 36L20 24L14 12H20L28 24L20 36H14Z" fill="white"/>
  <path d="M24 36L30 24L24 12H30L38 24L30 36H24Z" fill="white" opacity="0.7"/>
</svg>""",
    "gcp:gke": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="gke-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4285F4"/>
      <stop offset="100%" style="stop-color:#3367D6"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#gke-grad)"/>
  <polygon points="24,10 38,20 38,32 24,42 10,32 10,20" fill="white"/>
  <polygon points="24,14 34,22 34,30 24,38 14,30 14,22" fill="#326CE5"/>
</svg>""",
    "gcp:cloud-storage": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="gcs-grad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4285F4"/>
      <stop offset="100%" style="stop-color:#3367D6"/>
    </linearGradient>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#gcs-grad)"/>
  <path d="M10 30L24 36L38 30V18L24 12L10 18V30Z" fill="white"/>
  <path d="M24 24L38 18M24 24L10 18M24 24V36" stroke="#4285F4" stroke-width="1.5"/>
</svg>""",
}


class IconLibrary:
    """
    Cloud provider icon library for diagram generation.

    Supports:
    - AWS Architecture Icons (official)
    - Azure Architecture Icons (official)
    - GCP Icons (official)
    - Kubernetes Icons
    - Generic technology icons
    - Multiple color modes (native, Aura semantic, monochrome)

    Usage:
        library = IconLibrary(color_mode=IconColorMode.AURA_SEMANTIC)
        icon = library.get_icon("aws:lambda")
        svg = library.get_svg_content(icon)
    """

    def __init__(
        self,
        icons_base_path: str = "static/icons",
        color_mode: IconColorMode = IconColorMode.NATIVE,
    ):
        self.base_path = Path(icons_base_path)
        self.color_mode = color_mode
        self._icons: dict[str, DiagramIcon] = {}
        self._alias_map: dict[str, str] = {}

        # Load all icon sets
        self._icons.update(AWS_ICONS)
        self._icons.update(AZURE_ICONS)
        self._icons.update(GCP_ICONS)
        self._icons.update(KUBERNETES_ICONS)
        self._icons.update(GENERIC_ICONS)

        # Build alias map for fuzzy matching
        for icon_id, icon in self._icons.items():
            for alias in icon.aliases:
                alias_key = alias.lower().replace(" ", "-").replace("_", "-")
                self._alias_map[alias_key] = icon_id

    def get_icon(self, identifier: str) -> Optional[DiagramIcon]:
        """
        Get icon by ID or alias.

        Examples:
            get_icon("aws:ec2") -> EC2 icon
            get_icon("lambda") -> AWS Lambda icon (via alias)
            get_icon("kubernetes") -> EKS icon (via alias)

        Args:
            identifier: Icon ID or alias name

        Returns:
            DiagramIcon if found, None otherwise
        """
        # Try direct ID match
        if identifier in self._icons:
            return self._icons[identifier]

        # Try alias match
        alias_key = identifier.lower().replace(" ", "-").replace("_", "-")
        if alias_key in self._alias_map:
            return self._icons[self._alias_map[alias_key]]

        # Try partial match with provider prefix
        for provider in ["aws", "azure", "gcp", "k8s"]:
            prefixed_key = f"{provider}:{alias_key}"
            if prefixed_key in self._icons:
                return self._icons[prefixed_key]

        return None

    def get_icon_color(self, icon: DiagramIcon) -> str:
        """Get icon color based on current color mode."""
        return icon.get_color(self.color_mode)

    def get_svg_content(self, icon: DiagramIcon, apply_color: bool = True) -> str:
        """
        Load SVG content for an icon, optionally applying color mode.

        Tries sources in order:
        1. Embedded professional SVG icons (EMBEDDED_ICONS dict)
        2. External SVG file (if exists at svg_path)
        3. Generated professional placeholder

        Args:
            icon: The icon to render
            apply_color: Whether to apply the current color mode

        Returns:
            SVG content string
        """
        # First try embedded icons (highest quality)
        if icon.id in EMBEDDED_ICONS:
            content = EMBEDDED_ICONS[icon.id]
            if apply_color and self.color_mode != IconColorMode.NATIVE:
                content = self._apply_color_mode(content, icon)
            return content

        # Then try file-based icons
        svg_path = self.base_path / icon.svg_path
        if svg_path.exists():
            content = svg_path.read_text()
            if apply_color and self.color_mode != IconColorMode.NATIVE:
                content = self._apply_color_mode(content, icon)
            return content

        # Return professional placeholder SVG for missing icons
        return self._generate_placeholder_svg(icon)

    def _apply_color_mode(self, svg_content: str, icon: DiagramIcon) -> str:
        """Apply color mode to SVG content."""
        color = icon.get_color(self.color_mode)
        # Replace fill attributes (simplified - production would use proper SVG parsing)
        svg_content = re.sub(r'fill="[^"]*"', f'fill="{color}"', svg_content)
        return svg_content

    def _generate_placeholder_svg(self, icon: DiagramIcon) -> str:
        """
        Generate professional placeholder SVG for icons without embedded definitions.

        Creates a visually appealing icon with:
        - Gradient background matching the icon's category color
        - Rounded corners and subtle shadow effect
        - Service abbreviation in a clean font
        - Professional styling consistent with embedded icons
        """
        color = icon.get_color(self.color_mode)
        # Create darker shade for gradient
        darker_color = self._darken_color(color, 0.2)
        # Abbreviate name for display (max 4 chars)
        abbrev = icon.name[:4].upper()
        # Generate unique gradient ID to avoid conflicts
        grad_id = f"placeholder-{icon.name.replace('-', '')}-grad"

        return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{icon.width}" height="{icon.height}" viewBox="0 0 48 48">
  <defs>
    <linearGradient id="{grad_id}" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:{color}"/>
      <stop offset="100%" style="stop-color:{darker_color}"/>
    </linearGradient>
    <filter id="placeholder-shadow" x="-10%" y="-10%" width="120%" height="130%">
      <feDropShadow dx="0" dy="1" stdDeviation="1" flood-opacity="0.2"/>
    </filter>
  </defs>
  <rect x="4" y="4" width="40" height="40" rx="4" fill="url(#{grad_id})" filter="url(#placeholder-shadow)"/>
  <rect x="10" y="14" width="28" height="20" rx="3" fill="white" opacity="0.95"/>
  <text x="24" y="28" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="10" font-weight="700" fill="{color}">{abbrev}</text>
</svg>"""

    def _darken_color(self, hex_color: str, factor: float = 0.2) -> str:
        """
        Darken a hex color by the specified factor.

        Args:
            hex_color: Color in #RRGGBB format
            factor: Amount to darken (0.0-1.0)

        Returns:
            Darkened color in #RRGGBB format
        """
        # Remove # prefix
        hex_color = hex_color.lstrip("#")

        # Parse RGB components
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)

            # Darken each component
            r = max(0, int(r * (1 - factor)))
            g = max(0, int(g * (1 - factor)))
            b = max(0, int(b * (1 - factor)))

            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            # Return original color if parsing fails
            return f"#{hex_color}"

    def list_icons(self) -> list[DiagramIcon]:
        """List all available icons."""
        return list(self._icons.values())

    def list_icons_by_provider(self, provider: CloudProvider) -> list[DiagramIcon]:
        """List all icons for a specific provider."""
        return [i for i in self._icons.values() if i.provider == provider]

    def list_icons_by_category(self, category: IconCategory) -> list[DiagramIcon]:
        """List all icons in a specific category."""
        return [i for i in self._icons.values() if i.category == category]

    def search_icons(self, query: str) -> list[DiagramIcon]:
        """
        Search icons by name, display name, or alias.

        Args:
            query: Search query string

        Returns:
            List of matching icons sorted by relevance
        """
        query_lower = query.lower()
        results = []

        for icon in self._icons.values():
            score = 0
            # Exact name match
            if icon.name.lower() == query_lower:
                score = 100
            # Display name contains query
            elif query_lower in icon.display_name.lower():
                score = 80
            # Alias match
            elif any(query_lower in alias.lower() for alias in icon.aliases):
                score = 60
            # ID contains query
            elif query_lower in icon.id.lower():
                score = 40

            if score > 0:
                results.append((score, icon))

        # Sort by score descending
        results.sort(key=lambda x: x[0], reverse=True)
        return [icon for _, icon in results]

    def set_color_mode(self, mode: IconColorMode) -> None:
        """Change the current color mode."""
        self.color_mode = mode

    def get_icon_count(self) -> dict[str, int]:
        """Get count of icons by provider."""
        counts = {provider.value: 0 for provider in CloudProvider}
        for icon in self._icons.values():
            counts[icon.provider.value] += 1
        return counts
