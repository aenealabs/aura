"""Lambda handler for Constitutional AI audit queue consumer.

Reads audit entries from SQS and persists to DynamoDB for compliance
reporting as specified in ADR-063 Phase 3.

DynamoDB Table Schema:
- pk: AUDIT#{agent_name}
- sk: {timestamp}
- GSI: agent-timestamp-index (agent_name, timestamp)

This enables efficient queries by agent and time range for:
- Agent-specific audit history
- Time-range compliance reports
- Aggregate metrics computation
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_dynamodb_resource
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource

logger = logging.getLogger()
logger.setLevel(logging.INFO)

AUDIT_TABLE = os.environ.get("AUDIT_TABLE_NAME", "aura-constitutional-audit-dev")


def get_audit_table():
    """Get DynamoDB audit table (lazy initialization)."""
    return get_dynamodb_resource().Table(AUDIT_TABLE)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Process SQS batch of Constitutional AI audit entries.

    Args:
        event: SQS event containing Records array
        context: Lambda context

    Returns:
        Response dict with status and counts

    Event structure:
        {
            "Records": [
                {
                    "messageId": "...",
                    "body": "{...audit entry JSON...}",
                    ...
                }
            ]
        }
    """
    table = get_audit_table()

    processed = 0
    errors = 0
    records = event.get("Records", [])

    logger.info(f"Processing {len(records)} audit records")

    for record in records:
        try:
            # Parse audit entry from SQS message body
            body = json.loads(record["body"])

            # Build DynamoDB item with partition and sort keys
            item = build_dynamodb_item(body)

            # Write to DynamoDB
            table.put_item(Item=item)
            processed += 1

            logger.debug(
                f"Persisted audit: {body.get('agent_name')}/{body.get('operation_type')}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in audit record: {e}")
            errors += 1

        except Exception as e:
            logger.error(f"Failed to process audit record: {e}")
            errors += 1

    logger.info(f"Processed {processed} audit entries, {errors} errors")

    return {
        "statusCode": 200,
        "body": json.dumps(
            {
                "processed": processed,
                "errors": errors,
                "total_records": len(records),
            }
        ),
    }


def build_dynamodb_item(audit_entry: Dict[str, Any]) -> Dict[str, Any]:
    """Build DynamoDB item from audit entry.

    Creates a DynamoDB item with:
    - pk: Partition key for agent-based access pattern
    - sk: Sort key (timestamp) for time-range queries
    - All audit entry fields preserved

    Args:
        audit_entry: Audit entry dictionary from SQS

    Returns:
        DynamoDB item dictionary
    """
    agent_name = audit_entry.get("agent_name", "unknown")
    timestamp = audit_entry.get("timestamp", datetime.now(timezone.utc).isoformat())

    # Build item with keys and all audit data
    item = {
        "pk": f"AUDIT#{agent_name}",
        "sk": timestamp,
        "agent_name": agent_name,
        "timestamp": timestamp,
        "operation_type": audit_entry.get("operation_type", "unknown"),
        "output_hash": audit_entry.get("output_hash", ""),
        "critique_performed": audit_entry.get("critique_performed", True),
        "critique_summary": audit_entry.get("critique_summary", {}),
        "revision_performed": audit_entry.get("revision_performed", False),
        "revision_iterations": audit_entry.get("revision_iterations", 0),
        "blocked": audit_entry.get("blocked", False),
        "block_reason": audit_entry.get("block_reason"),
        "hitl_required": audit_entry.get("hitl_required", False),
        "hitl_request_id": audit_entry.get("hitl_request_id"),
        "processing_time_ms": audit_entry.get("processing_time_ms", 0.0),
        "autonomy_level": audit_entry.get("autonomy_level", "COLLABORATIVE"),
        "critique_tier": audit_entry.get("critique_tier", "STANDARD"),
        "principles_evaluated": audit_entry.get("principles_evaluated", 0),
        "issues_found": audit_entry.get("issues_found", {}),
        "cache_hit": audit_entry.get("cache_hit", False),
        "fast_path_blocked": audit_entry.get("fast_path_blocked", False),
        "metadata": audit_entry.get("metadata", {}),
        # Add processing metadata
        "ingestion_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Remove None values (DynamoDB doesn't accept None)
    return {k: v for k, v in item.items() if v is not None}


def query_audits_by_agent(
    agent_name: str,
    start_time: str,
    end_time: str,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """Query audit entries for a specific agent in a time range.

    Utility function for compliance reporting (not used by Lambda handler).

    Args:
        agent_name: Name of the agent to query
        start_time: ISO format start timestamp
        end_time: ISO format end timestamp
        limit: Maximum number of records to return

    Returns:
        List of audit entry dictionaries
    """
    table = get_audit_table()

    response = table.query(
        KeyConditionExpression="pk = :pk AND sk BETWEEN :start AND :end",
        ExpressionAttributeValues={
            ":pk": f"AUDIT#{agent_name}",
            ":start": start_time,
            ":end": end_time,
        },
        Limit=limit,
        ScanIndexForward=False,  # Newest first
    )

    return response.get("Items", [])


def get_audit_summary(agent_name: str, hours: int = 24) -> Dict[str, Any]:
    """Get summary statistics for an agent's recent audits.

    Utility function for monitoring dashboards.

    Args:
        agent_name: Name of the agent
        hours: Number of hours to look back

    Returns:
        Summary dictionary with counts and metrics
    """
    from datetime import timedelta

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours)

    audits = query_audits_by_agent(
        agent_name=agent_name,
        start_time=start_time.isoformat(),
        end_time=end_time.isoformat(),
        limit=1000,
    )

    # Compute summary statistics in single pass
    total = len(audits)
    blocked_count = 0
    revised_count = 0
    cache_hits = 0
    hitl_count = 0
    processing_times = []
    issues = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    for a in audits:
        if a.get("blocked", False):
            blocked_count += 1
        if a.get("revision_performed", False):
            revised_count += 1
        if a.get("cache_hit", False):
            cache_hits += 1
        if a.get("hitl_required", False):
            hitl_count += 1
        pt = a.get("processing_time_ms")
        if pt:
            processing_times.append(pt)
        found = a.get("issues_found", {})
        for severity in issues:
            issues[severity] += found.get(severity, 0)

    avg_processing_time = (
        sum(processing_times) / len(processing_times) if processing_times else 0
    )

    return {
        "agent_name": agent_name,
        "period_hours": hours,
        "total_audits": total,
        "blocked_count": blocked_count,
        "blocked_rate": blocked_count / total if total > 0 else 0,
        "revised_count": revised_count,
        "revision_rate": revised_count / total if total > 0 else 0,
        "cache_hit_count": cache_hits,
        "cache_hit_rate": cache_hits / total if total > 0 else 0,
        "hitl_count": hitl_count,
        "hitl_rate": hitl_count / total if total > 0 else 0,
        "avg_processing_time_ms": avg_processing_time,
        "issues_by_severity": issues,
    }
