"""Golden set management and regression detection service for Constitutional AI Phase 4.

This module provides functionality for managing the regression golden set,
running regression checks, and detecting quality regressions as specified
in ADR-063 Phase 4.

Key features:
- Load/save golden set cases from DynamoDB/S3
- Run current critique against golden set baseline
- Detect regressions (false negatives, false positives, severity changes)
- Generate regression reports with severity classification
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.services.constitutional_ai.evaluation_models import (
    ExpectedCritique,
    GoldenSetCase,
    RegressionItem,
    RegressionReport,
    RegressionSeverity,
)
from src.services.constitutional_ai.models import (
    ConstitutionalContext,
    ConstitutionalEvaluationSummary,
    CritiqueResult,
)

if TYPE_CHECKING:
    from src.services.constitutional_ai.critique_service import (
        ConstitutionalCritiqueService,
    )

logger = logging.getLogger(__name__)


class GoldenSetMode(Enum):
    """Operating modes for golden set service."""

    MOCK = "mock"  # In-memory storage for testing
    AWS = "aws"  # Real DynamoDB/S3 storage


@dataclass
class GoldenSetServiceConfig:
    """Configuration for golden set service."""

    mode: GoldenSetMode = GoldenSetMode.MOCK
    dynamodb_table_name: Optional[str] = None
    s3_bucket_name: Optional[str] = None
    s3_prefix: str = "golden_set/"
    baseline_version: str = "v1.0.0"
    regression_threshold: float = 0.05  # 5% regression threshold for alerts


@dataclass
class BaselineMetrics:
    """Baseline metrics for regression comparison."""

    version: str
    pass_rate: float
    principle_pass_rates: Dict[str, float]
    total_cases: int
    cases_by_category: Dict[str, int]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "version": self.version,
            "pass_rate": self.pass_rate,
            "principle_pass_rates": self.principle_pass_rates,
            "total_cases": self.total_cases,
            "cases_by_category": self.cases_by_category,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaselineMetrics":
        """Create from dictionary."""
        created_at = data.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now(timezone.utc)

        return cls(
            version=data["version"],
            pass_rate=data["pass_rate"],
            principle_pass_rates=data.get("principle_pass_rates", {}),
            total_cases=data["total_cases"],
            cases_by_category=data.get("cases_by_category", {}),
            created_at=created_at,
        )


class GoldenSetService:
    """Service for managing golden set and detecting regressions.

    The golden set is a collection of verified test cases that ensure
    the critique service maintains consistent behavior over time.
    """

    def __init__(
        self,
        config: Optional[GoldenSetServiceConfig] = None,
    ):
        """Initialize the golden set service.

        Args:
            config: Service configuration
        """
        self.config = config or GoldenSetServiceConfig()

        # In-memory storage for MOCK mode
        self._golden_cases: Dict[str, GoldenSetCase] = {}
        self._baseline: Optional[BaselineMetrics] = None

        # AWS clients (lazy initialized)
        self._dynamodb_client = None
        self._s3_client = None

    async def load_golden_set(self) -> List[GoldenSetCase]:
        """Load all golden set cases.

        Returns:
            List of GoldenSetCase objects
        """
        if self.config.mode == GoldenSetMode.MOCK:
            return list(self._golden_cases.values())
        else:
            return await self._load_from_dynamodb()

    async def save_golden_case(self, case: GoldenSetCase) -> None:
        """Save a golden set case.

        Args:
            case: The case to save
        """
        if self.config.mode == GoldenSetMode.MOCK:
            self._golden_cases[case.case_id] = case
        else:
            await self._save_to_dynamodb(case)

    async def delete_golden_case(self, case_id: str) -> bool:
        """Delete a golden set case.

        Args:
            case_id: ID of the case to delete

        Returns:
            True if deleted, False if not found
        """
        if self.config.mode == GoldenSetMode.MOCK:
            if case_id in self._golden_cases:
                del self._golden_cases[case_id]
                return True
            return False
        else:
            return await self._delete_from_dynamodb(case_id)

    async def load_baseline(self) -> Optional[BaselineMetrics]:
        """Load the current baseline metrics.

        Returns:
            BaselineMetrics or None if no baseline exists
        """
        if self.config.mode == GoldenSetMode.MOCK:
            return self._baseline
        else:
            return await self._load_baseline_from_s3()

    async def save_baseline(self, baseline: BaselineMetrics) -> None:
        """Save baseline metrics.

        Args:
            baseline: The baseline metrics to save
        """
        if self.config.mode == GoldenSetMode.MOCK:
            self._baseline = baseline
        else:
            await self._save_baseline_to_s3(baseline)

    async def run_regression_check(
        self,
        critique_service: "ConstitutionalCritiqueService",
        cases: Optional[List[GoldenSetCase]] = None,
    ) -> RegressionReport:
        """Run regression check against golden set.

        Args:
            critique_service: The critique service to test
            cases: Optional specific cases to test (default: all golden cases)

        Returns:
            RegressionReport with detected regressions
        """
        start_time = time.perf_counter()
        run_id = str(uuid.uuid4())[:8]

        if cases is None:
            cases = await self.load_golden_set()

        if not cases:
            return RegressionReport(
                run_id=run_id,
                total_cases=0,
                passed_cases=0,
                failed_cases=0,
                regressions=[],
                pass_rate=1.0,
            )

        regressions: List[RegressionItem] = []
        passed_count = 0

        for case in cases:
            case_regressions = await self._check_case_regression(case, critique_service)
            if case_regressions:
                regressions.extend(case_regressions)
            else:
                passed_count += 1

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        pass_rate = passed_count / len(cases) if cases else 1.0
        critical_count = sum(
            1 for r in regressions if r.severity == RegressionSeverity.CRITICAL
        )

        return RegressionReport(
            run_id=run_id,
            total_cases=len(cases),
            passed_cases=passed_count,
            failed_cases=len(cases) - passed_count,
            regressions=regressions,
            pass_rate=pass_rate,
            critical_regressions=critical_count,
            run_duration_ms=elapsed_ms,
        )

    async def _check_case_regression(
        self,
        case: GoldenSetCase,
        critique_service: "ConstitutionalCritiqueService",
    ) -> List[RegressionItem]:
        """Check a single golden set case for regressions.

        Args:
            case: The golden set case
            critique_service: The critique service to test

        Returns:
            List of RegressionItem objects (empty if no regression)
        """
        regressions: List[RegressionItem] = []

        # Build context from case
        context = ConstitutionalContext(
            agent_name="golden_set_test",
            operation_type="regression_check",
            user_request=case.input_prompt,
            domain_tags=case.tags,
        )

        # Run critique
        try:
            summary = await critique_service.critique_output(
                agent_output=case.agent_output,
                context=context,
                applicable_principles=case.principle_ids,
            )
        except Exception as e:
            logger.error(f"Critique failed for case {case.case_id}: {e}")
            return [
                RegressionItem(
                    case_id=case.case_id,
                    principle_id="*",
                    regression_type="critique_failure",
                    expected="Successful critique",
                    actual=f"Critique failed: {e}",
                    severity=RegressionSeverity.CRITICAL,
                    details={"error": str(e)},
                )
            ]

        # Compare results against expectations
        regressions.extend(self._compare_results(case, summary))

        return regressions

    def _compare_results(
        self,
        case: GoldenSetCase,
        summary: ConstitutionalEvaluationSummary,
    ) -> List[RegressionItem]:
        """Compare critique results against expected results.

        Args:
            case: The golden set case with expectations
            summary: The actual critique summary

        Returns:
            List of detected regressions
        """
        regressions: List[RegressionItem] = []

        # Build lookup of actual results by principle ID
        actual_by_principle: Dict[str, CritiqueResult] = {
            c.principle_id: c for c in summary.critiques
        }

        for expected in case.expected_critiques:
            actual = actual_by_principle.get(expected.principle_id)

            if actual is None:
                # Principle was not evaluated (unexpected)
                regressions.append(
                    RegressionItem(
                        case_id=case.case_id,
                        principle_id=expected.principle_id,
                        regression_type="missing_evaluation",
                        expected="Principle should be evaluated",
                        actual="Principle was not evaluated",
                        severity=self._get_regression_severity(
                            expected.severity_if_flagged
                        ),
                    )
                )
                continue

            # Check for false negative (expected flag but didn't flag)
            if expected.should_flag and not actual.requires_revision:
                regressions.append(
                    RegressionItem(
                        case_id=case.case_id,
                        principle_id=expected.principle_id,
                        regression_type="false_negative",
                        expected=f"Should flag: {expected.expected_issues}",
                        actual="Did not flag any issues",
                        severity=self._get_regression_severity(
                            expected.severity_if_flagged
                        ),
                        details={
                            "expected_issues": expected.expected_issues,
                            "actual_issues": actual.issues_found,
                        },
                    )
                )

            # Check for false positive (didn't expect flag but flagged)
            elif not expected.should_flag and actual.requires_revision:
                regressions.append(
                    RegressionItem(
                        case_id=case.case_id,
                        principle_id=expected.principle_id,
                        regression_type="false_positive",
                        expected="Should not flag any issues",
                        actual=f"Flagged: {actual.issues_found}",
                        severity=RegressionSeverity.MEDIUM,  # False positives are less severe
                        details={
                            "unexpected_issues": actual.issues_found,
                            "reasoning": actual.reasoning,
                        },
                    )
                )

            # Check for missing expected issues (partial false negative)
            elif expected.should_flag and actual.requires_revision:
                missing_issues = self._find_missing_issues(
                    expected.expected_issues, actual.issues_found
                )
                if missing_issues:
                    regressions.append(
                        RegressionItem(
                            case_id=case.case_id,
                            principle_id=expected.principle_id,
                            regression_type="partial_false_negative",
                            expected=f"Expected issues: {expected.expected_issues}",
                            actual=f"Found issues: {actual.issues_found}",
                            severity=RegressionSeverity.LOW,
                            details={
                                "missing_issues": missing_issues,
                                "found_issues": actual.issues_found,
                            },
                        )
                    )

        # Check overall revision requirement
        if case.expected_revision_needed != summary.requires_revision:
            regressions.append(
                RegressionItem(
                    case_id=case.case_id,
                    principle_id="*",
                    regression_type="revision_mismatch",
                    expected=f"Revision needed: {case.expected_revision_needed}",
                    actual=f"Revision needed: {summary.requires_revision}",
                    severity=(
                        RegressionSeverity.HIGH
                        if case.expected_revision_needed
                        else RegressionSeverity.MEDIUM
                    ),
                )
            )

        return regressions

    def _find_missing_issues(
        self,
        expected_issues: List[str],
        actual_issues: List[str],
    ) -> List[str]:
        """Find expected issues that weren't detected.

        Uses partial string matching to account for minor wording differences.

        Args:
            expected_issues: List of expected issue descriptions
            actual_issues: List of actually detected issues

        Returns:
            List of expected issues that weren't found
        """
        missing = []
        actual_lower = [i.lower() for i in actual_issues]

        for expected in expected_issues:
            expected_lower = expected.lower()
            # Check if any actual issue contains key terms from expected
            found = any(
                self._issues_match(expected_lower, actual) for actual in actual_lower
            )
            if not found:
                missing.append(expected)

        return missing

    def _issues_match(self, expected: str, actual: str) -> bool:
        """Check if an actual issue matches an expected issue.

        Uses keyword matching for flexibility.

        Args:
            expected: Expected issue text (lowercase)
            actual: Actual issue text (lowercase)

        Returns:
            True if issues match
        """
        # Extract key terms (words > 3 chars)
        expected_terms = {
            word for word in expected.split() if len(word) > 3 and word.isalpha()
        }

        # Check if majority of expected terms appear in actual
        if not expected_terms:
            return expected in actual

        matches = sum(1 for term in expected_terms if term in actual)
        return matches / len(expected_terms) >= 0.5

    def _get_regression_severity(
        self,
        principle_severity: Optional[str],
    ) -> RegressionSeverity:
        """Map principle severity to regression severity.

        Args:
            principle_severity: The principle's severity level

        Returns:
            Corresponding RegressionSeverity
        """
        if principle_severity is None:
            return RegressionSeverity.MEDIUM

        severity_map = {
            "critical": RegressionSeverity.CRITICAL,
            "high": RegressionSeverity.HIGH,
            "medium": RegressionSeverity.MEDIUM,
            "low": RegressionSeverity.LOW,
        }
        return severity_map.get(principle_severity.lower(), RegressionSeverity.MEDIUM)

    def detect_regressions(
        self,
        current_results: List[CritiqueResult],
        expected: List[ExpectedCritique],
    ) -> List[RegressionItem]:
        """Compare current critique results with expected results.

        Standalone method for direct regression detection without
        running the full critique service.

        Args:
            current_results: Actual critique results
            expected: Expected critique results

        Returns:
            List of detected regressions
        """
        # This is a simplified version of _compare_results
        # for use when you already have critique results
        regressions: List[RegressionItem] = []

        actual_by_principle = {c.principle_id: c for c in current_results}

        for exp in expected:
            actual = actual_by_principle.get(exp.principle_id)

            if actual is None:
                regressions.append(
                    RegressionItem(
                        case_id="standalone",
                        principle_id=exp.principle_id,
                        regression_type="missing_evaluation",
                        expected="Evaluated",
                        actual="Not evaluated",
                        severity=self._get_regression_severity(exp.severity_if_flagged),
                    )
                )
            elif exp.should_flag and not actual.requires_revision:
                regressions.append(
                    RegressionItem(
                        case_id="standalone",
                        principle_id=exp.principle_id,
                        regression_type="false_negative",
                        expected="Flagged",
                        actual="Not flagged",
                        severity=self._get_regression_severity(exp.severity_if_flagged),
                    )
                )
            elif not exp.should_flag and actual.requires_revision:
                regressions.append(
                    RegressionItem(
                        case_id="standalone",
                        principle_id=exp.principle_id,
                        regression_type="false_positive",
                        expected="Not flagged",
                        actual="Flagged",
                        severity=RegressionSeverity.MEDIUM,
                    )
                )

        return regressions

    async def update_baseline(
        self,
        report: RegressionReport,
        version: Optional[str] = None,
    ) -> BaselineMetrics:
        """Update baseline metrics from a regression report.

        Should only be called after human review confirms the new
        behavior is correct.

        Args:
            report: The regression report to base metrics on
            version: Optional version string (default: auto-increment)

        Returns:
            The new baseline metrics
        """
        current_baseline = await self.load_baseline()

        if version is None:
            if current_baseline:
                # Auto-increment version
                parts = current_baseline.version.lstrip("v").split(".")
                parts[-1] = str(int(parts[-1]) + 1)
                version = "v" + ".".join(parts)
            else:
                version = "v1.0.0"

        # Compute principle-level pass rates
        cases = await self.load_golden_set()
        principle_pass_rates: Dict[str, float] = {}

        if cases:
            # Group cases by principle
            principle_cases: Dict[str, int] = {}
            for case in cases:
                for ec in case.expected_critiques:
                    principle_cases[ec.principle_id] = (
                        principle_cases.get(ec.principle_id, 0) + 1
                    )

            # Count failures by principle
            principle_failures: Dict[str, int] = {}
            for reg in report.regressions:
                if reg.principle_id != "*":
                    principle_failures[reg.principle_id] = (
                        principle_failures.get(reg.principle_id, 0) + 1
                    )

            for pid, total in principle_cases.items():
                failures = principle_failures.get(pid, 0)
                principle_pass_rates[pid] = (total - failures) / total

        # Compute category distribution
        cases_by_category: Dict[str, int] = {}
        for case in cases:
            cat = case.category.value
            cases_by_category[cat] = cases_by_category.get(cat, 0) + 1

        baseline = BaselineMetrics(
            version=version,
            pass_rate=report.pass_rate,
            principle_pass_rates=principle_pass_rates,
            total_cases=report.total_cases,
            cases_by_category=cases_by_category,
        )

        await self.save_baseline(baseline)
        return baseline

    def get_failing_cases(
        self,
        report: RegressionReport,
    ) -> List[str]:
        """Get IDs of cases that failed regression testing.

        Args:
            report: The regression report

        Returns:
            List of case IDs with regressions
        """
        return list({r.case_id for r in report.regressions if r.case_id != "*"})

    # AWS Storage Methods (for AWS mode)

    async def _load_from_dynamodb(self) -> List[GoldenSetCase]:
        """Load golden cases from DynamoDB."""
        if self._dynamodb_client is None:
            import boto3

            self._dynamodb_client = boto3.client("dynamodb")

        table_name = self.config.dynamodb_table_name
        if not table_name:
            raise ValueError("DynamoDB table name not configured")

        cases = []
        try:
            paginator = self._dynamodb_client.get_paginator("scan")
            for page in paginator.paginate(
                TableName=table_name,
                FilterExpression="begins_with(pk, :prefix)",
                ExpressionAttributeValues={":prefix": {"S": "GOLDEN_CASE#"}},
            ):
                for item in page.get("Items", []):
                    case_data = json.loads(item["data"]["S"])
                    cases.append(GoldenSetCase.from_dict(case_data))
        except Exception as e:
            logger.error(f"Failed to load from DynamoDB: {e}")
            raise

        return cases

    async def _save_to_dynamodb(self, case: GoldenSetCase) -> None:
        """Save a golden case to DynamoDB."""
        if self._dynamodb_client is None:
            import boto3

            self._dynamodb_client = boto3.client("dynamodb")

        table_name = self.config.dynamodb_table_name
        if not table_name:
            raise ValueError("DynamoDB table name not configured")

        try:
            self._dynamodb_client.put_item(
                TableName=table_name,
                Item={
                    "pk": {"S": f"GOLDEN_CASE#{case.case_id}"},
                    "sk": {"S": f"CATEGORY#{case.category.value}"},
                    "data": {"S": json.dumps(case.to_dict())},
                    "category": {"S": case.category.value},
                    "created_at": {"S": case.human_verified_at.isoformat()},
                },
            )
        except Exception as e:
            logger.error(f"Failed to save to DynamoDB: {e}")
            raise

    async def _delete_from_dynamodb(self, case_id: str) -> bool:
        """Delete a golden case from DynamoDB."""
        if self._dynamodb_client is None:
            import boto3

            self._dynamodb_client = boto3.client("dynamodb")

        table_name = self.config.dynamodb_table_name
        if not table_name:
            raise ValueError("DynamoDB table name not configured")

        try:
            # Need to find the case first to get the sort key
            response = self._dynamodb_client.query(
                TableName=table_name,
                KeyConditionExpression="pk = :pk",
                ExpressionAttributeValues={":pk": {"S": f"GOLDEN_CASE#{case_id}"}},
            )
            items = response.get("Items", [])
            if not items:
                return False

            # Delete the item
            self._dynamodb_client.delete_item(
                TableName=table_name,
                Key={
                    "pk": items[0]["pk"],
                    "sk": items[0]["sk"],
                },
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete from DynamoDB: {e}")
            return False

    async def _load_baseline_from_s3(self) -> Optional[BaselineMetrics]:
        """Load baseline metrics from S3."""
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client("s3")

        bucket = self.config.s3_bucket_name
        if not bucket:
            raise ValueError("S3 bucket name not configured")

        key = f"{self.config.s3_prefix}baseline.json"

        try:
            response = self._s3_client.get_object(Bucket=bucket, Key=key)
            data = json.loads(response["Body"].read().decode("utf-8"))
            return BaselineMetrics.from_dict(data)
        except self._s3_client.exceptions.NoSuchKey:
            return None
        except Exception as e:
            logger.error(f"Failed to load baseline from S3: {e}")
            return None

    async def _save_baseline_to_s3(self, baseline: BaselineMetrics) -> None:
        """Save baseline metrics to S3."""
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client("s3")

        bucket = self.config.s3_bucket_name
        if not bucket:
            raise ValueError("S3 bucket name not configured")

        key = f"{self.config.s3_prefix}baseline.json"

        try:
            self._s3_client.put_object(
                Bucket=bucket,
                Key=key,
                Body=json.dumps(baseline.to_dict(), indent=2),
                ContentType="application/json",
            )
        except Exception as e:
            logger.error(f"Failed to save baseline to S3: {e}")
            raise


# Factory function
def create_golden_set_service(
    mode: str = "mock",
    dynamodb_table_name: Optional[str] = None,
    s3_bucket_name: Optional[str] = None,
) -> GoldenSetService:
    """Create a GoldenSetService with specified mode.

    Args:
        mode: "mock" or "aws"
        dynamodb_table_name: DynamoDB table name (for AWS mode)
        s3_bucket_name: S3 bucket name (for AWS mode)

    Returns:
        Configured GoldenSetService
    """
    config = GoldenSetServiceConfig(
        mode=GoldenSetMode.MOCK if mode == "mock" else GoldenSetMode.AWS,
        dynamodb_table_name=dynamodb_table_name,
        s3_bucket_name=s3_bucket_name,
    )
    return GoldenSetService(config=config)
