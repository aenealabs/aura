"""
Aura Chat Handler Lambda

Main Lambda function for processing chat messages through Bedrock Claude.
Supports REST API requests for chat/message and conversation management.

Features:
- Intelligent 3-tier model routing (FAST/ACCURATE/MAXIMUM)
- Multi-provider model support (Anthropic, OpenAI, Google via Bedrock)
- Tool use with agentic loop
- Conversation persistence in DynamoDB
"""

import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from botocore.exceptions import ClientError

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_bedrock_runtime_client, get_dynamodb_resource
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_bedrock_runtime_client = _aws_clients.get_bedrock_runtime_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource

# =============================================================================
# Model Routing Configuration (ADR-028 Compliant)
# =============================================================================


class ModelTier(Enum):
    """Model selection tiers based on task complexity."""

    FAST = "fast"  # Simple queries, classifications
    ACCURATE = "accurate"  # Code analysis, diagram generation
    MAXIMUM = "maximum"  # Deep research, complex reasoning


@dataclass
class ModelSpec:
    """Specification for an LLM model."""

    model_id: str
    provider: str
    tier: ModelTier
    max_tokens: int
    cost_per_1k_input: float
    cost_per_1k_output: float
    capabilities: list[str]


# Model catalog - extensible for multi-provider support
# Using inference profile IDs for cross-region routing
MODEL_CATALOG: dict[str, ModelSpec] = {
    # Anthropic via Bedrock (using inference profiles for on-demand)
    "claude-3-haiku": ModelSpec(
        model_id="us.anthropic.claude-3-haiku-20240307-v1:0",
        provider="anthropic",
        tier=ModelTier.FAST,
        max_tokens=4096,
        cost_per_1k_input=0.00025,
        cost_per_1k_output=0.00125,
        capabilities=["classification", "simple_qa", "formatting"],
    ),
    "claude-3-5-sonnet": ModelSpec(
        model_id="us.anthropic.claude-3-5-sonnet-20240620-v1:0",
        provider="anthropic",
        tier=ModelTier.ACCURATE,
        max_tokens=4096,
        cost_per_1k_input=0.003,
        cost_per_1k_output=0.015,
        capabilities=[
            "code_analysis",
            "diagram_generation",
            "security_review",
            "tool_use",
        ],
    ),
    "claude-3-5-opus": ModelSpec(
        model_id="us.anthropic.claude-3-opus-20240229-v1:0",
        provider="anthropic",
        tier=ModelTier.MAXIMUM,
        max_tokens=4096,
        cost_per_1k_input=0.015,
        cost_per_1k_output=0.075,
        capabilities=[
            "deep_research",
            "cross_codebase",
            "complex_reasoning",
            "architecture",
        ],
    ),
}


# Query classification patterns for automatic routing (pre-compiled for performance)
FAST_PATTERNS = [
    re.compile(r"^(hello|hi|hey|thanks|thank you|bye|goodbye)\b", re.IGNORECASE),
    re.compile(r"^what (time|date|day) is it", re.IGNORECASE),
    re.compile(r"^help$", re.IGNORECASE),
    re.compile(r"^status$", re.IGNORECASE),
    re.compile(r"^(yes|no|ok|okay|sure)\b", re.IGNORECASE),
]

MAXIMUM_PATTERNS = [
    re.compile(r"deep (research|analysis|dive)", re.IGNORECASE),
    re.compile(r"cross[- ]codebase", re.IGNORECASE),
    re.compile(r"comprehensive (review|analysis|audit)", re.IGNORECASE),
    re.compile(r"architecture (review|design|proposal)", re.IGNORECASE),
    re.compile(r"security audit", re.IGNORECASE),
    re.compile(r"threat model", re.IGNORECASE),
    re.compile(r"compare.*across.*repositories", re.IGNORECASE),
]

ACCURATE_PATTERNS = [
    re.compile(
        r"(generate|create|draw).*(diagram|flowchart|sequence|class|er)", re.IGNORECASE
    ),
    re.compile(r"code (review|analysis)", re.IGNORECASE),
    re.compile(r"explain.*(function|class|module|code)", re.IGNORECASE),
    re.compile(r"vulnerability", re.IGNORECASE),
    re.compile(r"(find|search).*(bug|issue|error)", re.IGNORECASE),
]

