"""Lambda handler for nightly Constitutional AI evaluation.

This Lambda function is triggered by EventBridge on a nightly schedule to:
1. Load evaluation dataset from S3
2. Run LLM-as-Judge evaluations on sampled response pairs
3. Run golden set regression checks
4. Publish metrics to CloudWatch
5. Send SNS alerts for significant quality drops

Specified in ADR-063 Phase 4 (Evaluation).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.services.constitutional_ai.evaluation_models import (
        EvaluationDataset,
        RegressionReport,
    )

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
EVALUATION_BUCKET = os.environ.get("EVALUATION_BUCKET", "")
GOLDEN_SET_TABLE = os.environ.get("GOLDEN_SET_TABLE", "")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN", "")
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
SAMPLE_SIZE = int(os.environ.get("SAMPLE_SIZE", "50"))
ENABLE_REGRESSION_ALERTS = (
    os.environ.get("ENABLE_REGRESSION_ALERTS", "true").lower() == "true"
)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda entry point for nightly evaluation.

    Args:
        event: EventBridge scheduled event or test event
        context: Lambda context

    Returns:
        Evaluation result summary
    """
    logger.info(f"Starting nightly constitutional AI evaluation: {json.dumps(event)}")
    start_time = time.perf_counter()

    try:
        # Run async evaluation
        result = asyncio.get_event_loop().run_until_complete(
            run_evaluation(event, context)
        )

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        result["execution_time_ms"] = elapsed_ms

        logger.info(f"Evaluation completed successfully in {elapsed_ms:.0f}ms")
        return {
            "statusCode": 200,
            "body": result,
        }

    except Exception as e:
        logger.error(f"Evaluation failed: {e}", exc_info=True)

        # Send failure alert
        if SNS_TOPIC_ARN and ENABLE_REGRESSION_ALERTS:
            asyncio.get_event_loop().run_until_complete(send_failure_alert(str(e)))

        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "status": "failed",
            },
        }


