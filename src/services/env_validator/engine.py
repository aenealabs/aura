"""Validation engine for Environment Validator (ADR-062).

Orchestrates all validators and produces validation results.
"""

import hashlib
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import yaml

from src.services.env_validator.models import (
    ManifestResource,
    Severity,
    TriggerType,
    ValidationResult,
    ValidationRun,
    Violation,
)
from src.services.env_validator.validators.arn import ArnValidator
from src.services.env_validator.validators.configmap import ConfigMapValidator
from src.services.env_validator.validators.deployment import DeploymentValidator
from src.services.env_validator.validators.naming import NamingValidator

logger = logging.getLogger(__name__)


class ValidationEngine:
    """Orchestrates environment validation across all validators."""

    def __init__(self, target_env: str):
        """Initialize the validation engine.

        Args:
            target_env: Target environment name (dev, qa, staging, prod)
        """
        self.target_env = target_env

        # Initialize all validators
        self.validators = [
            ArnValidator(target_env),
            ConfigMapValidator(target_env),
            DeploymentValidator(target_env),
            NamingValidator(target_env),
        ]

    def validate_manifest(
        self,
        manifest_content: str,
        trigger: TriggerType = TriggerType.MANUAL,
    ) -> ValidationRun:
        """Validate a Kubernetes manifest file.

        Args:
            manifest_content: YAML content of the manifest
            trigger: What triggered this validation

        Returns:
            ValidationRun with results
        """
        start_time = time.time()
        run_id = str(uuid.uuid4())[:8]
        manifest_hash = hashlib.sha256(manifest_content.encode()).hexdigest()[:12]

        all_violations: list[Violation] = []
        resources_scanned = 0

        # Parse YAML (supports multi-document manifests)
        try:
            documents = list(yaml.safe_load_all(manifest_content))
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML: {e}")
            return self._create_parse_error_run(run_id, trigger, str(e))

        # Validate each resource in the manifest
        for doc in documents:
            if not doc or not isinstance(doc, dict):
                continue

            resource = self._parse_resource(doc)
            if not resource:
                continue

            resources_scanned += 1

            # Run all validators
            for validator in self.validators:
                try:
                    violations = validator.validate(resource)
                    all_violations.extend(violations)
                except Exception as e:
                    logger.warning(
                        f"Validator {validator.__class__.__name__} failed on "
                        f"{resource.full_name}: {e}"
                    )

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Categorize violations by severity
        critical = [v for v in all_violations if v.severity == Severity.CRITICAL]
        warnings = [v for v in all_violations if v.severity == Severity.WARNING]
        info = [v for v in all_violations if v.severity == Severity.INFO]

        # Determine overall result
        if critical:
            result = ValidationResult.FAIL
        elif warnings:
            result = ValidationResult.WARN
        else:
            result = ValidationResult.PASS

        return ValidationRun(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            environment=self.target_env,
            trigger=trigger,
            manifest_hash=manifest_hash,
            duration_ms=duration_ms,
            result=result,
            violations=critical,
            warnings=warnings,
            info=info,
            resources_scanned=resources_scanned,
        )

    def validate_resource(self, resource: ManifestResource) -> list[Violation]:
        """Validate a single Kubernetes resource.

        Args:
            resource: Parsed Kubernetes resource

        Returns:
            List of violations found
        """
        all_violations = []

        for validator in self.validators:
            try:
                violations = validator.validate(resource)
                all_violations.extend(violations)
            except Exception as e:
                logger.warning(
                    f"Validator {validator.__class__.__name__} failed on "
                    f"{resource.full_name}: {e}"
                )

        return all_violations

    def _parse_resource(self, doc: dict) -> Optional[ManifestResource]:
        """Parse a YAML document into a ManifestResource.

        Args:
            doc: Parsed YAML document

        Returns:
            ManifestResource if valid, None otherwise
        """
        api_version = doc.get("apiVersion", "")
        kind = doc.get("kind", "")
        metadata = doc.get("metadata", {})
        name = metadata.get("name", "")
        namespace = metadata.get("namespace")

        if not api_version or not kind or not name:
            return None

        return ManifestResource(
            api_version=api_version,
            kind=kind,
            name=name,
            namespace=namespace,
            raw=doc,
        )

    def _create_parse_error_run(
        self, run_id: str, trigger: TriggerType, error: str
    ) -> ValidationRun:
        """Create a ValidationRun for a parse error."""
        return ValidationRun(
            run_id=run_id,
            timestamp=datetime.now(timezone.utc),
            environment=self.target_env,
            trigger=trigger,
            manifest_hash=None,
            duration_ms=0,
            result=ValidationResult.FAIL,
            violations=[
                Violation(
                    rule_id="PARSE-001",
                    severity=Severity.CRITICAL,
                    resource_type="Manifest",
                    resource_name="unknown",
                    field_path="",
                    expected_value="Valid YAML",
                    actual_value="Invalid YAML",
                    message=f"Failed to parse manifest: {error}",
                    suggested_fix="Fix YAML syntax errors",
                    auto_remediable=False,
                )
            ],
            warnings=[],
            info=[],
            resources_scanned=0,
        )


def validate_manifest_file(
    file_path: str,
    target_env: str,
    trigger: TriggerType = TriggerType.MANUAL,
) -> ValidationRun:
    """Convenience function to validate a manifest file.

    Args:
        file_path: Path to the manifest file
        target_env: Target environment name
        trigger: What triggered this validation

    Returns:
        ValidationRun with results
    """
    with open(file_path, "r") as f:
        content = f.read()

    engine = ValidationEngine(target_env)
    return engine.validate_manifest(content, trigger)


def validate_manifest_string(
    manifest_content: str,
    target_env: str,
    trigger: TriggerType = TriggerType.MANUAL,
) -> ValidationRun:
    """Convenience function to validate a manifest string.

    Args:
        manifest_content: YAML content of the manifest
        target_env: Target environment name
        trigger: What triggered this validation

    Returns:
        ValidationRun with results
    """
    engine = ValidationEngine(target_env)
    return engine.validate_manifest(manifest_content, trigger)
