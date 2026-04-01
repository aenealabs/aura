"""
External Tool Connectors Registry.

This module provides a centralized registry of all external tool connectors
available in Project Aura. Each connector integrates with a third-party
service for security, DevOps, or ITSM capabilities.

Architecture Notes:
    - Connectors are intentionally kept as independent modules (~1000 lines each)
    - Each connector handles its own authentication, data models, and error handling
    - This isolation allows independent updates without cross-connector regression
    - All connectors inherit from ExternalToolConnector base class

Available Connectors:
    Security & Vulnerability:
        - CrowdStrikeConnector: Endpoint detection and response (EDR)
        - QualysConnector: Vulnerability management and scanning
        - SnykConnector: Developer security and dependency scanning
        - SplunkConnector: SIEM and security analytics
        - ZscalerConnector: Zero Trust cloud security (ZIA, ZPA) - ADR-053

    Identity & GRC (ADR-053):
        - SaviyntConnector: Enterprise Identity Cloud governance and PAM
        - AuditBoardConnector: GRC platform for controls, risks, and compliance

    DevOps & Infrastructure:
        - AzureDevOpsConnector: Azure DevOps work items and pipelines
        - TerraformCloudConnector: Infrastructure as Code management

    ITSM & Ticketing:
        - ServiceNowConnector: Enterprise ITSM (incidents, changes, CMDB)
        - JiraConnector: Issue tracking and project management
        - SlackConnector: Team messaging and notifications
        - PagerDutyConnector: Incident management and alerting

Usage Examples:

    # Import specific connector
    from src.services.azure_devops_connector import AzureDevOpsConnector

    # Initialize with credentials
    connector = AzureDevOpsConnector(
        organization="my-org",
        project="my-project",
        pat_token="my-pat-token"
    )

    # Test connection
    if await connector.test_connection():
        results = await connector.search_work_items("security bug")

    # Using the factory pattern
    from src.services.external_tool_connectors import ExternalToolConnectorFactory

    factory = ExternalToolConnectorFactory()
    connector = factory.create_connector("azure_devops", config)

Connector Development:
    See docs/guides/CONNECTOR_DEVELOPMENT.md for patterns and best practices
    when adding new connectors.

Related Modules:
    - src/services/external_tool_connectors.py: Base class and factory
    - src/services/ticketing/: Ticketing-specific abstraction layer (ADR-046)
"""

from typing import Dict, List, Type