try:
    from tools import CHAT_TOOLS, execute_tool
except ImportError:
    from .tools import CHAT_TOOLS, execute_tool

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
CONVERSATIONS_TABLE = os.environ.get(
    "CONVERSATIONS_TABLE", f"{PROJECT_NAME}-chat-conversations-{ENVIRONMENT}"
)
MESSAGES_TABLE = os.environ.get(
    "MESSAGES_TABLE", f"{PROJECT_NAME}-chat-messages-{ENVIRONMENT}"
)
# 3-tier model configuration
HAIKU_MODEL_ID = os.environ.get(
    "HAIKU_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0"
)
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "anthropic.claude-3-5-sonnet-20241022-v2:0"
)
OPUS_MODEL_ID = os.environ.get("OPUS_MODEL_ID", "anthropic.claude-3-opus-20240229-v1:0")
CONVERSATION_TTL_DAYS = int(os.environ.get("CONVERSATION_TTL_DAYS", "30"))
RATE_LIMIT_PER_MINUTE = int(os.environ.get("RATE_LIMIT_PER_MINUTE", "30"))

# Map tiers to environment-configured model IDs
TIER_TO_MODEL: dict[ModelTier, str] = {
    ModelTier.FAST: HAIKU_MODEL_ID,
    ModelTier.ACCURATE: BEDROCK_MODEL_ID,
    ModelTier.MAXIMUM: OPUS_MODEL_ID,
}


# Lazy table accessors (Issue #466)
def get_conversations_table():
    """Get DynamoDB conversations table (lazy initialization)."""
    return get_dynamodb_resource().Table(CONVERSATIONS_TABLE)


def get_messages_table():
    """Get DynamoDB messages table (lazy initialization)."""
    return get_dynamodb_resource().Table(MESSAGES_TABLE)


# System prompt for the chat assistant
SYSTEM_PROMPT = """You are Aura Assistant, the AI-powered support assistant for the Project Aura security platform.

Your capabilities:
1. Answer questions about platform features, configurations, and best practices
2. Query real-time vulnerability metrics and agent status using tools
3. Search platform documentation, ADRs, and guides
4. Generate ad-hoc reports on vulnerabilities, incidents, and patches
5. Help users understand GraphRAG code relationships
6. Provide HITL approval queue insights

Guidelines:
- Be concise and helpful. Security engineers are busy.
- Use tools to fetch real-time data when asked about metrics, status, or incidents.
- For documentation questions, use the search_documentation tool.
- If you're unsure about something, say so rather than guessing.
- Format responses with markdown for readability.
- Always maintain tenant isolation - only access data for the user's tenant.

Available tools:
- get_vulnerability_metrics: Query vulnerability statistics
- get_agent_status: Check agent health and activity
- get_approval_queue: View pending HITL approvals
- search_documentation: Search docs, ADRs, and guides
- get_incident_details: Get incident investigation data
- generate_report: Create ad-hoc summary reports
- query_code_graph: Query GraphRAG code relationships
- get_sandbox_status: Check sandbox environment status

Current environment: {environment}
"""


def handler(event: dict, context: Any) -> dict:
    """
    Main Lambda handler for chat requests.

    Supports:
    - POST /chat/message - Send a chat message
    - GET /chat/conversations - List user conversations
    - GET /chat/conversations/{id} - Get conversation with messages
    - DELETE /chat/conversations/{id} - Delete a conversation
    """
    logger.info(f"Received event: {json.dumps(event)}")

    try:
        # Extract HTTP method and path
        http_method = event.get("httpMethod", "POST")
        path = event.get("path", "/chat/message")
        path_params = event.get("pathParameters") or {}

        # Extract user info from Cognito authorizer
        user_info = extract_user_info(event)
        if not user_info:
            return error_response(401, "Unauthorized")

        # Route request
        if http_method == "POST" and path.endswith("/message"):
            return handle_chat_message(event, user_info)
        elif http_method == "GET" and "conversationId" in path_params:
            return handle_get_conversation(path_params["conversationId"], user_info)
        elif http_method == "GET" and path.endswith("/conversations"):
            return handle_list_conversations(event, user_info)
        elif http_method == "DELETE" and "conversationId" in path_params:
            return handle_delete_conversation(path_params["conversationId"], user_info)
        else:
            return error_response(404, "Not found")

    except Exception as e:
        logger.exception(f"Error processing request: {e}")
        return error_response(500, "Internal server error")


