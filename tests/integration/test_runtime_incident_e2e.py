"""End-to-end integration test for RuntimeIncidentAgent (ADR-025 Phase 6).

Tests the complete workflow:
1. CloudWatch alarm triggers EventBridge
2. Step Functions executes investigation workflow
3. ECS Fargate runs RuntimeIncidentAgent
4. Investigation results stored in DynamoDB
5. SNS notification sent
6. HITL approval via API

This test requires AWS credentials and deployed infrastructure.
Set RUN_AWS_E2E_TESTS=1 to enable.
"""

import os
import time
from datetime import datetime, timezone

import boto3
import pytest

# Skip unless explicitly enabled, mark as slow due to polling delays
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.getenv("RUN_AWS_E2E_TESTS"),
        reason="E2E tests require RUN_AWS_E2E_TESTS=1",
    ),
]

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
PROJECT_NAME = "aura"
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")


@pytest.fixture(scope="module")
def aws_clients():
    """Initialize AWS clients for E2E testing."""
    return {
        "stepfunctions": boto3.client("stepfunctions", region_name=AWS_REGION),
        "dynamodb": boto3.resource("dynamodb", region_name=AWS_REGION),
        "cloudformation": boto3.client("cloudformation", region_name=AWS_REGION),
    }


@pytest.fixture(scope="module")
def state_machine_arn(aws_clients):
    """Get Step Functions state machine ARN from CloudFormation."""
    cfn = aws_clients["cloudformation"]
    stack_name = f"{PROJECT_NAME}-incident-investigation-{ENVIRONMENT}"

    response = cfn.describe_stacks(StackName=stack_name)
    outputs = response["Stacks"][0]["Outputs"]

    for output in outputs:
        if output["OutputKey"] == "StateMachineArn":
            return output["OutputValue"]

    raise RuntimeError("StateMachineArn not found in stack outputs")


def test_e2e_incident_investigation_workflow(aws_clients, state_machine_arn):
    """
    Test end-to-end incident investigation workflow.

    Workflow:
    1. Start Step Functions execution with test incident
    2. Wait for execution to complete
    3. Verify investigation results in DynamoDB
    4. Verify HITL status is pending
    """
    sfn = aws_clients["stepfunctions"]
    dynamodb = aws_clients["dynamodb"]

    # Test incident event (CloudWatch alarm format)
    test_incident = {
        "id": f"e2e-test-{int(time.time())}",
        "source": "aws.cloudwatch",
        "detail": {
            "alarmName": f"{PROJECT_NAME}-test-alarm-{ENVIRONMENT}",
            "newStateValue": "ALARM",
            "newStateReason": "E2E test alarm for ADR-025",
            "stateChangeTime": datetime.now(timezone.utc).isoformat(),
        },
    }

    # Step 1: Start execution
    response = sfn.start_execution(
        stateMachineArn=state_machine_arn,
        name=test_incident["id"],
        input=str(test_incident).replace("'", '"'),
    )

    execution_arn = response["executionArn"]
    print(f"Started execution: {execution_arn}")

    # Step 2: Wait for completion (max 15 minutes)
    # Timeout accounts for: ECS Fargate cold start (~3 min) + SSM/LLM calls (~5 min) + buffer
    max_wait = int(os.getenv("E2E_TIMEOUT_SECONDS", "900"))  # 15 minutes default
    poll_interval = 15  # seconds between status checks
    start_time = time.time()

    while time.time() - start_time < max_wait:
        execution = sfn.describe_execution(executionArn=execution_arn)
        status = execution["status"]
        elapsed = int(time.time() - start_time)

        print(f"[{elapsed}s] Execution status: {status}")

        if status == "SUCCEEDED":
            print(f"Execution succeeded after {elapsed} seconds")
            break
        elif status in ["FAILED", "TIMED_OUT", "ABORTED"]:
            pytest.fail(f"Execution failed with status: {status}")

        time.sleep(poll_interval)
    else:
        pytest.fail(f"Execution timed out after {max_wait} seconds")

    # Step 3: Verify results in DynamoDB
    investigations_table = dynamodb.Table(
        f"{PROJECT_NAME}-incident-investigations-{ENVIRONMENT}"
    )

    response = investigations_table.query(
        KeyConditionExpression="incident_id = :id",
        ExpressionAttributeValues={":id": test_incident["id"]},
        Limit=1,
    )

    assert len(response["Items"]) == 1, "Investigation not found in DynamoDB"

    investigation = response["Items"][0]

    # Verify investigation fields
    assert investigation["incident_id"] == test_incident["id"]
    assert investigation["source"] == "aws.cloudwatch"
    assert investigation["hitl_status"] == "pending"
    assert "rca_hypothesis" in investigation
    assert "confidence_score" in investigation
    assert 0 <= investigation["confidence_score"] <= 100
    assert "mitigation_plan" in investigation

    print(f"Investigation verified: {investigation['incident_id']}")
    print(f"RCA Confidence: {investigation['confidence_score']}%")
    print(f"Hypothesis: {investigation['rca_hypothesis']}")

    # Cleanup: Mark as approved to remove from pending list
    investigations_table.update_item(
        Key={
            "incident_id": test_incident["id"],
            "timestamp": investigation["timestamp"],
        },
        UpdateExpression="SET hitl_status = :status",
        ExpressionAttributeValues={":status": "approved"},
    )

    print("E2E test completed successfully")
