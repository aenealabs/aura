"""Baseline management for Environment Validator (ADR-062 Phase 2).

Stores and retrieves validated configuration baselines using DynamoDB
single-table design per the architecture recommendation.
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Baseline:
    """Represents a validated configuration baseline."""

    environment: str
    resource_type: str
    resource_name: str
    namespace: str
    content: dict
    content_hash: str
    validated_at: datetime
    validation_run_id: str
    created_by: str  # User or system that created the baseline

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"ENV#{self.environment}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"BASELINE#{self.resource_type}#{self.namespace}#{self.resource_name}"

    def to_item(self) -> dict:
        """Convert to DynamoDB item."""
        return {
            "PK": {"S": self.pk},
            "SK": {"S": self.sk},
            "environment": {"S": self.environment},
            "resource_type": {"S": self.resource_type},
            "resource_name": {"S": self.resource_name},
            "namespace": {"S": self.namespace},
            "content": {"S": json.dumps(self.content)},
            "content_hash": {"S": self.content_hash},
            "validated_at": {"S": self.validated_at.isoformat()},
            "validation_run_id": {"S": self.validation_run_id},
            "created_by": {"S": self.created_by},
            "gsi1pk": {"S": f"TYPE#{self.resource_type}"},
            "gsi1sk": {
                "S": f"ENV#{self.environment}#{self.namespace}#{self.resource_name}"
            },
        }

    @classmethod
    def from_item(cls, item: dict) -> "Baseline":
        """Create from DynamoDB item."""
        return cls(
            environment=item["environment"]["S"],
            resource_type=item["resource_type"]["S"],
            resource_name=item["resource_name"]["S"],
            namespace=item["namespace"]["S"],
            content=json.loads(item["content"]["S"]),
            content_hash=item["content_hash"]["S"],
            validated_at=datetime.fromisoformat(item["validated_at"]["S"]),
            validation_run_id=item["validation_run_id"]["S"],
            created_by=item["created_by"]["S"],
        )


@dataclass
class DriftHistory:
    """Represents a historical drift detection event."""

    environment: str
    event_id: str
    detected_at: datetime
    resource_type: str
    resource_name: str
    namespace: str
    field_path: str
    baseline_value: str
    current_value: str
    severity: str
    resolved: bool
    resolved_at: Optional[datetime]

    @property
    def pk(self) -> str:
        """DynamoDB partition key."""
        return f"ENV#{self.environment}"

    @property
    def sk(self) -> str:
        """DynamoDB sort key."""
        return f"DRIFT#{self.detected_at.isoformat()}#{self.event_id}"

    def to_item(self) -> dict:
        """Convert to DynamoDB item."""
        item = {
            "PK": {"S": self.pk},
            "SK": {"S": self.sk},
            "environment": {"S": self.environment},
            "event_id": {"S": self.event_id},
            "detected_at": {"S": self.detected_at.isoformat()},
            "resource_type": {"S": self.resource_type},
            "resource_name": {"S": self.resource_name},
            "namespace": {"S": self.namespace},
            "field_path": {"S": self.field_path},
            "baseline_value": {"S": self.baseline_value},
            "current_value": {"S": self.current_value},
            "severity": {"S": self.severity},
            "resolved": {"BOOL": self.resolved},
            "gsi1pk": {"S": f"SEVERITY#{self.severity}"},
            "gsi1sk": {"S": f"ENV#{self.environment}#{self.detected_at.isoformat()}"},
        }
        if self.resolved_at:
            item["resolved_at"] = {"S": self.resolved_at.isoformat()}
        return item


class BaselineManager:
    """Manages configuration baselines in DynamoDB."""

    def __init__(self, environment: str, table_name: Optional[str] = None):
        """Initialize baseline manager.

        Args:
            environment: Target environment (dev, qa, staging, prod)
            table_name: DynamoDB table name (default from environment)
        """
        self.environment = environment
        self.table_name = table_name or os.environ.get(
            "ENV_VALIDATOR_TABLE", f"aura-env-validator-{environment}"
        )
        self._client = None
        self._use_mock = (
            os.environ.get("ENV_VALIDATOR_USE_MOCK", "false").lower() == "true"
        )
        self._mock_store: dict[str, dict] = {}

    @property
    def dynamodb_client(self):
        """Get or create DynamoDB client."""
        if self._use_mock:
            return None

        if self._client is None:
            import boto3

            self._client = boto3.client("dynamodb")
        return self._client

    def save_baseline(
        self, manifest_content: str, validation_run_id: str, created_by: str = "system"
    ) -> list[Baseline]:
        """Save validated manifest as baseline.

        Args:
            manifest_content: Validated Kubernetes manifest YAML
            validation_run_id: ID of successful validation run
            created_by: User or system creating the baseline

        Returns:
            List of saved baselines
        """
        baselines = []

        try:
            docs = list(yaml.safe_load_all(manifest_content))
            docs = [d for d in docs if d]
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse manifest for baseline: {e}")
            return []

        for doc in docs:
            if not isinstance(doc, dict):
                continue

            kind = doc.get("kind", "Unknown")
            metadata = doc.get("metadata", {})
            name = metadata.get("name", "unknown")
            namespace = metadata.get("namespace", "default")

            # Compute content hash
            content_hash = hashlib.sha256(
                json.dumps(doc, sort_keys=True).encode()
            ).hexdigest()[:16]

            baseline = Baseline(
                environment=self.environment,
                resource_type=kind,
                resource_name=name,
                namespace=namespace,
                content=doc,
                content_hash=content_hash,
                validated_at=datetime.utcnow(),
                validation_run_id=validation_run_id,
                created_by=created_by,
            )

            self._save_baseline_item(baseline)
            baselines.append(baseline)
            logger.info(f"Saved baseline for {kind}/{name} in {namespace}")

        return baselines

    def get_baseline(
        self,
        environment: str,
        resource_type: str,
        resource_name: str,
        namespace: str = "default",
    ) -> Optional[dict]:
        """Get baseline for a specific resource.

        Args:
            environment: Target environment
            resource_type: Kubernetes resource kind
            resource_name: Resource name
            namespace: Resource namespace

        Returns:
            Baseline content dict or None if not found
        """
        pk = f"ENV#{environment}"
        sk = f"BASELINE#{resource_type}#{namespace}#{resource_name}"

        if self._use_mock:
            key = f"{pk}#{sk}"
            item = self._mock_store.get(key)
            if item:
                return json.loads(item["content"]["S"])
            return None

        try:
            response = self.dynamodb_client.get_item(
                TableName=self.table_name,
                Key={"PK": {"S": pk}, "SK": {"S": sk}},
            )
            item = response.get("Item")
            if item:
                return json.loads(item["content"]["S"])
            return None
        except Exception as e:
            logger.error(f"Failed to get baseline: {e}")
            return None

    def list_baselines(
        self, environment: str, resource_type: Optional[str] = None
    ) -> list[Baseline]:
        """List all baselines for an environment.

        Args:
            environment: Target environment
            resource_type: Optional filter by resource type

        Returns:
            List of baselines
        """
        pk = f"ENV#{environment}"

        if self._use_mock:
            baselines = []
            for key, item in self._mock_store.items():
                if key.startswith(pk) and "BASELINE#" in key:
                    if (
                        resource_type is None
                        or item["resource_type"]["S"] == resource_type
                    ):
                        baselines.append(Baseline.from_item(item))
            return baselines

        try:
            response = self.dynamodb_client.query(
                TableName=self.table_name,
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                ExpressionAttributeValues={
                    ":pk": {"S": pk},
                    ":sk_prefix": {"S": "BASELINE#"},
                },
            )
            baselines = [Baseline.from_item(item) for item in response.get("Items", [])]

            if resource_type:
                baselines = [b for b in baselines if b.resource_type == resource_type]

            return baselines
        except Exception as e:
            logger.error(f"Failed to list baselines: {e}")
            return []

    def delete_baseline(
        self,
        environment: str,
        resource_type: str,
        resource_name: str,
        namespace: str = "default",
    ) -> bool:
        """Delete a baseline.

        Args:
            environment: Target environment
            resource_type: Kubernetes resource kind
            resource_name: Resource name
            namespace: Resource namespace

        Returns:
            True if deleted, False otherwise
        """
        pk = f"ENV#{environment}"
        sk = f"BASELINE#{resource_type}#{namespace}#{resource_name}"

        if self._use_mock:
            key = f"{pk}#{sk}"
            if key in self._mock_store:
                del self._mock_store[key]
                return True
            return False

        try:
            self.dynamodb_client.delete_item(
                TableName=self.table_name,
                Key={"PK": {"S": pk}, "SK": {"S": sk}},
            )
            logger.info(f"Deleted baseline for {resource_type}/{resource_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete baseline: {e}")
            return False

    def save_drift_event(self, drift_event) -> bool:
        """Save a drift detection event to history.

        Args:
            drift_event: DriftEvent from drift detector

        Returns:
            True if saved successfully
        """
        history = DriftHistory(
            environment=self.environment,
            event_id=drift_event.event_id,
            detected_at=drift_event.detected_at,
            resource_type=drift_event.resource_type,
            resource_name=drift_event.resource_name,
            namespace=drift_event.namespace,
            field_path=drift_event.field_path,
            baseline_value=drift_event.baseline_value,
            current_value=drift_event.current_value,
            severity=drift_event.severity.value,
            resolved=False,
            resolved_at=None,
        )

        item = history.to_item()

        if self._use_mock:
            key = f"{history.pk}#{history.sk}"
            self._mock_store[key] = item
            return True

        try:
            self.dynamodb_client.put_item(TableName=self.table_name, Item=item)
            logger.info(f"Saved drift event {drift_event.event_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save drift event: {e}")
            return False

    def get_unresolved_drift(
        self, environment: str, limit: int = 100
    ) -> list[DriftHistory]:
        """Get unresolved drift events for an environment.

        Args:
            environment: Target environment
            limit: Maximum number of events to return

        Returns:
            List of unresolved drift history events
        """
        pk = f"ENV#{environment}"

        if self._use_mock:
            events = []
            for key, item in self._mock_store.items():
                if key.startswith(pk) and "DRIFT#" in key:
                    if not item.get("resolved", {}).get("BOOL", False):
                        events.append(self._drift_history_from_item(item))
            return events[:limit]

        try:
            response = self.dynamodb_client.query(
                TableName=self.table_name,
                KeyConditionExpression="PK = :pk AND begins_with(SK, :sk_prefix)",
                FilterExpression="resolved = :resolved",
                ExpressionAttributeValues={
                    ":pk": {"S": pk},
                    ":sk_prefix": {"S": "DRIFT#"},
                    ":resolved": {"BOOL": False},
                },
                Limit=limit,
            )
            return [
                self._drift_history_from_item(item)
                for item in response.get("Items", [])
            ]
        except Exception as e:
            logger.error(f"Failed to get unresolved drift: {e}")
            return []

    def _save_baseline_item(self, baseline: Baseline) -> None:
        """Save baseline item to DynamoDB."""
        item = baseline.to_item()

        if self._use_mock:
            key = f"{baseline.pk}#{baseline.sk}"
            self._mock_store[key] = item
            return

        try:
            self.dynamodb_client.put_item(TableName=self.table_name, Item=item)
        except Exception as e:
            logger.error(f"Failed to save baseline: {e}")
            raise

    def _drift_history_from_item(self, item: dict) -> DriftHistory:
        """Create DriftHistory from DynamoDB item."""
        resolved_at = None
        if "resolved_at" in item:
            resolved_at = datetime.fromisoformat(item["resolved_at"]["S"])

        return DriftHistory(
            environment=item["environment"]["S"],
            event_id=item["event_id"]["S"],
            detected_at=datetime.fromisoformat(item["detected_at"]["S"]),
            resource_type=item["resource_type"]["S"],
            resource_name=item["resource_name"]["S"],
            namespace=item["namespace"]["S"],
            field_path=item["field_path"]["S"],
            baseline_value=item["baseline_value"]["S"],
            current_value=item["current_value"]["S"],
            severity=item["severity"]["S"],
            resolved=item.get("resolved", {}).get("BOOL", False),
            resolved_at=resolved_at,
        )


class MockBaselineManager(BaselineManager):
    """Mock baseline manager for testing."""

    def __init__(self, environment: str):
        """Initialize mock manager."""
        super().__init__(environment)
        self._use_mock = True
        self._mock_store = {}

    def add_mock_baseline(
        self, resource_type: str, resource_name: str, namespace: str, content: dict
    ) -> None:
        """Add a mock baseline for testing.

        Args:
            resource_type: Kubernetes resource kind
            resource_name: Resource name
            namespace: Resource namespace
            content: Baseline content dict
        """
        baseline = Baseline(
            environment=self.environment,
            resource_type=resource_type,
            resource_name=resource_name,
            namespace=namespace,
            content=content,
            content_hash=hashlib.sha256(
                json.dumps(content, sort_keys=True).encode()
            ).hexdigest()[:16],
            validated_at=datetime.utcnow(),
            validation_run_id="mock-run",
            created_by="mock",
        )
        item = baseline.to_item()
        key = f"{baseline.pk}#{baseline.sk}"
        self._mock_store[key] = item
