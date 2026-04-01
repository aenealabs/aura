"""
Aura Chat WebSocket Message Handler

Handles incoming WebSocket messages and streams responses back to clients.
Implements real-time streaming using Bedrock's streaming API.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import boto3
from botocore.exceptions import ClientError

try:
    from tools import CHAT_TOOLS, execute_tool
except ImportError:
    from .tools import CHAT_TOOLS, execute_tool

# Import lazy-initialized AWS clients (Issue #466)
try:
    from aws_clients import get_bedrock_runtime_client, get_dynamodb_resource
except ImportError:
    import importlib

    _aws_clients = importlib.import_module("src.lambda.aws_clients")
    get_bedrock_runtime_client = _aws_clients.get_bedrock_runtime_client
    get_dynamodb_resource = _aws_clients.get_dynamodb_resource

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
PROJECT_NAME = os.environ.get("PROJECT_NAME", "aura")
CONNECTIONS_TABLE = os.environ.get(
    "CONNECTIONS_TABLE", f"{PROJECT_NAME}-chat-connections-{ENVIRONMENT}"
)
CONVERSATIONS_TABLE = os.environ.get(
    "CONVERSATIONS_TABLE", f"{PROJECT_NAME}-chat-conversations-{ENVIRONMENT}"
)
MESSAGES_TABLE = os.environ.get(
    "MESSAGES_TABLE", f"{PROJECT_NAME}-chat-messages-{ENVIRONMENT}"
)
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
)
CONVERSATION_TTL_DAYS = int(os.environ.get("CONVERSATION_TTL_DAYS", "30"))


# Lazy table accessors (Issue #466)
def get_connections_table():
    """Get DynamoDB connections table (lazy initialization)."""
    return get_dynamodb_resource().Table(CONNECTIONS_TABLE)


def get_conversations_table():
    """Get DynamoDB conversations table (lazy initialization)."""
    return get_dynamodb_resource().Table(CONVERSATIONS_TABLE)


def get_messages_table():
    """Get DynamoDB messages table (lazy initialization)."""
    return get_dynamodb_resource().Table(MESSAGES_TABLE)


# System prompt
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

Current environment: {environment}
"""


def handler(event: dict, context) -> dict:
    """
    Handle WebSocket messages (sendMessage route and $default).

    Supports:
    - action: "sendMessage" - Process a chat message with streaming
    - action: "ping" - Health check
    """
    logger.info(f"WebSocket message event: {json.dumps(event)}")

    try:
        connection_id = event["requestContext"]["connectionId"]
        domain = event["requestContext"]["domainName"]
        stage = event["requestContext"]["stage"]

        # Create API Gateway management client
        endpoint_url = f"https://{domain}/{stage}"
        api_client = boto3.client(
            "apigatewaymanagementapi",
            endpoint_url=endpoint_url,
        )

        # Parse message body
        body = json.loads(event.get("body", "{}"))
        action = body.get("action", "sendMessage")

        if action == "ping":
            send_to_connection(api_client, connection_id, {"type": "pong"})
            return {"statusCode": 200}

        if action == "sendMessage":
            return handle_send_message(
                api_client=api_client,
                connection_id=connection_id,
                body=body,
            )

        # Unknown action
        send_to_connection(
            api_client,
            connection_id,
            {
                "type": "error",
                "message": f"Unknown action: {action}",
            },
        )
        return {"statusCode": 400}

    except Exception as e:
        logger.exception(f"Error handling WebSocket message: {e}")
        return {"statusCode": 500}


