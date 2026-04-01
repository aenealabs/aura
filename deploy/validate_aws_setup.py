#!/usr/bin/env python3
"""
AWS Infrastructure Validation Script for Project Aura
Validates that all required AWS resources are properly configured.
"""

import json
import sys
from typing import Dict, List, Tuple

# Check if boto3 is available
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    print("⚠️  Warning: boto3 not installed. Install with: pip install boto3")
    print()

# ANSI color codes for pretty output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(text: str):
    """Print a formatted header."""
    print(f"\n{BLUE}{'=' * 60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'=' * 60}{RESET}\n")


def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓{RESET} {text}")


def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗{RESET} {text}")


def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠{RESET} {text}")


def print_info(text: str):
    """Print info message."""
    print(f"{BLUE}ℹ{RESET} {text}")


def check_aws_credentials() -> Tuple[bool, str]:
    """Check if AWS credentials are configured."""
    try:
        sts = boto3.client("sts", region_name="us-east-1")
        identity = sts.get_caller_identity()
        account_id = identity["Account"]
        user_arn = identity["Arn"]
        return True, f"Account: {account_id}, ARN: {user_arn}"
    except NoCredentialsError:
        return False, "No AWS credentials found. Run: aws configure"
    except ClientError as e:
        return False, f"Error: {e}"


def check_bedrock_access() -> Tuple[bool, List[str]]:
    """Check if Bedrock is accessible and models are available."""
    try:
        bedrock = boto3.client("bedrock", region_name="us-east-1")
        response = bedrock.list_foundation_models()

        claude_models = [
            model["modelId"]
            for model in response["modelSummaries"]
            if "claude" in model["modelId"].lower()
        ]

        required_models = [
            "anthropic.claude-3-5-sonnet-20241022-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
        ]

        available = [m for m in required_models if m in claude_models]

        if len(available) == len(required_models):
            return True, available
        else:
            return False, available

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            return False, ["Access denied - request model access in Bedrock console"]
        return False, [f"Error: {error_code}"]


