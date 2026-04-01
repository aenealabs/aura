"""
Tests for IaC Correlation Engine
================================

ADR-056 Phase 2: Cloud Infrastructure Correlation

Tests for IaC parsing and resource correlation.
"""

import platform
import tempfile
from pathlib import Path

import pytest

# pytest-forked on macOS to prevent state pollution
if platform.system() != "Linux":
    pytestmark = pytest.mark.forked

from src.services.cloud_discovery.exceptions import IaCParseError
from src.services.cloud_discovery.iac_correlator import IaCCorrelator, IaCResource
from src.services.cloud_discovery.types import (
    CloudProvider,
    CloudResource,
    CloudResourceType,
    DiscoveryResult,
)


class TestIaCResource:
    """Tests for IaCResource dataclass."""

    def test_create_resource(self) -> None:
        """Test creating IaC resource."""
        resource = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
            source_line=42,
        )
        assert resource.logical_id == "MyBucket"
        assert resource.resource_type == "AWS::S3::Bucket"
        assert resource.source_file == "template.yaml"
        assert resource.source_line == 42

    def test_create_resource_with_properties(self) -> None:
        """Test creating IaC resource with properties."""
        resource = IaCResource(
            logical_id="MyInstance",
            resource_type="AWS::EC2::Instance",
            source_file="template.yaml",
            properties={"InstanceType": "t3.micro"},
            depends_on=["MySecurityGroup"],
        )
        assert resource.properties["InstanceType"] == "t3.micro"
        assert "MySecurityGroup" in resource.depends_on


class TestIaCCorrelator:
    """Tests for IaCCorrelator."""

    def test_create_correlator(self) -> None:
        """Test creating correlator."""
        correlator = IaCCorrelator()
        assert correlator.use_mock is False

    def test_create_correlator_mock_mode(self) -> None:
        """Test creating correlator in mock mode."""
        correlator = IaCCorrelator(use_mock=True)
        assert correlator.use_mock is True


class TestIaCCorrelatorCloudFormationParsing:
    """Tests for CloudFormation parsing."""

    @pytest.fixture
    def temp_cfn_dir(self) -> Path:
        """Create temp directory with CloudFormation templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Create YAML template
            yaml_content = """
AWSTemplateFormatVersion: '2010-09-09'
Description: Test template

Resources:
  MyBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: my-test-bucket

  MyLambda:
    Type: AWS::Lambda::Function
    Properties:
      FunctionName: my-function
      Runtime: python3.11
      Handler: index.handler
