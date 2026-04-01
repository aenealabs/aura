"""Tests for Environment Validator validators (ADR-062)."""

from src.services.env_validator.models import ManifestResource, Severity
from src.services.env_validator.validators.arn import ArnValidator, ParsedArn
from src.services.env_validator.validators.configmap import ConfigMapValidator
from src.services.env_validator.validators.deployment import DeploymentValidator
from src.services.env_validator.validators.naming import NamingValidator

from .conftest import TEST_DEV_ACCOUNT_ID, TEST_QA_ACCOUNT_ID

# Note: clear_cache fixture moved to conftest.py (setup_test_environment)


class TestParsedArn:
    """Tests for ARN parsing."""

    def test_parse_valid_arn(self):
        """Test parsing a valid ARN."""
        arn = f"arn:aws:dynamodb:us-east-1:{TEST_DEV_ACCOUNT_ID}:table/aura-jobs-dev"
        parsed = ParsedArn.parse(arn)

        assert parsed is not None
        assert parsed.partition == "aws"
        assert parsed.service == "dynamodb"
        assert parsed.region == "us-east-1"
        assert parsed.account_id == TEST_DEV_ACCOUNT_ID
        assert parsed.resource == "table/aura-jobs-dev"

    def test_parse_govcloud_arn(self):
        """Test parsing a GovCloud ARN."""
        arn = "arn:aws-us-gov:s3:us-gov-west-1:123456789012:bucket/my-bucket"
        parsed = ParsedArn.parse(arn)

        assert parsed is not None
        assert parsed.partition == "aws-us-gov"
        assert parsed.region == "us-gov-west-1"

    def test_parse_global_service_arn(self):
        """Test parsing an ARN for a global service (empty region)."""
        arn = f"arn:aws:iam::{TEST_DEV_ACCOUNT_ID}:role/my-role"
        parsed = ParsedArn.parse(arn)

        assert parsed is not None
        assert parsed.service == "iam"
        assert parsed.region == ""
        assert parsed.account_id == TEST_DEV_ACCOUNT_ID

    def test_parse_invalid_arn(self):
        """Test parsing an invalid ARN returns None."""
        assert ParsedArn.parse("not-an-arn") is None
        assert ParsedArn.parse("arn:invalid") is None
        assert ParsedArn.parse("") is None


class TestArnValidator:
    """Tests for ARN validation."""

    def test_env001_wrong_account_id(self):
        """Test ENV-001: Detect wrong account ID in ARN."""
        validator = ArnValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="test-config",
            namespace="default",
            raw={
                "data": {
                    "TABLE_ARN": f"arn:aws:dynamodb:us-east-1:{TEST_DEV_ACCOUNT_ID}:table/aura-jobs-dev"
                }
            },
        )

        violations = validator.validate(resource)

        # Should detect DEV account ID in QA environment
        assert len(violations) >= 1
        account_violations = [v for v in violations if v.rule_id == "ENV-001"]
        assert len(account_violations) == 1
        assert account_violations[0].severity == Severity.CRITICAL
        assert TEST_DEV_ACCOUNT_ID in account_violations[0].actual_value

    def test_env001_correct_account_id(self):
        """Test ENV-001: No violation for correct account ID."""
        validator = ArnValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="test-config",
            namespace="default",
            raw={
                "data": {
                    "TABLE_ARN": f"arn:aws:dynamodb:us-east-1:{TEST_QA_ACCOUNT_ID}:table/aura-jobs-qa"
                }
            },
        )

        violations = validator.validate(resource)
        account_violations = [v for v in violations if v.rule_id == "ENV-001"]
        assert len(account_violations) == 0

    def test_env006_wrong_region(self):
        """Test ENV-006: Detect wrong region in ARN."""
        validator = ArnValidator("prod")  # prod uses us-gov-west-1

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="test-config",
            namespace="default",
            raw={
                "data": {
                    # Using us-east-1 instead of us-gov-west-1
                    "QUEUE_ARN": "arn:aws:sqs:us-east-1:123456789012:my-queue"
                }
            },
        )

        violations = validator.validate(resource)
        region_violations = [v for v in violations if v.rule_id == "ENV-006"]
        # Should have a region violation (prod expects us-gov-west-1)
        assert len(region_violations) >= 1

    def test_env008_iam_role_wrong_account(self):
        """Test ENV-008: Detect IAM role from wrong account."""
        validator = ArnValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ServiceAccount",
            name="test-sa",
            namespace="default",
            raw={
                "metadata": {
                    "annotations": {
                        "eks.amazonaws.com/role-arn": f"arn:aws:iam::{TEST_DEV_ACCOUNT_ID}:role/dev-role"
                    }
                }
            },
        )

        violations = validator.validate(resource)
        iam_violations = [v for v in violations if v.rule_id == "ENV-008"]
        assert len(iam_violations) == 1
        assert iam_violations[0].severity == Severity.CRITICAL