def extract_user_info(event: dict) -> dict | None:
    """Extract user information from Cognito authorizer claims."""
    try:
        claims = event.get("requestContext", {}).get("authorizer", {}).get("claims", {})

        if not claims:
            # No Cognito claims - authentication required
            # Dev auth bypass removed for security (see GitHub issue #37)
            return None

        return {
            "user_id": claims.get("sub"),
            "tenant_id": claims.get("custom:tenant_id", claims.get("sub")),
            "email": claims.get("email"),
            "groups": claims.get("cognito:groups", "").split(","),
        }
    except Exception as e:
        logger.error(f"Error extracting user info: {e}")
        return None


def handle_chat_message(event: dict, user_info: dict) -> dict:
    """Process a chat message and return AI response."""
    try:
        body = json.loads(event.get("body", "{}"))
        message_text = body.get("message", "").strip()
        conversation_id = body.get("conversation_id")

        if not message_text:
            return error_response(400, "Message is required")

        if len(message_text) > 10000:
            return error_response(400, "Message too long (max 10,000 characters)")

        # Get or create conversation
        if conversation_id:
            conversation = get_conversation(conversation_id, user_info["user_id"])
            if not conversation:
                return error_response(404, "Conversation not found")
        else:
            conversation_id = str(uuid.uuid4())
            conversation = create_new_conversation(conversation_id, user_info)

        # Get conversation history for context
        history = get_conversation_history(conversation_id, limit=10)

        # Save user message
        _user_message_id = save_message(  # noqa: F841
            conversation_id=conversation_id,
            role="user",
            content=message_text,
            tenant_id=user_info["tenant_id"],
        )

        # Call Bedrock with tools
        response = call_bedrock_with_tools(
            message=message_text,
            history=history,
            user_info=user_info,
        )

        # Save assistant response
        assistant_message_id = save_message(
            conversation_id=conversation_id,
            role="assistant",
            content=response["content"],
            tenant_id=user_info["tenant_id"],
            tool_calls=response.get("tool_calls"),
            tokens_input=response.get("tokens_input", 0),
            tokens_output=response.get("tokens_output", 0),
            model_id=response.get("model_id", BEDROCK_MODEL_ID),
            latency_ms=response.get("latency_ms", 0),
        )

        # Update conversation metadata
        update_conversation_metadata(
            conversation_id=conversation_id,
            user_id=user_info["user_id"],
            message_text=message_text,
            tokens_used=response.get("tokens_input", 0)
            + response.get("tokens_output", 0),
        )

        return success_response(
            {
                "conversation_id": conversation_id,
                "message_id": assistant_message_id,
                "content": response["content"],
                "tool_calls": response.get("tool_calls"),
                "model_id": response.get("model_id", BEDROCK_MODEL_ID),
            }
        )

    except json.JSONDecodeError:
        return error_response(400, "Invalid JSON body")
    except Exception as e:
        logger.exception(f"Error handling chat message: {e}")
        return error_response(500, "Failed to process message")


