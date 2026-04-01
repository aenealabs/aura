"""Tests for Environment Validator engine (ADR-062)."""

from src.services.env_validator.engine import ValidationEngine, validate_manifest_string
from src.services.env_validator.models import TriggerType, ValidationResult

from .conftest import TEST_DEV_ACCOUNT_ID, TEST_QA_ACCOUNT_ID

# Note: clear_cache fixture moved to conftest.py (setup_test_environment)


class TestValidationEngine:
    """Tests for ValidationEngine."""

    def test_validate_empty_manifest(self):
        """Test validation of empty manifest."""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest("")

        assert result.result == ValidationResult.PASS
        assert result.resources_scanned == 0

    def test_validate_single_resource(self):
        """Test validation of a single resource."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-test-config
  labels:
    app: test
    environment: qa
data:
  ENVIRONMENT: qa
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)

        assert result.resources_scanned == 1
        # Should pass with only INFO level issues (naming prefix)
        assert result.result in [ValidationResult.PASS, ValidationResult.WARN]

    def test_detect_cross_env_configmap(self):
        """Test detection of cross-environment ConfigMap."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  labels:
    app: aura-api
    environment: qa
data:
  ENVIRONMENT: dev
  JOBS_TABLE: aura-gpu-jobs-dev
  NEPTUNE_ENDPOINT: aura-neptune-dev.cluster-abc.neptune.amazonaws.com
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)

        assert result.result == ValidationResult.FAIL
        assert result.has_critical
        # Should have violations for table name and endpoint
        critical_rule_ids = [v.rule_id for v in result.violations]
        assert "ENV-003" in critical_rule_ids  # DynamoDB table
        assert "ENV-004" in critical_rule_ids  # Neptune endpoint

    def test_detect_cross_env_deployment(self):
        """Test detection of cross-environment Deployment."""
        manifest = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  labels:
    app: aura-api
    environment: qa
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aura-api
  template:
    metadata:
      labels:
        app: aura-api
    spec:
      containers:
      - name: api
        image: {TEST_DEV_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)

        assert result.result == ValidationResult.FAIL
        assert result.has_critical
        # Should have ECR violation
        ecr_violations = [v for v in result.violations if v.rule_id == "ENV-002"]
        assert len(ecr_violations) >= 1

    def test_multi_document_manifest(self):
        """Test validation of multi-document YAML manifest."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config-1
  labels:
    app: test
    environment: qa
data:
  ENVIRONMENT: qa
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-config-2
  labels:
    app: test
    environment: qa
data:
  ENVIRONMENT: dev
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)

        assert result.resources_scanned == 2
        # Second ConfigMap has wrong ENVIRONMENT
        env_warnings = [v for v in result.warnings if v.rule_id == "ENV-101"]
        assert len(env_warnings) == 1

    def test_invalid_yaml(self):
        """Test handling of invalid YAML."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: test
  invalid yaml here: [[[
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)

        assert result.result == ValidationResult.FAIL
        assert result.resources_scanned == 0
        parse_errors = [v for v in result.violations if v.rule_id == "PARSE-001"]
        assert len(parse_errors) == 1

    def test_trigger_type_preserved(self):
        """Test that trigger type is preserved in result."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-test
data: {}
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest, TriggerType.PRE_DEPLOY)

        assert result.trigger == TriggerType.PRE_DEPLOY

    def test_run_id_generated(self):
        """Test that unique run ID is generated."""
        manifest = "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: test"
        engine = ValidationEngine("qa")

        result1 = engine.validate_manifest(manifest)
        result2 = engine.validate_manifest(manifest)

        assert result1.run_id != result2.run_id


class TestValidateManifestString:
    """Tests for validate_manifest_string helper."""

    def test_convenience_function(self):
        """Test that convenience function works."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  labels:
    app: aura-api
    environment: qa
data:
  ENVIRONMENT: qa
"""
        result = validate_manifest_string(manifest, "qa")

        assert result.environment == "qa"
        assert result.resources_scanned == 1


class TestValidationRunToDict:
    """Tests for ValidationRun serialization."""

    def test_to_dict_basic(self):
        """Test basic serialization."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
data:
  ENVIRONMENT: dev
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)
        result_dict = result.to_dict()

        assert "run_id" in result_dict
        assert "timestamp" in result_dict
        assert result_dict["environment"] == "qa"
        assert "violations" in result_dict
        assert "warnings" in result_dict
        assert "info" in result_dict

    def test_to_dict_with_violations(self):
        """Test serialization with violations."""
        manifest = """
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
data:
  JOBS_TABLE: aura-jobs-dev
"""
        engine = ValidationEngine("qa")
        result = engine.validate_manifest(manifest)
        result_dict = result.to_dict()

        assert result_dict["has_critical"] is True
        assert len(result_dict["violations"]) > 0

        violation = result_dict["violations"][0]
        assert "rule_id" in violation
        assert "severity" in violation
        assert "message" in violation


class TestRealWorldScenarios:
    """Integration tests for real-world scenarios discovered during GPU Scheduler deployment."""

    def test_qa_configmap_pointing_to_dev(self):
        """Test the exact scenario that caused QA issues.

        This was discovered when QA ConfigMap had DEV values causing
        AccessDeniedException errors.
        """
        manifest = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  namespace: default
  labels:
    app: aura-api
    environment: dev
data:
  APPROVAL_TABLE_NAME: aura-approval-requests-dev
  ENVIRONMENT: dev
  HITL_SNS_TOPIC_ARN: arn:aws:sns:us-east-1:{TEST_DEV_ACCOUNT_ID}:aura-hitl-notifications-dev
  NEPTUNE_ENDPOINT: aura-neptune-dev.cluster-EXAMPLE.us-east-1.neptune.amazonaws.com
  OPENSEARCH_ENDPOINT: vpc-aura-dev-EXAMPLE.us-east-1.es.amazonaws.com
  WORKFLOW_TABLE_NAME: aura-patch-workflows-dev
"""
        result = validate_manifest_string(manifest, "qa")

        assert result.result == ValidationResult.FAIL
        assert result.has_critical

        # Should catch multiple issues
        rule_ids = [v.rule_id for v in result.violations]
        assert "ENV-003" in rule_ids  # DynamoDB tables
        assert "ENV-004" in rule_ids  # Neptune/OpenSearch endpoints
        assert "ENV-005" in rule_ids  # SNS ARN

        # Should also catch the environment variable as warning
        warning_ids = [v.rule_id for v in result.warnings]
        assert "ENV-101" in warning_ids  # ENVIRONMENT variable

    def test_qa_deployment_with_dev_ecr(self):
        """Test detection of QA deployment pulling from DEV ECR.

        This scenario was discovered when QA kubectl deployment was
        incorrectly pointing to DEV ECR.
        """
        manifest = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: default
  labels:
    app: aura-api
    environment: qa
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aura-api
  template:
    metadata:
      labels:
        app: aura-api
    spec:
      serviceAccountName: aura-api
      containers:
      - name: aura-api
        image: {TEST_DEV_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest
        ports:
        - containerPort: 8080
"""
        result = validate_manifest_string(manifest, "qa")

        assert result.result == ValidationResult.FAIL
        assert result.has_critical

        # Should detect wrong ECR registry
        ecr_violations = [v for v in result.violations if v.rule_id == "ENV-002"]
        assert len(ecr_violations) >= 1
        assert TEST_DEV_ACCOUNT_ID in ecr_violations[0].actual_value

    def test_correct_qa_deployment(self):
        """Test that a correctly configured QA deployment passes."""
        manifest = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-api-config
  namespace: default
  labels:
    app: aura-api
    environment: qa
data:
  ENVIRONMENT: qa
  JOBS_TABLE_NAME: aura-gpu-jobs-qa
  QUOTAS_TABLE_NAME: aura-gpu-quotas-qa
  NEPTUNE_ENDPOINT: aura-neptune-qa.cluster-EXAMPLE.us-east-1.neptune.amazonaws.com
  SNS_TOPIC_ARN: arn:aws:sns:us-east-1:{TEST_QA_ACCOUNT_ID}:aura-alerts-qa
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-api
  namespace: default
  labels:
    app: aura-api
    environment: qa
spec:
  replicas: 1
  selector:
    matchLabels:
      app: aura-api
  template:
    metadata:
      labels:
        app: aura-api
    spec:
      containers:
      - name: aura-api
        image: {TEST_QA_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api-qa:latest
"""
        result = validate_manifest_string(manifest, "qa")

        # Should pass with no critical violations
        assert not result.has_critical
        assert result.result in [ValidationResult.PASS, ValidationResult.WARN]