def handle_send_message(
    api_client,
    connection_id: str,
    body: dict,
) -> dict:
    """Process a chat message and stream the response."""
    message_text = body.get("message", "").strip()
    conversation_id = body.get("conversation_id")

    if not message_text:
        send_to_connection(
            api_client,
            connection_id,
            {
                "type": "error",
                "message": "Message is required",
            },
        )
        return {"statusCode": 400}

    # Get connection info for user context
    connection_info = get_connection_info(connection_id)
    if not connection_info:
        send_to_connection(
            api_client,
            connection_id,
            {
                "type": "error",
                "message": "Connection not found",
            },
        )
        return {"statusCode": 401}

    user_info = {
        "user_id": connection_info.get("user_id", "anonymous"),
        "tenant_id": connection_info.get("tenant_id", "default"),
    }

    # Get or create conversation
    if not conversation_id:
        conversation_id = str(uuid.uuid4())
        create_conversation(conversation_id, user_info)

    # Send acknowledgment
    send_to_connection(
        api_client,
        connection_id,
        {
            "type": "ack",
            "conversation_id": conversation_id,
        },
    )

    # Get conversation history
    history = get_conversation_history(conversation_id, limit=10)

    # Save user message
    save_message(
        conversation_id=conversation_id,
        role="user",
        content=message_text,
        tenant_id=user_info["tenant_id"],
    )

    # Stream response from Bedrock
    full_response = stream_bedrock_response(
        api_client=api_client,
        connection_id=connection_id,
        message=message_text,
        history=history,
        user_info=user_info,
        conversation_id=conversation_id,
    )

    # Save assistant response
    save_message(
        conversation_id=conversation_id,
        role="assistant",
        content=full_response["content"],
        tenant_id=user_info["tenant_id"],
        tool_calls=full_response.get("tool_calls"),
        tokens_input=full_response.get("tokens_input", 0),
        tokens_output=full_response.get("tokens_output", 0),
        model_id=BEDROCK_MODEL_ID,
    )

    # Send completion
    send_to_connection(
        api_client,
        connection_id,
        {
            "type": "done",
            "conversation_id": conversation_id,
        },
    )

    return {"statusCode": 200}


def stream_bedrock_response(
    api_client,
    connection_id: str,
    message: str,
    history: list[dict],
    user_info: dict,
    conversation_id: str,
) -> dict:
    """
    Call Bedrock with streaming and send chunks to WebSocket.

    Returns the full response for storage.
    """
    import time

    start_time = time.time()

    # Build messages
    messages = []
    for msg in history:
        messages.append(
            {
                "role": msg["role"],
                "content": [{"text": msg["content"]}],
            }
        )
    messages.append(
        {
            "role": "user",
            "content": [{"text": message}],
        }
    )

    # Tool definitions
    tool_definitions = [
        {
            "toolSpec": {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": {"json": tool["parameters"]},
            }
        }
        for tool in CHAT_TOOLS
    ]

    full_content = ""
    tool_calls = []
    total_input_tokens = 0
    total_output_tokens = 0

    # Agentic loop with streaming
    max_iterations = 5
    for _iteration in range(max_iterations):
        try:
            # Use streaming API
            response = get_bedrock_runtime_client().converse_stream(
                modelId=BEDROCK_MODEL_ID,
                system=[{"text": SYSTEM_PROMPT.format(environment=ENVIRONMENT)}],
                messages=messages,
                toolConfig={"tools": tool_definitions},
                inferenceConfig={"maxTokens": 4096, "temperature": 0.3},
            )

            # Process stream
            current_text = ""
            current_tool_use = None
            stop_reason = None

            for event in response.get("stream", []):
                if "contentBlockStart" in event:
                    block = event["contentBlockStart"]
                    if "toolUse" in block.get("start", {}):
                        current_tool_use = {
                            "id": block["start"]["toolUse"]["toolUseId"],
                            "name": block["start"]["toolUse"]["name"],
                            "input": "",
                        }

                elif "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"]["delta"]

                    if "text" in delta:
                        chunk = delta["text"]
                        current_text += chunk
                        full_content += chunk

                        # Send chunk to client
                        send_to_connection(
                            api_client,
                            connection_id,
                            {
                                "type": "chunk",
                                "content": chunk,
                                "conversation_id": conversation_id,
                            },
                        )

                    elif "toolUse" in delta and current_tool_use:
                        current_tool_use["input"] += delta["toolUse"].get("input", "")

                elif "contentBlockStop" in event:
                    if current_tool_use:
                        # Parse tool input
                        try:
                            current_tool_use["input"] = json.loads(
                                current_tool_use["input"]
                            )
                        except json.JSONDecodeError:
                            pass

                elif "messageStop" in event:
                    stop_reason = event["messageStop"].get("stopReason")

                elif "metadata" in event:
                    usage = event["metadata"].get("usage", {})
                    total_input_tokens += usage.get("inputTokens", 0)
                    total_output_tokens += usage.get("outputTokens", 0)

            # Handle tool use
            if stop_reason == "tool_use" and current_tool_use:
                # Notify client about tool use
                send_to_connection(
                    api_client,
                    connection_id,
                    {
                        "type": "tool_use",
                        "tool_name": current_tool_use["name"],
                        "conversation_id": conversation_id,
                    },
                )

                # Execute tool
                try:
                    tool_result = execute_tool(
                        current_tool_use["name"],
                        current_tool_use["input"],
                        user_info,
                    )
                    tool_calls.append(
                        {
                            "name": current_tool_use["name"],
                            "input": current_tool_use["input"],
                            "output": tool_result,
                        }
                    )

                    # Add to messages for next iteration
                    messages.append(
                        {
                            "role": "assistant",
                            "content": [
                                {"text": current_text} if current_text else None,
                                {
                                    "toolUse": {
                                        "toolUseId": current_tool_use["id"],
                                        "name": current_tool_use["name"],
                                        "input": current_tool_use["input"],
                                    }
                                },
                            ],
                        }
                    )
                    # Filter out None
                    messages[-1]["content"] = [c for c in messages[-1]["content"] if c]

                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "toolResult": {
                                        "toolUseId": current_tool_use["id"],
                                        "content": [{"text": json.dumps(tool_result)}],
                                    }
                                }
                            ],
                        }
                    )

                except Exception as e:
                    logger.error(f"Tool execution error: {e}")
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "toolResult": {
                                        "toolUseId": current_tool_use["id"],
                                        "content": [{"text": f"Error: {str(e)}"}],
                                        "status": "error",
                                    }
                                }
                            ],
                        }
                    )
            else:
                # Final response
                break

        except ClientError as e:
            logger.error(f"Bedrock streaming error: {e}")
            send_to_connection(
                api_client,
                connection_id,
                {
                    "type": "error",
                    "message": "Failed to get AI response",
                },
            )
            break

    latency_ms = int((time.time() - start_time) * 1000)

    return {
        "content": full_content,
        "tool_calls": tool_calls if tool_calls else None,
        "tokens_input": total_input_tokens,
        "tokens_output": total_output_tokens,
        "latency_ms": latency_ms,
    }