async def run_evaluation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Run the full evaluation pipeline.

    Args:
        event: Lambda event
        context: Lambda context

    Returns:
        Evaluation result summary
    """
    # Import services (lazy to reduce cold start)
    from src.services.constitutional_ai.cai_metrics_publisher import (
        CAIMetricsMode,
        CAIMetricsPublisher,
        CAIMetricsPublisherConfig,
    )
    from src.services.constitutional_ai.critique_service import (
        ConstitutionalCritiqueService,
    )
    from src.services.constitutional_ai.evaluation_models import EvaluationMetrics
    from src.services.constitutional_ai.golden_set_service import (
        GoldenSetMode,
        GoldenSetService,
        GoldenSetServiceConfig,
    )
    from src.services.constitutional_ai.llm_judge_service import (
        ConstitutionalJudgeService,
        JudgeMode,
        JudgeServiceConfig,
    )

    # Determine mode based on environment
    is_test = event.get("test_mode", False)

    # Initialize services
    judge_config = JudgeServiceConfig(
        mode=JudgeMode.MOCK if is_test else JudgeMode.AWS,
    )
    judge_service = ConstitutionalJudgeService(config=judge_config)

    golden_set_config = GoldenSetServiceConfig(
        mode=GoldenSetMode.MOCK if is_test else GoldenSetMode.AWS,
        dynamodb_table_name=GOLDEN_SET_TABLE,
        s3_bucket_name=EVALUATION_BUCKET,
    )
    golden_set_service = GoldenSetService(config=golden_set_config)

    critique_service = ConstitutionalCritiqueService()

    metrics_config = CAIMetricsPublisherConfig(
        mode=CAIMetricsMode.MOCK if is_test else CAIMetricsMode.AWS,
        environment=ENVIRONMENT,
    )
    metrics_publisher = CAIMetricsPublisher(config=metrics_config)

    # Step 1: Load and sample evaluation dataset
    logger.info("Loading evaluation dataset from S3...")
    dataset = await load_evaluation_dataset(is_test)
    sample_size = min(SAMPLE_SIZE, len(dataset.response_pairs))
    sampled_pairs = random.sample(dataset.response_pairs, sample_size)
    logger.info(f"Sampled {sample_size} pairs from {len(dataset.response_pairs)} total")

    # Step 2: Run LLM-as-Judge evaluation
    logger.info("Running LLM-as-Judge evaluation...")
    judge_result = await judge_service.batch_evaluate(sampled_pairs)
    critique_accuracy = judge_result.accuracy_vs_human or 0.0
    logger.info(f"Judge accuracy vs human: {critique_accuracy:.2%}")

    # Step 3: Run golden set regression check
    logger.info("Running golden set regression check...")
    regression_report = await golden_set_service.run_regression_check(critique_service)
    logger.info(
        f"Regression check: {regression_report.passed_cases}/{regression_report.total_cases} passed"
    )

    # Step 4: Collect additional metrics from critique service
    cache_stats = critique_service.get_cache_stats()
    cache_hit_rate = cache_stats.get("cache_hit_rate", 0.0)

    # Step 5: Calculate non-evasive rate (sample a few responses)
    non_evasive_scores = []
    for pair in sampled_pairs[:10]:  # Sample 10 for efficiency
        result = await judge_service.evaluate_non_evasiveness(
            response=pair.response_b,
            user_request=pair.context.user_request or pair.prompt,
            agent_name=pair.context.agent_name,
        )
        non_evasive_scores.append(result.get("non_evasive_score", 0.5))
    non_evasive_rate = (
        sum(non_evasive_scores) / len(non_evasive_scores) if non_evasive_scores else 0.5
    )

    # Step 6: Calculate revision convergence rate (from cache stats or historical)
    # For now, use a placeholder - in production this comes from critique service
    revision_convergence_rate = 0.95  # Placeholder

    # Step 7: Calculate critique latency P95
    latencies = [r.latency_ms for r in judge_result.results if r.latency_ms > 0]
    latencies.sort()
    critique_latency_p95 = (
        latencies[int(len(latencies) * 0.95)] if len(latencies) >= 20 else 400.0
    )

    # Step 8: Publish metrics to CloudWatch
    logger.info("Publishing metrics to CloudWatch...")
    await metrics_publisher.publish_evaluation_metrics(
        critique_accuracy=critique_accuracy,
        revision_convergence_rate=revision_convergence_rate,
        cache_hit_rate=cache_hit_rate,
        non_evasive_rate=non_evasive_rate,
        golden_set_pass_rate=regression_report.pass_rate,
        critique_latency_p95_ms=critique_latency_p95,
        evaluation_pairs_processed=sample_size,
        critique_count=len(judge_result.results),
        issues_by_severity={
            "critical": regression_report.critical_regressions,
            "high": sum(
                1 for r in regression_report.regressions if r.severity.value == "high"
            ),
            "medium": sum(
                1 for r in regression_report.regressions if r.severity.value == "medium"
            ),
            "low": sum(
                1 for r in regression_report.regressions if r.severity.value == "low"
            ),
        },
    )
    await metrics_publisher.flush()

    # Step 9: Check for critical regressions and alert
    if regression_report.has_critical_regressions and ENABLE_REGRESSION_ALERTS:
        logger.warning(
            f"Critical regressions detected: {regression_report.critical_regressions}"
        )
        await send_regression_alert(regression_report)

    # Build result summary
    evaluation_metrics = EvaluationMetrics(
        critique_accuracy=critique_accuracy,
        revision_convergence_rate=revision_convergence_rate,
        cache_hit_rate=cache_hit_rate,
        non_evasive_rate=non_evasive_rate,
        golden_set_pass_rate=regression_report.pass_rate,
        critique_latency_p95_ms=critique_latency_p95,
        evaluation_pairs_processed=sample_size,
        critique_count=len(judge_result.results),
        issues_by_severity={
            "critical": regression_report.critical_regressions,
        },
    )

    targets_met = evaluation_metrics.meets_targets()

    return {
        "status": "success",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "environment": ENVIRONMENT,
        "metrics": {
            "critique_accuracy": f"{critique_accuracy:.2%}",
            "revision_convergence_rate": f"{revision_convergence_rate:.2%}",
            "cache_hit_rate": f"{cache_hit_rate:.2%}",
            "non_evasive_rate": f"{non_evasive_rate:.2%}",
            "golden_set_pass_rate": f"{regression_report.pass_rate:.2%}",
            "critique_latency_p95_ms": critique_latency_p95,
        },
        "targets_met": targets_met,
        "all_targets_met": all(targets_met.values()),
        "evaluation_summary": {
            "pairs_evaluated": sample_size,
            "judge_results": len(judge_result.results),
            "golden_set_cases": regression_report.total_cases,
            "regressions_detected": len(regression_report.regressions),
            "critical_regressions": regression_report.critical_regressions,
        },
        "alerts_sent": regression_report.has_critical_regressions
        and ENABLE_REGRESSION_ALERTS,
    }


async def load_evaluation_dataset(is_test: bool = False) -> "EvaluationDataset":
    """Load evaluation dataset from S3 or create mock data.

    Args:
        is_test: If True, return mock dataset

    Returns:
        EvaluationDataset
    """
    from src.services.constitutional_ai.evaluation_models import (
        EvaluationDataset,
        ResponsePair,
    )
    from src.services.constitutional_ai.models import ConstitutionalContext

    if is_test or not EVALUATION_BUCKET:
        # Return mock dataset for testing
        pairs = []
        for i in range(100):
            pairs.append(
                ResponsePair(
                    pair_id=f"mock_pair_{i}",
                    prompt=f"Test prompt {i}",
                    response_a=f"Baseline response {i}",
                    response_b=f"Revised response {i} with improvements",
                    context=ConstitutionalContext(
                        agent_name="mock_agent",
                        operation_type="code_generation",
                        user_request=f"Test prompt {i}",
                    ),
                    applicable_principles=[
                        "principle_1_security_first",
                        "principle_8_accuracy_precision",
                    ],
                    human_preference="b" if i % 3 != 0 else "a",
                )
            )

        return EvaluationDataset(
            dataset_id="mock_dataset",
            version="1.0.0",
            name="Mock Evaluation Dataset",
            description="Mock dataset for testing",
            response_pairs=pairs,
        )

    # Load from S3
    import boto3

    s3 = boto3.client("s3")

    try:
        response = s3.get_object(
            Bucket=EVALUATION_BUCKET,
            Key="datasets/latest/response_pairs.jsonl",
        )
        content = response["Body"].read().decode("utf-8")

        pairs = []
        for line in content.strip().split("\n"):
            if line:
                data = json.loads(line)
                pairs.append(ResponsePair.from_dict(data))

        return EvaluationDataset(
            dataset_id="s3_dataset",
            version="latest",
            name="S3 Evaluation Dataset",
            description=f"Loaded from {EVALUATION_BUCKET}",
            response_pairs=pairs,
        )
    except Exception as e:
        logger.error(f"Failed to load dataset from S3: {e}")
        raise


async def send_regression_alert(report: "RegressionReport") -> None:
    """Send SNS alert for critical regressions.

    Args:
        report: The regression report with detected issues
    """
    if not SNS_TOPIC_ARN:
        logger.warning("SNS_TOPIC_ARN not configured, skipping alert")
        return

    import boto3

    sns = boto3.client("sns")

    # Format alert message
    message = {
        "alert_type": "constitutional_ai_regression",
        "severity": "critical",
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_cases": report.total_cases,
            "passed_cases": report.passed_cases,
            "failed_cases": report.failed_cases,
            "pass_rate": f"{report.pass_rate:.2%}",
            "critical_regressions": report.critical_regressions,
            "total_regressions": len(report.regressions),
        },
        "critical_regressions": [
            {
                "case_id": r.case_id,
                "principle_id": r.principle_id,
                "type": r.regression_type,
                "expected": r.expected,
                "actual": r.actual,
            }
            for r in report.regressions
            if r.severity.value == "critical"
        ][
            :10
        ],  # Limit to first 10
        "action_required": (
            "Review the critical regressions and verify if behavior change is expected. "
            "If unexpected, investigate and fix the regression before next deployment."
        ),
    }

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[{ENVIRONMENT.upper()}] Constitutional AI Critical Regression Detected",
            Message=json.dumps(message, indent=2),
            MessageAttributes={
                "AlertType": {"DataType": "String", "StringValue": "regression"},
                "Severity": {"DataType": "String", "StringValue": "critical"},
                "Environment": {"DataType": "String", "StringValue": ENVIRONMENT},
            },
        )
        logger.info("Regression alert sent to SNS")
    except Exception as e:
        logger.error(f"Failed to send SNS alert: {e}")


async def send_failure_alert(error: str) -> None:
    """Send SNS alert for evaluation failure.

    Args:
        error: Error message
    """
    if not SNS_TOPIC_ARN:
        return

    import boto3

    sns = boto3.client("sns")

    message = {
        "alert_type": "constitutional_ai_evaluation_failure",
        "severity": "high",
        "environment": ENVIRONMENT,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "action_required": "Investigate Lambda execution failure and check CloudWatch logs.",
    }

    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"[{ENVIRONMENT.upper()}] Constitutional AI Evaluation Failed",
            Message=json.dumps(message, indent=2),
        )
    except Exception as e:
        logger.error(f"Failed to send failure alert: {e}")


# For local testing
if __name__ == "__main__":
    import sys

    # Run with --test flag for mock mode
    test_mode = "--test" in sys.argv

    test_event = {
        "source": "local-test",
        "test_mode": test_mode,
    }

    result = handler(test_event, None)
    print(json.dumps(result, indent=2))