def check_iam_role(role_name: str = "AuraBedrockServiceRole") -> Tuple[bool, str]:
    """Check if IAM role exists and has correct policies."""
    try:
        iam = boto3.client("iam", region_name="us-east-1")

        # Check if role exists
        try:
            role = iam.get_role(RoleName=role_name)
            role_arn = role["Role"]["Arn"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchEntity":
                return False, f"Role '{role_name}' not found"
            raise

        # Check attached policies
        attached_policies = iam.list_attached_role_policies(RoleName=role_name)
        policy_count = len(attached_policies["AttachedPolicies"])

        # Check inline policies
        inline_policies = iam.list_role_policies(RoleName=role_name)
        inline_count = len(inline_policies["PolicyNames"])

        total_policies = policy_count + inline_count

        if total_policies == 0:
            return False, f"Role exists but has no policies attached"

        return True, f"Role ARN: {role_arn}, Policies: {total_policies}"

    except ClientError as e:
        return False, f"Error: {e}"


def check_dynamodb_table(table_name: str = "aura-llm-costs") -> Tuple[bool, str]:
    """Check if DynamoDB table exists with correct indexes."""
    try:
        dynamodb = boto3.client("dynamodb", region_name="us-east-1")

        response = dynamodb.describe_table(TableName=table_name)
        table = response["Table"]

        status = table["TableStatus"]
        billing = table.get("BillingModeSummary", {}).get("BillingMode", "N/A")

        # Check for indexes
        indexes = table.get("GlobalSecondaryIndexes", [])
        index_names = [idx["IndexName"] for idx in indexes]

        required_indexes = ["date-index", "month-index"]
        missing_indexes = [idx for idx in required_indexes if idx not in index_names]

        if status != "ACTIVE":
            return False, f"Table status: {status} (not ACTIVE)"

        if missing_indexes:
            return False, f"Missing indexes: {', '.join(missing_indexes)}"

        return True, f"Status: {status}, Billing: {billing}, Indexes: {len(indexes)}"

    except ClientError as e:
        if e.response["Error"]["Code"] == "ResourceNotFoundException":
            return False, f"Table '{table_name}' not found"
        return False, f"Error: {e}"


def check_secrets_manager(secret_prefix: str = "aura/") -> Tuple[bool, List[str]]:
    """Check if secrets exist in Secrets Manager."""
    try:
        sm = boto3.client("secretsmanager", region_name="us-east-1")

        response = sm.list_secrets()
        aura_secrets = [
            secret["Name"]
            for secret in response["SecretList"]
            if secret["Name"].startswith(secret_prefix)
        ]

        if not aura_secrets:
            return False, ["No secrets found with prefix 'aura/'"]

        return True, aura_secrets

    except ClientError as e:
        return False, [f"Error: {e}"]


def check_sns_topic(topic_substring: str = "aura-budget-alerts") -> Tuple[bool, str]:
    """Check if SNS topic exists."""
    try:
        sns = boto3.client("sns", region_name="us-east-1")

        response = sns.list_topics()
        aura_topics = [
            topic["TopicArn"]
            for topic in response["Topics"]
            if topic_substring in topic["TopicArn"]
        ]

        if not aura_topics:
            return False, f"No topic found containing '{topic_substring}'"

        topic_arn = aura_topics[0]

        # Check subscriptions
        subs = sns.list_subscriptions_by_topic(TopicArn=topic_arn)
        sub_count = len(subs["Subscriptions"])
        confirmed = sum(
            1
            for s in subs["Subscriptions"]
            if s["SubscriptionArn"] != "PendingConfirmation"
        )

        return (
            True,
            f"ARN: {topic_arn}, Subscriptions: {confirmed}/{sub_count} confirmed",
        )

    except ClientError as e:
        return False, f"Error: {e}"


def check_cloudwatch_alarms(alarm_prefix: str = "aura-") -> Tuple[bool, List[str]]:
    """Check if CloudWatch alarms exist."""
    try:
        cw = boto3.client("cloudwatch", region_name="us-east-1")

        response = cw.describe_alarms(AlarmNamePrefix=alarm_prefix)
        alarm_names = [alarm["AlarmName"] for alarm in response["MetricAlarms"]]

        if not alarm_names:
            return False, ["No alarms found with prefix 'aura-'"]

        return True, alarm_names

    except ClientError as e:
        return False, [f"Error: {e}"]


def test_bedrock_invocation() -> Tuple[bool, str]:
    """Test actual Bedrock API invocation."""
    try:
        bedrock_runtime = boto3.client("bedrock-runtime", region_name="us-east-1")

        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 20,
            "messages": [
                {"role": "user", "content": "Say 'test successful' and nothing else."}
            ],
        }

        response = bedrock_runtime.invoke_model(
            modelId="anthropic.claude-3-haiku-20240307-v1:0",
            body=json.dumps(request_body),
        )

        response_body = json.loads(response["body"].read())
        text = response_body["content"][0]["text"]
        tokens = (
            response_body["usage"]["input_tokens"]
            + response_body["usage"]["output_tokens"]
        )

        return True, f"Response received ({tokens} tokens): {text[:50]}"

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "AccessDeniedException":
            return False, "Access denied - check IAM permissions"
        elif error_code == "ResourceNotFoundException":
            return False, "Model not found - request access in console"
        return False, f"Error: {error_code}"