"""
            (path / "template.yaml").write_text(yaml_content)

            # Create JSON template
            json_content = """
{
  "AWSTemplateFormatVersion": "2010-09-09",
  "Resources": {
    "MyTable": {
      "Type": "AWS::DynamoDB::Table",
      "Properties": {
        "TableName": "my-table"
      }
    }
  }
}
"""
            (path / "template.json").write_text(json_content)

            yield path

    @pytest.mark.asyncio
    async def test_parse_yaml_template(self, temp_cfn_dir: Path) -> None:
        """Test parsing YAML CloudFormation template."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_cfn_dir, patterns=["*.yaml"])

        # Should find 2 resources from YAML
        assert len(resources) == 2
        logical_ids = {r.logical_id for r in resources}
        assert "MyBucket" in logical_ids
        assert "MyLambda" in logical_ids

    @pytest.mark.asyncio
    async def test_parse_json_template(self, temp_cfn_dir: Path) -> None:
        """Test parsing JSON CloudFormation template."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_cfn_dir, patterns=["*.json"])

        # Should find 1 resource from JSON
        assert len(resources) == 1
        assert resources[0].logical_id == "MyTable"
        assert resources[0].resource_type == "AWS::DynamoDB::Table"

    @pytest.mark.asyncio
    async def test_parse_all_templates(self, temp_cfn_dir: Path) -> None:
        """Test parsing all templates with default patterns."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_cfn_dir)

        # Should find all 3 resources
        assert len(resources) == 3

    @pytest.mark.asyncio
    async def test_parse_nonexistent_directory(self) -> None:
        """Test parsing nonexistent directory raises error."""
        correlator = IaCCorrelator()
        with pytest.raises(IaCParseError):
            await correlator.parse_repository("/nonexistent/path")

    @pytest.mark.asyncio
    async def test_parse_extracts_line_numbers(self, temp_cfn_dir: Path) -> None:
        """Test line numbers are extracted from templates."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_cfn_dir, patterns=["*.yaml"])

        bucket_resource = next(r for r in resources if r.logical_id == "MyBucket")
        # Line number should be non-zero (found in file)
        assert bucket_resource.source_line > 0


class TestIaCCorrelatorTerraformParsing:
    """Tests for Terraform parsing."""

    @pytest.fixture
    def temp_tf_dir(self) -> Path:
        """Create temp directory with Terraform files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            tf_content = """
resource "aws_instance" "web" {
  ami           = "ami-12345678"
  instance_type = "t3.micro"
}

resource "aws_s3_bucket" "data" {
  bucket = "my-data-bucket"
}

resource "aws_lambda_function" "handler" {
  function_name = "my-handler"
  runtime       = "python3.11"
}
"""
            (path / "main.tf").write_text(tf_content)
            yield path

    @pytest.mark.asyncio
    async def test_parse_terraform(self, temp_tf_dir: Path) -> None:
        """Test parsing Terraform files."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_tf_dir, patterns=["*.tf"])

        # Should find 3 resources
        assert len(resources) == 3

        types = {r.resource_type for r in resources}
        assert "aws_instance" in types
        assert "aws_s3_bucket" in types
        assert "aws_lambda_function" in types

    @pytest.mark.asyncio
    async def test_parse_terraform_logical_ids(self, temp_tf_dir: Path) -> None:
        """Test Terraform resource names are captured."""
        correlator = IaCCorrelator()
        resources = await correlator.parse_repository(temp_tf_dir, patterns=["*.tf"])

        logical_ids = {r.logical_id for r in resources}
        assert "web" in logical_ids
        assert "data" in logical_ids
        assert "handler" in logical_ids


class TestIaCCorrelatorTypeMapping:
    """Tests for resource type mapping."""

    def test_get_cloud_type_cloudformation(self) -> None:
        """Test CloudFormation type mapping."""
        correlator = IaCCorrelator()

        assert (
            correlator._get_cloud_type("AWS::EC2::Instance")
            == CloudResourceType.EC2_INSTANCE
        )
        assert (
            correlator._get_cloud_type("AWS::S3::Bucket") == CloudResourceType.S3_BUCKET
        )
        assert (
            correlator._get_cloud_type("AWS::Lambda::Function")
            == CloudResourceType.LAMBDA_FUNCTION
        )
        assert (
            correlator._get_cloud_type("AWS::DynamoDB::Table")
            == CloudResourceType.DYNAMODB_TABLE
        )

    def test_get_cloud_type_terraform(self) -> None:
        """Test Terraform type mapping."""
        correlator = IaCCorrelator()

        assert (
            correlator._get_cloud_type("aws_instance") == CloudResourceType.EC2_INSTANCE
        )
        assert (
            correlator._get_cloud_type("aws_s3_bucket") == CloudResourceType.S3_BUCKET
        )
        assert (
            correlator._get_cloud_type("aws_lambda_function")
            == CloudResourceType.LAMBDA_FUNCTION
        )
        assert (
            correlator._get_cloud_type("aws_dynamodb_table")
            == CloudResourceType.DYNAMODB_TABLE
        )

    def test_get_cloud_type_unknown(self) -> None:
        """Test unknown type returns UNKNOWN."""
        correlator = IaCCorrelator()

        assert correlator._get_cloud_type("Unknown::Type") == CloudResourceType.UNKNOWN
        assert (
            correlator._get_cloud_type("custom_resource") == CloudResourceType.UNKNOWN
        )


class TestIaCCorrelatorCorrelation:
    """Tests for IaC-to-resource correlation."""

    @pytest.fixture
    def iac_resources(self) -> list[IaCResource]:
        """Create sample IaC resources."""
        return [
            IaCResource(
                logical_id="MyBucket",
                resource_type="AWS::S3::Bucket",
                source_file="template.yaml",
                properties={"BucketName": "my-bucket"},
            ),
            IaCResource(
                logical_id="MyLambda",
                resource_type="AWS::Lambda::Function",
                source_file="template.yaml",
                properties={"Runtime": "python3.11"},
            ),
            IaCResource(
                logical_id="UnmatchedResource",
                resource_type="AWS::EC2::Instance",
                source_file="template.yaml",
            ),
        ]

    @pytest.fixture
    def discovery_result(self) -> DiscoveryResult:
        """Create sample discovery result."""
        return DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
            regions=["us-east-1"],
            resources=[
                CloudResource(
                    resource_id="arn:aws:s3:::my-bucket",
                    resource_type=CloudResourceType.S3_BUCKET,
                    provider=CloudProvider.AWS,
                    name="my-bucket",
                    tags={"aws:cloudformation:logical-id": "MyBucket"},
                ),
                CloudResource(
                    resource_id="arn:aws:lambda:us-east-1:123456789012:function:my-lambda",
                    resource_type=CloudResourceType.LAMBDA_FUNCTION,
                    provider=CloudProvider.AWS,
                    name="my-lambda",
                    properties={"runtime": "python3.11"},
                ),
                CloudResource(
                    resource_id="arn:aws:sqs:us-east-1:123456789012:queue:orphan-queue",
                    resource_type=CloudResourceType.SQS_QUEUE,
                    provider=CloudProvider.AWS,
                    name="orphan-queue",
                ),
            ],
        )

    @pytest.mark.asyncio
    async def test_correlate_basic(
        self,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
    ) -> None:
        """Test basic correlation."""
        correlator = IaCCorrelator()
        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery_result,
        )

        assert result.repository_id == "my-repo"
        # Should have some matched and some unmatched
        assert len(result.iac_mappings) > 0
        assert len(result.unmatched_iac) > 0

    @pytest.mark.asyncio
    async def test_correlate_cfn_tag_match(
        self,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
    ) -> None:
        """Test correlation matches on CloudFormation tag."""
        correlator = IaCCorrelator()
        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery_result,
        )

        # Bucket should match via tag
        bucket_mapping = next(
            (m for m in result.iac_mappings if m.logical_id == "MyBucket"),
            None,
        )
        assert bucket_mapping is not None
        assert bucket_mapping.physical_resource_id == "arn:aws:s3:::my-bucket"
        assert bucket_mapping.confidence > 0.5

    @pytest.mark.asyncio
    async def test_correlate_identifies_drift(
        self,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
    ) -> None:
        """Test correlation identifies drift (resources not in IaC)."""
        correlator = IaCCorrelator()
        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery_result,
        )

        # SQS queue should be in drift (not in IaC)
        drift_ids = {r.resource_id for r in result.unmatched_resources}
        assert "arn:aws:sqs:us-east-1:123456789012:queue:orphan-queue" in drift_ids

    @pytest.mark.asyncio
    async def test_correlate_identifies_undeployed(
        self,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
    ) -> None:
        """Test correlation identifies undeployed IaC resources."""
        correlator = IaCCorrelator()
        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery_result,
        )

        # UnmatchedResource (EC2) should be in unmatched_iac
        unmatched_ids = {m.logical_id for m in result.unmatched_iac}
        assert "UnmatchedResource" in unmatched_ids

    @pytest.mark.asyncio
    async def test_correlate_correlation_rate(
        self,
        iac_resources: list[IaCResource],
        discovery_result: DiscoveryResult,
    ) -> None:
        """Test correlation rate calculation."""
        correlator = IaCCorrelator()
        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery_result,
        )

        # Should be between 0 and 1
        assert 0.0 <= result.correlation_rate <= 1.0

    @pytest.mark.asyncio
    async def test_correlate_mock_mode(self, iac_resources: list[IaCResource]) -> None:
        """Test correlation in mock mode."""
        correlator = IaCCorrelator(use_mock=True)
        discovery = DiscoveryResult(
            provider=CloudProvider.AWS,
            account_id="123456789012",
        )

        result = await correlator.correlate(
            repository_id="my-repo",
            iac_resources=iac_resources,
            discovery_result=discovery,
        )

        # Mock mode returns half matched, half unmatched
        assert result.correlation_confidence == 0.85


class TestIaCCorrelatorMatchScoring:
    """Tests for match scoring logic."""

    def test_calculate_match_score_exact_name(self) -> None:
        """Test match score for exact name match."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        resource = CloudResource(
            resource_id="arn:aws:s3:::mybucket",
            resource_type=CloudResourceType.S3_BUCKET,
            provider=CloudProvider.AWS,
            name="mybucket",
        )

        score = correlator._calculate_match_score(iac, resource)
        assert score > 0.0

    def test_calculate_match_score_cfn_tag(self) -> None:
        """Test match score for CloudFormation tag match."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        resource = CloudResource(
            resource_id="arn:aws:s3:::some-bucket",
            resource_type=CloudResourceType.S3_BUCKET,
            provider=CloudProvider.AWS,
            name="some-bucket",
            tags={"aws:cloudformation:logical-id": "MyBucket"},
        )

        score = correlator._calculate_match_score(iac, resource)
        # Should get tag match bonus
        assert score >= 0.3

    def test_calculate_match_score_no_match(self) -> None:
        """Test match score for no match."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="FirstResource",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        resource = CloudResource(
            resource_id="arn:aws:s3:::completely-different",
            resource_type=CloudResourceType.S3_BUCKET,
            provider=CloudProvider.AWS,
            name="completely-different",
        )

        score = correlator._calculate_match_score(iac, resource)
        # Should be low
        assert score < 0.5

    def test_calculate_confidence_with_cfn_tag(self) -> None:
        """Test confidence calculation with CloudFormation tag."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        resource = CloudResource(
            resource_id="arn:aws:s3:::my-bucket",
            resource_type=CloudResourceType.S3_BUCKET,
            provider=CloudProvider.AWS,
            name="my-bucket",
            tags={
                "aws:cloudformation:logical-id": "MyBucket",
                "aws:cloudformation:stack-name": "my-stack",
            },
        )

        confidence = correlator._calculate_confidence(iac, resource)
        # Should be high with both tag matches
        assert confidence > 0.7


class TestIaCCorrelatorFindBestMatch:
    """Tests for finding best match."""

    def test_find_best_match_single_candidate(self) -> None:
        """Test finding match with single candidate."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        candidates = [
            CloudResource(
                resource_id="arn:aws:s3:::my-bucket",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="my-bucket",
                tags={"aws:cloudformation:logical-id": "MyBucket"},
            )
        ]

        match = correlator._find_best_match(iac, candidates)
        assert match is not None
        assert match.name == "my-bucket"

    def test_find_best_match_multiple_candidates(self) -> None:
        """Test finding best match among multiple candidates."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        candidates = [
            CloudResource(
                resource_id="arn:aws:s3:::other-bucket",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="other-bucket",
            ),
            CloudResource(
                resource_id="arn:aws:s3:::my-bucket",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="my-bucket",
                tags={"aws:cloudformation:logical-id": "MyBucket"},
            ),
        ]

        match = correlator._find_best_match(iac, candidates)
        assert match is not None
        # Should find the one with the CFN tag
        assert match.tags.get("aws:cloudformation:logical-id") == "MyBucket"

    def test_find_best_match_no_candidates(self) -> None:
        """Test finding match with no candidates."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="MyBucket",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )

        match = correlator._find_best_match(iac, [])
        assert match is None

    def test_find_best_match_low_confidence(self) -> None:
        """Test no match returned for low confidence."""
        correlator = IaCCorrelator()

        iac = IaCResource(
            logical_id="VerySpecificName",
            resource_type="AWS::S3::Bucket",
            source_file="template.yaml",
        )
        candidates = [
            CloudResource(
                resource_id="arn:aws:s3:::completely-different",
                resource_type=CloudResourceType.S3_BUCKET,
                provider=CloudProvider.AWS,
                name="completely-different",
            )
        ]

        match = correlator._find_best_match(iac, candidates)
        # No match because confidence below threshold
        assert match is None


class TestIaCCorrelatorLineNumbers:
    """Tests for line number detection."""

    def test_find_line_number_found(self) -> None:
        """Test finding line number in content."""
        correlator = IaCCorrelator()
        content = """line1
line2
MyBucket:
  Type: AWS::S3::Bucket
"""
        line = correlator._find_line_number(content, "MyBucket")
        assert line == 3

    def test_find_line_number_not_found(self) -> None:
        """Test line number not found returns 0."""
        correlator = IaCCorrelator()
        content = "no match here"
        line = correlator._find_line_number(content, "MyBucket")
        assert line == 0