# Registry of available connectors with metadata
CONNECTOR_REGISTRY: Dict[str, Dict] = {
    # Security & Vulnerability Connectors
    "crowdstrike": {
        "module": "src.services.crowdstrike_connector",
        "class": "CrowdStrikeConnector",
        "category": "security",
        "description": "CrowdStrike Falcon endpoint detection and response",
        "auth_methods": ["api_key"],
        "data_models": ["CrowdStrikeHost", "CrowdStrikeDetection", "CrowdStrikeIOC"],
    },
    "qualys": {
        "module": "src.services.qualys_connector",
        "class": "QualysConnector",
        "category": "security",
        "description": "Qualys vulnerability management and compliance scanning",
        "auth_methods": ["basic_auth"],
        "data_models": ["QualysVulnerability", "QualysHost", "QualysDetection"],
    },
    "snyk": {
        "module": "src.services.snyk_connector",
        "class": "SnykConnector",
        "category": "security",
        "description": "Snyk developer security and dependency scanning",
        "auth_methods": ["api_token"],
        "data_models": ["SnykVulnerability", "SnykProject", "SnykIssue"],
    },
    "splunk": {
        "module": "src.services.splunk_connector",
        "class": "SplunkConnector",
        "category": "security",
        "description": "Splunk SIEM and security event analytics",
        "auth_methods": ["basic_auth", "token"],
        "data_models": ["SplunkEvent", "SplunkSearchJob", "SplunkAlert"],
    },
    "zscaler": {
        "module": "src.services.zscaler_connector",
        "class": "ZscalerConnector",
        "category": "security",
        "subcategory": "zero_trust",
        "description": "Zscaler Zero Trust cloud security platform (ZIA, ZPA)",
        "auth_methods": ["api_key", "oauth2"],
        "govcloud_compatible": True,
        "govcloud_cloud": "zscalergov.net",
        "data_models": [
            "ZscalerThreatEvent",
            "ZscalerDLPIncident",
            "ZscalerURLFilteringRule",
            "ZscalerUserRisk",
            "ZscalerZPAApplication",
        ],
    },
    # Identity & GRC Connectors (ADR-053)
    "saviynt": {
        "module": "src.services.saviynt_connector",
        "class": "SaviyntConnector",
        "category": "identity",
        "subcategory": "identity_governance",
        "description": "Saviynt Enterprise Identity Cloud governance and PAM",
        "auth_methods": ["bearer_token"],
        "govcloud_compatible": True,
        "data_models": [
            "SaviyntUser",
            "SaviyntEntitlement",
            "SaviyntAccessRequest",
            "SaviyntCertification",
            "SaviyntPAMSession",
            "SaviyntRiskScore",
        ],
    },
    "auditboard": {
        "module": "src.services.auditboard_connector",
        "class": "AuditBoardConnector",
        "category": "grc",
        "subcategory": "compliance",
        "description": "AuditBoard GRC platform for controls, risks, and compliance",
        "auth_methods": ["hmac_signature"],
        "govcloud_compatible": True,
        "data_models": [
            "AuditBoardControl",
            "AuditBoardRisk",
            "AuditBoardFinding",
            "AuditBoardEvidence",
            "AuditBoardComplianceStatus",
        ],
    },
    # DevOps & Infrastructure Connectors
    "azure_devops": {
        "module": "src.services.azure_devops_connector",
        "class": "AzureDevOpsConnector",
        "category": "devops",
        "description": "Azure DevOps work items, pipelines, and repositories",
        "auth_methods": ["pat_token"],
        "data_models": ["WorkItem", "PipelineRun"],
    },
    "terraform_cloud": {
        "module": "src.services.terraform_cloud_connector",
        "class": "TerraformCloudConnector",
        "category": "devops",
        "description": "Terraform Cloud/Enterprise workspace and run management",
        "auth_methods": ["api_token"],
        "data_models": ["TerraformWorkspace", "TerraformRun", "TerraformVariable"],
    },
    # ITSM & Ticketing Connectors
    "servicenow": {
        "module": "src.services.servicenow_connector",
        "class": "ServiceNowConnector",
        "category": "itsm",
        "description": "ServiceNow ITSM incidents, changes, and CMDB",
        "auth_methods": ["basic_auth", "oauth"],
        "data_models": [
            "ServiceNowIncident",
            "ServiceNowChangeRequest",
            "CMDBConfigurationItem",
        ],
    },
    "jira": {
        "module": "src.services.external_tool_connectors",
        "class": "JiraConnector",
        "category": "itsm",
        "description": "Jira issue tracking and project management",
        "auth_methods": ["basic_auth", "api_token"],
        "data_models": ["JiraIssue"],
    },
    "slack": {
        "module": "src.services.external_tool_connectors",
        "class": "SlackConnector",
        "category": "notifications",
        "description": "Slack team messaging and notifications",
        "auth_methods": ["bot_token", "webhook"],
        "data_models": ["SlackMessage", "SlackAttachment"],
    },
    "pagerduty": {
        "module": "src.services.external_tool_connectors",
        "class": "PagerDutyConnector",
        "category": "notifications",
        "description": "PagerDuty incident management and alerting",
        "auth_methods": ["api_key"],
        "data_models": ["PagerDutyEvent"],
    },
}


def list_connectors(category: str | None = None) -> List[str]:
    """
    List available connector names.

    Args:
        category: Optional filter by category (security, devops, itsm, notifications)

    Returns:
        List of connector names
    """
    if category:
        return [
            name
            for name, info in CONNECTOR_REGISTRY.items()
            if info["category"] == category
        ]
    return list(CONNECTOR_REGISTRY.keys())


def get_connector_info(name: str) -> Dict | None:
    """
    Get metadata about a specific connector.

    Args:
        name: Connector name (e.g., "splunk", "azure_devops")

    Returns:
        Connector metadata dict or None if not found
    """
    return CONNECTOR_REGISTRY.get(name)


def get_connector_class(name: str) -> Type | None:
    """
    Dynamically import and return a connector class.

    Args:
        name: Connector name (e.g., "splunk", "azure_devops")

    Returns:
        Connector class or None if not found

    Example:
        ConnectorClass = get_connector_class("splunk")
        if ConnectorClass:
            connector = ConnectorClass(host="...", token="...")
    """
    info = CONNECTOR_REGISTRY.get(name)
    if not info:
        return None

    import importlib

    try:
        module = importlib.import_module(info["module"])
        return getattr(module, info["class"])
    except (ImportError, AttributeError):
        return None


# Expose commonly used items at package level
__all__ = [
    "CONNECTOR_REGISTRY",
    "list_connectors",
    "get_connector_info",
    "get_connector_class",
]