def call_bedrock_with_tools(
    message: str,
    history: list[dict],
    user_info: dict,
) -> dict:
    """
    Call Bedrock Claude with tool use support.

    Implements the agentic loop: LLM -> Tool -> LLM -> Response
    """
    import time

    start_time = time.time()

    # Build messages list
    messages = []

    # Add conversation history
    for msg in history:
        messages.append(
            {
                "role": msg["role"],
                "content": [{"text": msg["content"]}],
            }
        )

    # Add current message
    messages.append(
        {
            "role": "user",
            "content": [{"text": message}],
        }
    )

    # Prepare tool definitions for Bedrock
    tool_definitions = [
        {
            "toolSpec": {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": {
                    "json": tool["parameters"],
                },
            }
        }
        for tool in CHAT_TOOLS
    ]

    # Determine model (use Haiku for simple queries)
    model_id = select_model(message)

    total_input_tokens = 0
    total_output_tokens = 0
    tool_calls = []

    # Agentic loop - allow up to 5 tool calls
    max_iterations = 5
    for _iteration in range(max_iterations):
        try:
            response = get_bedrock_runtime_client().converse(
                modelId=model_id,
                system=[{"text": SYSTEM_PROMPT.format(environment=ENVIRONMENT)}],
                messages=messages,
                toolConfig={
                    "tools": tool_definitions,
                },
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.3,
                },
            )

            # Track token usage
            usage = response.get("usage", {})
            total_input_tokens += usage.get("inputTokens", 0)
            total_output_tokens += usage.get("outputTokens", 0)

            # Check stop reason
            stop_reason = response.get("stopReason", "end_turn")
            output = response.get("output", {})
            message_content = output.get("message", {}).get("content", [])

            if stop_reason == "tool_use":
                # Process tool calls
                tool_results = []
                for block in message_content:
                    if block.get("toolUse"):
                        tool_use = block["toolUse"]
                        tool_name = tool_use["name"]
                        tool_input = tool_use["input"]
                        tool_id = tool_use["toolUseId"]

                        logger.info(
                            f"Executing tool: {tool_name} with input: {tool_input}"
                        )

                        # Execute the tool
                        try:
                            result = execute_tool(tool_name, tool_input, user_info)
                            tool_calls.append(
                                {
                                    "name": tool_name,
                                    "input": tool_input,
                                    "output": result,
                                }
                            )
                            tool_results.append(
                                {
                                    "toolResult": {
                                        "toolUseId": tool_id,
                                        "content": [{"text": json.dumps(result)}],
                                    }
                                }
                            )
                        except Exception as e:
                            logger.error(f"Tool execution error: {e}")
                            tool_results.append(
                                {
                                    "toolResult": {
                                        "toolUseId": tool_id,
                                        "content": [{"text": f"Error: {str(e)}"}],
                                        "status": "error",
                                    }
                                }
                            )

                # Add assistant message with tool use
                messages.append(
                    {
                        "role": "assistant",
                        "content": message_content,
                    }
                )

                # Add tool results
                messages.append(
                    {
                        "role": "user",
                        "content": tool_results,
                    }
                )

            else:
                # Final response - extract text content
                final_text = ""
                for block in message_content:
                    if block.get("text"):
                        final_text += block["text"]

                latency_ms = int((time.time() - start_time) * 1000)

                return {
                    "content": final_text,
                    "tool_calls": tool_calls if tool_calls else None,
                    "tokens_input": total_input_tokens,
                    "tokens_output": total_output_tokens,
                    "model_id": model_id,
                    "latency_ms": latency_ms,
                }

        except ClientError as e:
            logger.error(f"Bedrock API error: {e}")
            raise

    # If we exhaust iterations, return partial response
    return {
        "content": "I apologize, but I couldn't complete your request. Please try a simpler query.",
        "tool_calls": tool_calls if tool_calls else None,
        "tokens_input": total_input_tokens,
        "tokens_output": total_output_tokens,
        "model_id": model_id,
        "latency_ms": int((time.time() - start_time) * 1000),
    }


def classify_query_tier(message: str) -> ModelTier:
    """
    Classify a query into the appropriate model tier using pattern matching.

    Routing Strategy (ADR-028):
    - FAST (Haiku): Simple queries, greetings, status checks
    - ACCURATE (Sonnet): Code analysis, diagrams, tool use
    - MAXIMUM (Opus): Deep research, cross-codebase analysis

    Returns:
        ModelTier: The recommended tier for the query
    """
    message_lower = message.lower().strip()

    # Check for MAXIMUM tier patterns first (most specific)
    for pattern in MAXIMUM_PATTERNS:
        if pattern.search(message_lower):
            logger.info(f"Query matched MAXIMUM pattern: {pattern.pattern}")
            return ModelTier.MAXIMUM

    # Check for FAST tier patterns (simple queries)
    for pattern in FAST_PATTERNS:
        if pattern.search(message_lower):
            # Additional check: FAST only for short messages
            if len(message) < 100:
                logger.info(f"Query matched FAST pattern: {pattern.pattern}")
                return ModelTier.FAST

    # Check for ACCURATE tier patterns
    for pattern in ACCURATE_PATTERNS:
        if pattern.search(message_lower):
            logger.info(f"Query matched ACCURATE pattern: {pattern.pattern}")
            return ModelTier.ACCURATE

    # Default to ACCURATE for medium-complexity queries
    # (This is the safest default for most chat interactions)
    logger.info("Query did not match specific patterns, defaulting to ACCURATE tier")
    return ModelTier.ACCURATE