class TestConfigMapValidator:
    """Tests for ConfigMap validation."""

    def test_env003_dynamodb_wrong_env(self):
        """Test ENV-003: Detect DynamoDB table with wrong environment suffix."""
        validator = ConfigMapValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "data": {
                    "JOBS_TABLE_NAME": "aura-gpu-jobs-dev",  # Should be -qa
                }
            },
        )

        violations = validator.validate(resource)
        table_violations = [v for v in violations if v.rule_id == "ENV-003"]
        assert len(table_violations) == 1
        assert table_violations[0].severity == Severity.CRITICAL
        assert "dev" in table_violations[0].message

    def test_env004_neptune_wrong_endpoint(self):
        """Test ENV-004: Detect Neptune endpoint for wrong environment."""
        validator = ConfigMapValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "data": {
                    "NEPTUNE_ENDPOINT": "aura-neptune-dev.cluster-abc.neptune.amazonaws.com",
                }
            },
        )

        violations = validator.validate(resource)
        endpoint_violations = [v for v in violations if v.rule_id == "ENV-004"]
        assert len(endpoint_violations) == 1
        assert endpoint_violations[0].severity == Severity.CRITICAL

    def test_env101_environment_var_mismatch(self):
        """Test ENV-101: Detect ENVIRONMENT variable mismatch."""
        validator = ConfigMapValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "data": {
                    "ENVIRONMENT": "dev",  # Should be "qa"
                }
            },
        )

        violations = validator.validate(resource)
        env_violations = [v for v in violations if v.rule_id == "ENV-101"]
        assert len(env_violations) == 1
        assert env_violations[0].severity == Severity.WARNING
        assert env_violations[0].auto_remediable is True

    def test_env005_sns_wrong_account(self):
        """Test ENV-005: Detect SNS ARN with wrong account."""
        validator = ConfigMapValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "data": {
                    "SNS_TOPIC_ARN": f"arn:aws:sns:us-east-1:{TEST_DEV_ACCOUNT_ID}:aura-alerts-dev",
                }
            },
        )

        violations = validator.validate(resource)
        sns_violations = [v for v in violations if v.rule_id == "ENV-005"]
        assert len(sns_violations) >= 1

    def test_no_violations_correct_config(self):
        """Test that correct configuration produces no violations."""
        validator = ConfigMapValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "data": {
                    "ENVIRONMENT": "qa",
                    "JOBS_TABLE_NAME": "aura-gpu-jobs-qa",
                    "NEPTUNE_ENDPOINT": "aura-neptune-qa.cluster-abc.neptune.amazonaws.com",
                    "SNS_TOPIC_ARN": f"arn:aws:sns:us-east-1:{TEST_QA_ACCOUNT_ID}:aura-alerts-qa",
                }
            },
        )

        violations = validator.validate(resource)
        critical = [v for v in violations if v.severity == Severity.CRITICAL]
        assert len(critical) == 0