def get_connection_info(connection_id: str) -> dict | None:
    """Get connection info from DynamoDB."""
    try:
        response = get_connections_table().get_item(
            Key={"connection_id": connection_id}
        )
        return response.get("Item")
    except Exception as e:
        logger.error(f"Error getting connection info: {e}")
        return None


def create_conversation(conversation_id: str, user_info: dict) -> None:
    """Create a new conversation."""
    now = datetime.now(timezone.utc).isoformat()
    ttl = int(
        (datetime.now(timezone.utc) + timedelta(days=CONVERSATION_TTL_DAYS)).timestamp()
    )

    get_conversations_table().put_item(
        Item={
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
    )


def get_conversation_history(conversation_id: str, limit: int = 10) -> list[dict]:
    """Get recent messages from a conversation."""
    try:
        response = get_messages_table().query(
            KeyConditionExpression="PK = :pk",
            ExpressionAttributeValues={":pk": f"CONV#{conversation_id}"},
            ScanIndexForward=False,
            Limit=limit,
        )
        items = list(reversed(response.get("Items", [])))
        return [{"role": item["role"], "content": item["content"]} for item in items]
    except Exception as e:
        logger.error(f"Error getting history: {e}")
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

    get_messages_table().put_item(Item=item)  # type: ignore[arg-type]
    return message_id


def send_to_connection(api_client, connection_id: str, data: dict) -> bool:
    """Send data to a WebSocket connection."""
    try:
        api_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps(data).encode("utf-8"),
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code")
        if error_code == "GoneException":
            logger.info(f"Connection {connection_id} is gone")
            # Clean up stale connection
            try:
                get_connections_table().delete_item(
                    Key={"connection_id": connection_id}
                )
            except Exception:
                pass
        else:
            logger.error(f"Error sending to connection: {e}")
        return False