def select_model(message: str, requested_tier: ModelTier | None = None) -> str:
    """
    Select the appropriate Bedrock model ID based on query complexity.

    Args:
        message: The user's message to analyze
        requested_tier: Optional explicit tier override

    Returns:
        str: The Bedrock model ID to use
    """
    # Allow explicit tier override
    if requested_tier:
        model_id = TIER_TO_MODEL.get(requested_tier, BEDROCK_MODEL_ID)
        logger.info(
            f"Using explicitly requested tier {requested_tier.value}: {model_id}"
        )
        return model_id

    # Classify the query automatically
    tier = classify_query_tier(message)
    model_id = TIER_TO_MODEL.get(tier, BEDROCK_MODEL_ID)

    logger.info(f"Auto-selected model tier {tier.value}: {model_id}")
    return model_id


def get_model_spec(model_id: str) -> ModelSpec | None:
    """
    Get the ModelSpec for a given model ID.

    Args:
        model_id: The Bedrock model ID

    Returns:
        ModelSpec if found, None otherwise
    """
    for spec in MODEL_CATALOG.values():
        if spec.model_id == model_id:
            return spec
    return None


def get_conversation(conversation_id: str, user_id: str) -> dict | None:
    """Get a conversation, verifying user ownership."""
    try:
        response = get_conversations_table().get_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"CONV#{conversation_id}",
            }
        )
        return response.get("Item")
    except Exception as e:
        logger.error(f"Error getting conversation: {e}")
        return None


def create_new_conversation(conversation_id: str, user_info: dict) -> dict:
    """Create a new conversation in DynamoDB."""
    now = datetime.now(timezone.utc).isoformat()
    ttl = int(
        (datetime.now(timezone.utc) + timedelta(days=CONVERSATION_TTL_DAYS)).timestamp()
    )

    item = {
        "PK": f"USER#{user_info['user_id']}",
        "SK": f"CONV#{conversation_id}",
        "conversation_id": conversation_id,
        "user_id": user_info["user_id"],
        "tenant_id": user_info["tenant_id"],
        "title": "New Conversation",
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
        "total_tokens": 0,
        "status": "active",
        "ttl": ttl,
    }

    get_conversations_table().put_item(Item=item)
    return item