class TestDeploymentValidator:
    """Tests for Deployment validation."""

    def test_env002_ecr_wrong_account(self):
        """Test ENV-002: Detect ECR image from wrong account."""
        validator = DeploymentValidator("qa")

        resource = ManifestResource(
            api_version="apps/v1",
            kind="Deployment",
            name="aura-api",
            namespace="default",
            raw={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "api",
                                    "image": f"{TEST_DEV_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api:latest",
                                }
                            ]
                        }
                    }
                }
            },
        )

        violations = validator.validate(resource)
        ecr_violations = [v for v in violations if v.rule_id == "ENV-002"]
        assert len(ecr_violations) >= 1
        assert ecr_violations[0].severity == Severity.CRITICAL
        assert TEST_DEV_ACCOUNT_ID in ecr_violations[0].actual_value

    def test_env002_correct_ecr(self):
        """Test ENV-002: No violation for correct ECR registry."""
        validator = DeploymentValidator("qa")

        resource = ManifestResource(
            api_version="apps/v1",
            kind="Deployment",
            name="aura-api",
            namespace="default",
            raw={
                "spec": {
                    "template": {
                        "spec": {
                            "containers": [
                                {
                                    "name": "api",
                                    "image": f"{TEST_QA_ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/aura-api-qa:latest",
                                }
                            ]
                        }
                    }
                }
            },
        )

        violations = validator.validate(resource)
        ecr_violations = [v for v in violations if v.rule_id == "ENV-002"]
        assert len(ecr_violations) == 0

    def test_env104_service_account_wrong_irsa(self):
        """Test ENV-104: Detect IRSA annotation with wrong account."""
        validator = DeploymentValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ServiceAccount",
            name="aura-api",
            namespace="default",
            raw={
                "metadata": {
                    "annotations": {
                        "eks.amazonaws.com/role-arn": f"arn:aws:iam::{TEST_DEV_ACCOUNT_ID}:role/aura-api-irsa-dev"
                    }
                }
            },
        )

        violations = validator.validate(resource)
        irsa_violations = [v for v in violations if v.rule_id == "ENV-104"]
        assert len(irsa_violations) == 1
        assert irsa_violations[0].severity == Severity.WARNING


class TestNamingValidator:
    """Tests for naming convention validation."""

    def test_env201_missing_prefix(self):
        """Test ENV-201: Detect resource without project prefix."""
        validator = NamingValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="my-config",  # Missing "aura-" prefix
            namespace="default",
            raw={"metadata": {"name": "my-config"}},
        )

        violations = validator.validate(resource)
        naming_violations = [v for v in violations if v.rule_id == "ENV-201"]
        assert len(naming_violations) == 1
        assert naming_violations[0].severity == Severity.INFO

    def test_env202_missing_labels(self):
        """Test ENV-202: Detect missing required labels."""
        validator = NamingValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "metadata": {
                    "name": "aura-api-config",
                    "labels": {},  # Missing required labels
                }
            },
        )

        violations = validator.validate(resource)
        label_violations = [v for v in violations if v.rule_id == "ENV-202"]
        # Should have violations for missing "app" and "environment" labels
        assert len(label_violations) >= 2

    def test_env202_wrong_environment_label(self):
        """Test ENV-202: Detect wrong environment label value."""
        validator = NamingValidator("qa")

        resource = ManifestResource(
            api_version="v1",
            kind="ConfigMap",
            name="aura-api-config",
            namespace="default",
            raw={
                "metadata": {
                    "name": "aura-api-config",
                    "labels": {
                        "app": "aura-api",
                        "environment": "dev",  # Should be "qa"
                    },
                }
            },
        )

        violations = validator.validate(resource)
        label_violations = [
            v
            for v in violations
            if v.rule_id == "ENV-202" and "environment label" in v.message.lower()
        ]
        assert len(label_violations) == 1