def main():
    """Run all validation checks."""
    print_header("Project Aura - AWS Infrastructure Validation")

    if not AWS_AVAILABLE:
        print_error("boto3 not installed. Cannot perform validation.")
        print_info("Install with: pip install -r requirements.txt")
        sys.exit(1)

    results = {}

    # Check 1: AWS Credentials
    print("1. Checking AWS credentials...")
    success, message = check_aws_credentials()
    results["credentials"] = success
    if success:
        print_success(message)
    else:
        print_error(message)

    if not success:
        print("\n" + "=" * 60)
        print_error("AWS credentials not configured. Cannot proceed with other checks.")
        print_info("Run: aws configure")
        sys.exit(1)

    # Check 2: Bedrock Access
    print("\n2. Checking Bedrock model access...")
    success, models = check_bedrock_access()
    results["bedrock"] = success
    if success:
        print_success(f"Bedrock access granted")
        for model in models:
            print(f"  • {model}")
    else:
        print_error("Bedrock access issue")
        for msg in models:
            print(f"  • {msg}")

    # Check 3: IAM Role
    print("\n3. Checking IAM service role...")
    success, message = check_iam_role()
    results["iam_role"] = success
    if success:
        print_success(message)
    else:
        print_error(message)

    # Check 4: DynamoDB Table
    print("\n4. Checking DynamoDB cost tracking table...")
    success, message = check_dynamodb_table()
    results["dynamodb"] = success
    if success:
        print_success(message)
    else:
        print_error(message)

    # Check 5: Secrets Manager
    print("\n5. Checking Secrets Manager configuration...")
    success, secrets = check_secrets_manager()
    results["secrets"] = success
    if success:
        print_success(f"Found {len(secrets)} secret(s)")
        for secret in secrets:
            print(f"  • {secret}")
    else:
        print_warning("No secrets found (optional)")
        for msg in secrets:
            print(f"  • {msg}")

    # Check 6: SNS Topic
    print("\n6. Checking SNS budget alerts topic...")
    success, message = check_sns_topic()
    results["sns"] = success
    if success:
        print_success(message)
    else:
        print_error(message)

    # Check 7: CloudWatch Alarms
    print("\n7. Checking CloudWatch budget alarms...")
    success, alarms = check_cloudwatch_alarms()
    results["cloudwatch"] = success
    if success:
        print_success(f"Found {len(alarms)} alarm(s)")
        for alarm in alarms:
            print(f"  • {alarm}")
    else:
        print_warning("No alarms found (optional)")
        for msg in alarms:
            print(f"  • {msg}")

    # Check 8: Test Bedrock API
    print("\n8. Testing Bedrock API invocation...")
    success, message = test_bedrock_invocation()
    results["bedrock_test"] = success
    if success:
        print_success(message)
    else:
        print_error(message)

    # Summary
    print_header("Validation Summary")

    total_checks = len(results)
    passed_checks = sum(1 for v in results.values() if v)
    failed_checks = total_checks - passed_checks

    print(f"Total checks: {total_checks}")
    print(f"{GREEN}Passed: {passed_checks}{RESET}")
    print(f"{RED}Failed: {failed_checks}{RESET}")
    print()

    # Critical vs optional
    critical_checks = ["credentials", "bedrock", "iam_role", "dynamodb"]
    critical_passed = sum(1 for k in critical_checks if results.get(k, False))

    print(f"Critical infrastructure: {critical_passed}/{len(critical_checks)} ready")
    print()

    if critical_passed == len(critical_checks):
        print_success("✓ All critical infrastructure is ready!")
        print_info("You can now use Bedrock LLM service in AWS mode")
        print()
        print("Next steps:")
        print("  1. Test the service: python3 src/services/bedrock_llm_service.py")
        print("  2. Run tests: python3 -m pytest tests/test_bedrock_service.py -v")
        print(
            "  3. Integrate with orchestrator: see docs/BEDROCK_INTEGRATION_README.md"
        )
        return 0
    else:
        print_error("✗ Some critical infrastructure is missing")
        print()
        print("Required steps:")
        if not results.get("bedrock"):
            print("  • Enable Bedrock: https://console.aws.amazon.com/bedrock/")
        if not results.get("iam_role"):
            print("  • Create IAM role: See deploy/AWS_SETUP_GUIDE.md Phase 3")
        if not results.get("dynamodb"):
            print("  • Create DynamoDB table: See deploy/AWS_SETUP_GUIDE.md Phase 4")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\nValidation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n{RED}Unexpected error: {e}{RESET}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