def get_conversation_history(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get recent messages from a conversation."""
    try:
        response = get_messages_table().query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={
                ":pk": f"CONV#{conversation_id}",
            },
            ScanIndexForward=False,  # Most recent first
            Limit=limit,
        )

        # Reverse to get chronological order
        items = list(reversed(response.get("Items", [])))
        return [{"role": item["role"], "content": item["content"]} for item in items]
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}")
        return []


def save_message(
    conversation_id: str,
    role: str,
    content: str,
    tenant_id: str,
    tool_calls: list | None = None,
    tokens_input: int = 0,
    tokens_output: int = 0,
    model_id: str | None = None,
    latency_ms: int = 0,
) -> str:
    """Save a message to DynamoDB."""
    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    ttl = int((now + timedelta(days=CONVERSATION_TTL_DAYS)).timestamp())

    item: dict = {
        "PK": f"CONV#{conversation_id}",
        "SK": f"MSG#{timestamp}#{message_id}",
        "message_id": message_id,
        "role": role,
        "content": content,
        "tenant_id": tenant_id,
        "created_at": timestamp,
        "ttl": ttl,
    }

    if tool_calls:
        item["tool_calls"] = tool_calls
    if tokens_input:
        item["tokens_input"] = tokens_input
    if tokens_output:
        item["tokens_output"] = tokens_output
    if model_id:
        item["model_id"] = model_id
    if latency_ms:
        item["latency_ms"] = latency_ms

    get_messages_table().put_item(Item=item)  # type: ignore[arg-type]
    return message_id


def update_conversation_metadata(
    conversation_id: str,
    user_id: str,
    message_text: str,
    tokens_used: int,
) -> None:
    """Update conversation metadata after a message."""
    now = datetime.now(timezone.utc).isoformat()

    # Generate title from first message if needed
    title = message_text[:50] + "..." if len(message_text) > 50 else message_text

    try:
        get_conversations_table().update_item(
            Key={
                "PK": f"USER#{user_id}",
                "SK": f"CONV#{conversation_id}",
            },
            UpdateExpression="""
                SET updated_at = :updated_at,
                    message_count = message_count + :inc,
                    total_tokens = total_tokens + :tokens,
                    title = if_not_exists(title, :title)
            """,
            ExpressionAttributeValues={
                ":updated_at": now,
                ":inc": 2,  # User + assistant message
                ":tokens": tokens_used,
                ":title": title,
            },
        )
    except Exception as e:
        logger.error(f"Error updating conversation metadata: {e}")


def handle_list_conversations(event: dict, user_info: dict) -> dict:
    """List all conversations for a user."""
    try:
        # Query by user-conversations-index
        response = get_conversations_table().query(
            IndexName="user-conversations-index",
            KeyConditionExpression="user_id = :user_id",
            ExpressionAttributeValues={
                ":user_id": user_info["user_id"],
            },
            ScanIndexForward=False,  # Most recent first
            Limit=50,
        )

        conversations = [
            {
                "conversation_id": item["conversation_id"],
                "title": item.get("title", "Untitled"),
                "updated_at": item["updated_at"],
                "message_count": item.get("message_count", 0),
            }
            for item in response.get("Items", [])
        ]

        return success_response({"conversations": conversations})

    except Exception as e:
        logger.exception(f"Error listing conversations: {e}")
        return error_response(500, "Failed to list conversations")


def handle_get_conversation(conversation_id: str, user_info: dict) -> dict:
    """Get a conversation with its messages."""
    try:
        # Verify ownership
        conversation = get_conversation(conversation_id, user_info["user_id"])
        if not conversation:
            return error_response(404, "Conversation not found")

        # Get messages
        messages_response = get_messages_table().query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={
                ":pk": f"CONV#{conversation_id}",
            },
            ScanIndexForward=True,  # Chronological order
            Limit=100,
        )

        messages = [
            {
                "message_id": item["message_id"],
                "role": item["role"],
                "content": item["content"],
                "created_at": item["created_at"],
                "tool_calls": item.get("tool_calls"),
            }
            for item in messages_response.get("Items", [])
        ]

        return success_response(
            {
                "conversation_id": conversation_id,
                "title": conversation.get("title", "Untitled"),
                "created_at": conversation["created_at"],
                "updated_at": conversation["updated_at"],
                "messages": messages,
            }
        )

    except Exception as e:
        logger.exception(f"Error getting conversation: {e}")
        return error_response(500, "Failed to get conversation")


def handle_delete_conversation(conversation_id: str, user_info: dict) -> dict:
    """Delete a conversation and its messages."""
    try:
        # Verify ownership
        conversation = get_conversation(conversation_id, user_info["user_id"])
        if not conversation:
            return error_response(404, "Conversation not found")

        # Delete conversation
        get_conversations_table().delete_item(
            Key={
                "PK": f"USER#{user_info['user_id']}",
                "SK": f"CONV#{conversation_id}",
            }
        )

        # Note: Messages will be cleaned up by TTL
        # For immediate deletion, we'd batch delete messages here

        return success_response({"deleted": True})

    except Exception as e:
        logger.exception(f"Error deleting conversation: {e}")
        return error_response(500, "Failed to delete conversation")


def success_response(data: dict) -> dict:
    """Build a successful API response."""
    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
        },
        "body": json.dumps(data, default=str),
    }


def error_response(status_code: int, message: str) -> dict:
    """Build an error API response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps({"error": message}),
    }
