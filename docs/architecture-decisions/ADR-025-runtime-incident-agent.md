# ADR-025: RuntimeIncidentAgent for Code-Aware Incident Response

**Status:** Deployed
**Date:** 2025-12-06
**Decision Makers:** Project Aura Team
**Related:** ADR-005 (HITL Sandbox Architecture), ADR-022 (GitOps with ArgoCD)

## Context

Project Aura currently excels at **autonomous code intelligence** (vulnerability detection, patch generation, sandbox testing) but lacks **runtime incident response** capabilities. When production systems experience incidents, Aura cannot:

- Automatically investigate runtime errors and anomalies
- Correlate CloudWatch alarms with code paths in Neptune graph
- Map exceptions to specific functions in the codebase
- Identify recent deployments that may have introduced issues
- Generate root cause analysis hypotheses with code context

**Market Context:**

AWS DevOps Agent (announced December 2025, public preview) demonstrates 86% root cause analysis (RCA) success rate for operational incidents using:
- Multi-vendor observability integration (CloudWatch, Datadog, Dynatrace, Splunk)
- Deployment correlation (links incidents to recent code deployments)
- Application topology mapping (resource relationship discovery)
- Autonomous investigation with mean time to resolution (MTTR) reduction from hours to minutes

**Aura's Competitive Advantage:**

Unlike AWS DevOps Agent (which only sees infrastructure telemetry), Aura can leverage:
- **Neptune graph database**: Code relationships, call graphs, dependency trees
- **OpenSearch vector database**: Semantic code search, commit history
- **Git history integration**: Change tracking, blame analysis
- **Threat intelligence**: SBOM matching, CVE correlation with deployed code
- **GovCloud availability**: AWS DevOps Agent is NOT available in GovCloud (US)

**Problem Statement:**

Aura's agents currently operate in a **proactive security mode** (find vulnerabilities before they're exploited) but lack a **reactive operations mode** (investigate and resolve runtime incidents). This creates a gap in the autonomous DevSecOps lifecycle:

```
Current State:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Proactive   │     │              │     │  Reactive    │
│  Security    │────▶│   Sandbox    │────▶│  Operations  │
│  (Aura)      │     │   Testing    │     │  (MISSING)   │
└──────────────┘     └──────────────┘     └──────────────┘
     ✅                     ✅                    ❌

Desired State:
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Proactive   │     │              │     │  Reactive    │
│  Security    │────▶│   Sandbox    │────▶│  Operations  │
│  (Aura)      │     │   Testing    │     │  (Aura RIA)  │
└──────────────┘     └──────────────┘     └──────────────┘
     ✅                     ✅                    ✅
```

**Enterprise Requirements:**

1. **Autonomous Incident Investigation**: Trigger on CloudWatch alarms, PagerDuty webhooks, SNS notifications
2. **Code-Aware RCA**: Correlate runtime metrics with Neptune code graph and OpenSearch semantic search
3. **Deployment Correlation**: Link incidents to recent ArgoCD deployments via Git commit SHAs
4. **HITL Governance**: Require human approval before executing mitigations (consistent with ADR-005)
5. **Audit Trail**: Log all investigations and actions in DynamoDB with 365-day retention
6. **GovCloud Compatibility**: No external SaaS dependencies (AWS services only)
7. **Multi-Vendor Observability**: Support CloudWatch, Datadog, Prometheus (via MCP adapters)

## Decision

We introduce a new **RuntimeIncidentAgent** that extends Aura's autonomous capabilities to runtime incident response, leveraging our unique code intelligence architecture.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RuntimeIncidentAgent Architecture                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   CloudWatch Alarm                                                           │
│   PagerDuty Webhook          EventBridge Rule                               │
│   SNS Notification    ──────▶ aura-incident-trigger-{env}                   │
│                                        │                                     │
│                                        ▼                                     │
│                         ┌──────────────────────────────┐                    │
│                         │  Step Functions Workflow      │                   │
│                         │  aura-incident-investigation  │                   │
│                         └──────────────────────────────┘                    │
│                                        │                                     │
│                                        ▼                                     │
│                         ┌──────────────────────────────┐                    │
│                         │  RuntimeIncidentAgent (ECS)   │                   │
│                         │  • Parse incident context     │                   │
│                         │  • Query observability        │                   │
│                         │  • Correlate with code graph  │                   │
│                         │  • Generate RCA hypothesis    │                   │
│                         │  • Propose mitigations        │                   │
│                         └──────────────────────────────┘                    │
│                                        │                                     │
│              ┌─────────────────────────┼─────────────────────────┐          │
│              ▼                         ▼                         ▼          │
│    ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐     │
│    │ Neptune Graph    │   │ OpenSearch       │   │ Observability    │     │
│    │ • Call graphs    │   │ • Git history    │   │ • CloudWatch     │     │
│    │ • Dependencies   │   │ • Commit search  │   │ • Datadog (MCP)  │     │
│    │ • Code entities  │   │ • Semantic code  │   │ • Prometheus     │     │
│    └──────────────────┘   └──────────────────┘   └──────────────────┘     │
│                                        │                                     │
│                                        ▼                                     │
│                         ┌──────────────────────────────┐                    │
│                         │  DynamoDB: Investigations     │                   │
│                         │  • incident_id (HASH)         │                   │
│                         │  • timestamp (RANGE)          │                   │
│                         │  • source (alarm/pagerduty)   │                   │
│                         │  • rca_hypothesis             │                   │
│                         │  • confidence_score           │                   │
│                         │  • deployment_correlation     │                   │
│                         │  • mitigation_plan            │                   │
│                         │  • hitl_status (pending/...)  │                   │
│                         └──────────────────────────────┘                    │
│                                        │                                     │
│                                        ▼                                     │
│                         ┌──────────────────────────────┐                    │
│                         │  HITL Approval Dashboard      │                   │
│                         │  • View RCA with code context │                   │
│                         │  • Approve/reject mitigation  │                   │
│                         │  • Manual runbook execution   │                   │
│                         └──────────────────────────────┘                    │
│                                        │                                     │
│                                        ▼                                     │
│                         ┌──────────────────────────────┐                    │
│                         │  SNS: Alert Notification      │                   │
│                         │  aura-incident-alerts-{env}   │                   │
│                         └──────────────────────────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. RuntimeIncidentAgent (Python Class)

**Location:** `src/agents/runtime_incident_agent.py`

**Responsibilities:**
- Parse incident events from EventBridge (CloudWatch alarms, PagerDuty webhooks)
- Query observability platforms (CloudWatch, Datadog via MCP, Prometheus)
- Correlate runtime metrics with Neptune code graph (map stack traces to functions)
- Search OpenSearch for recent code changes affecting incident scope
- Query deployment history from `aura-deployments-{env}` DynamoDB table
- Generate root cause analysis hypotheses with confidence scores
- Propose mitigation plans (rollback, config change, hotfix)
- Store investigation results in DynamoDB for HITL approval

**Unique Capabilities vs AWS DevOps Agent:**
| Capability | AWS DevOps Agent | RuntimeIncidentAgent |
|------------|------------------|----------------------|
| **Code correlation** | ❌ No code visibility | ✅ Maps exceptions to Neptune graph functions |
| **Semantic search** | ❌ No | ✅ OpenSearch finds related code changes |
| **Threat context** | ❌ No | ✅ Links incidents to known CVEs via SBOM |
| **Git blame** | ❌ No | ✅ Identifies authors of code in stack trace |
| **Patch generation** | ❌ No | ✅ Can trigger CoderAgent for hotfixes |

#### 2. Deployment Correlation Engine

**DynamoDB Table:** `aura-deployments-{env}`

**Schema:**
```yaml
AttributeDefinitions:
  - AttributeName: deployment_id
    AttributeType: S
  - AttributeName: timestamp
    AttributeType: S
  - AttributeName: application_name
    AttributeType: S

KeySchema:
  - AttributeName: deployment_id
    KeyType: HASH
  - AttributeName: timestamp
    KeyType: RANGE

GlobalSecondaryIndexes:
  - IndexName: by-application
    KeySchema:
      - AttributeName: application_name
        KeyType: HASH
      - AttributeName: timestamp
        KeyType: RANGE
    Projection:
      ProjectionType: ALL

Attributes:
  deployment_id: UUID (e.g., "deploy-20251206-143025-a1b2c3")
  timestamp: ISO 8601 (e.g., "2025-12-06T14:30:25Z")
  application_name: String (e.g., "aura-api", "frontend")
  commit_sha: String (e.g., "89778ca")
  commit_message: String
  argocd_sync_status: String (e.g., "Synced", "OutOfSync")
  rollout_status: String (e.g., "Healthy", "Degraded")
  image_tag: String (e.g., "v1.2.3")
  deployed_by: String (e.g., "argocd", "manual")
```

**EventBridge Integration:**
```yaml
# CloudFormation resource in deploy/cloudformation/serverless.yaml
DeploymentEventRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-deployment-events-${Environment}'
    EventBusName: !Ref IncidentEventBus
    EventPattern:
      source:
        - argocd
        - codebuild
      detail-type:
        - "ArgoCD Sync Completed"
        - "CodeBuild Build State Change"
    State: ENABLED
    Targets:
      - Arn: !GetAtt DeploymentRecorderFunction.Arn
        Id: record-deployment
```

**Lambda Function:** `DeploymentRecorderFunction` writes ArgoCD sync events to DynamoDB

#### 3. Investigation Workflow (Step Functions)

**State Machine:** `aura-incident-investigation-{env}`

**Workflow:**
```json
{
  "StartAt": "ParseIncidentEvent",
  "States": {
    "ParseIncidentEvent": {
      "Type": "Task",
      "Resource": "arn:${AWS::Partition}:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "${ParseIncidentFunction}",
        "Payload.$": "$"
      },
      "Next": "InvokeRuntimeIncidentAgent"
    },
    "InvokeRuntimeIncidentAgent": {
      "Type": "Task",
      "Resource": "arn:${AWS::Partition}:states:::ecs:runTask.sync",
      "Parameters": {
        "Cluster": "${ECSCluster}",
        "TaskDefinition": "${RuntimeIncidentAgentTask}",
        "LaunchType": "FARGATE",
        "Overrides": {
          "ContainerOverrides": [{
            "Name": "runtime-incident-agent",
            "Environment": [
              {"Name": "INCIDENT_ID", "Value.$": "$.incident_id"},
              {"Name": "SOURCE", "Value.$": "$.source"}
            ]
          }]
        }
      },
      "ResultPath": "$.investigation",
      "Next": "StoreInvestigationResults"
    },
    "StoreInvestigationResults": {
      "Type": "Task",
      "Resource": "arn:${AWS::Partition}:states:::dynamodb:putItem",
      "Parameters": {
        "TableName": "${InvestigationsTable}",
        "Item": {
          "incident_id": {"S.$": "$.incident_id"},
          "timestamp": {"S.$": "$$.State.EnteredTime"},
          "rca_hypothesis": {"S.$": "$.investigation.rca"},
          "confidence_score": {"N.$": "$.investigation.confidence"},
          "mitigation_plan": {"S.$": "$.investigation.mitigation"},
          "hitl_status": {"S": "pending"}
        }
      },
      "Next": "SendHITLNotification"
    },
    "SendHITLNotification": {
      "Type": "Task",
      "Resource": "arn:${AWS::Partition}:states:::sns:publish",
      "Parameters": {
        "TopicArn": "${IncidentAlertsTopic}",
        "Subject": "HITL Required: Incident Investigation Complete",
        "Message.$": "States.Format('Investigation {} complete. Confidence: {}%. Review at: {}', $.incident_id, $.investigation.confidence, $.dashboard_url)"
      },
      "End": true
    }
  }
}
```

#### 4. Incident Investigations Table (DynamoDB)

**Table Name:** `aura-incident-investigations-{env}`

**Schema:**
```yaml
AttributeDefinitions:
  - AttributeName: incident_id
    AttributeType: S
  - AttributeName: timestamp
    AttributeType: S
  - AttributeName: hitl_status
    AttributeType: S

KeySchema:
  - AttributeName: incident_id
    KeyType: HASH
  - AttributeName: timestamp
    KeyType: RANGE

GlobalSecondaryIndexes:
  - IndexName: by-hitl-status
    KeySchema:
      - AttributeName: hitl_status
        KeyType: HASH
      - AttributeName: timestamp
        KeyType: RANGE
    Projection:
      ProjectionType: ALL

TimeToLiveAttribute:
  AttributeName: ttl
  Enabled: true

Attributes:
  incident_id: UUID
  timestamp: ISO 8601
  source: String (e.g., "cloudwatch", "pagerduty", "datadog")
  alert_name: String
  affected_service: String
  rca_hypothesis: String (LLM-generated analysis)
  confidence_score: Number (0-100)
  deployment_correlation: JSON (recent deployments in incident window)
  code_entities: JSON (Neptune graph nodes involved)
  git_commits: JSON (OpenSearch results for related changes)
  mitigation_plan: String (proposed actions)
  hitl_status: String (pending/approved/rejected)
  hitl_approver: String (user email)
  hitl_timestamp: ISO 8601
  executed: Boolean
  execution_result: String
  ttl: Number (90 days for dev, 365 days for prod)
```

### Integration Points

#### EventBridge Rules (Incident Triggers)

**CloudWatch Alarms:**
```yaml
CloudWatchIncidentRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-cloudwatch-incidents-${Environment}'
    EventBusName: !Ref IncidentEventBus
    EventPattern:
      source:
        - aws.cloudwatch
      detail-type:
        - "CloudWatch Alarm State Change"
      detail:
        state:
          value:
            - ALARM
        alarmName:
          - prefix: "aura-"
    State: ENABLED
    Targets:
      - Arn: !GetAtt IncidentInvestigationStateMachine.Arn
        RoleArn: !GetAtt EventBridgeInvokeStepFunctionsRole.Arn
```

**PagerDuty Webhooks:**
```yaml
PagerDutyIncidentRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-pagerduty-incidents-${Environment}'
    EventBusName: !Ref IncidentEventBus
    EventPattern:
      source:
        - pagerduty
      detail-type:
        - "PagerDuty Incident Triggered"
    State: ENABLED
    Targets:
      - Arn: !GetAtt IncidentInvestigationStateMachine.Arn
        RoleArn: !GetAtt EventBridgeInvokeStepFunctionsRole.Arn
```

#### MCP Adapter Extensions

**Datadog APM Traces:**
```python
# src/services/mcp_tool_adapters.py

@require_enterprise_mode
async def datadog_query_traces(
    self,
    service: str,
    time_range: tuple[datetime, datetime],
    error_only: bool = True
) -> list[dict]:
    """
    Query Datadog APM traces for incident correlation.

    Args:
        service: Service name (e.g., "aura-api")
        time_range: (start_time, end_time) tuple
        error_only: Filter to error traces only

    Returns:
        List of trace spans with error context
    """
    start, end = time_range
    query = f"service:{service}"
    if error_only:
        query += " status:error"

    # Use Datadog MCP server or direct API
    traces = await self.mcp_client.call_tool(
        "datadog_traces",
        {
            "query": query,
            "start": int(start.timestamp()),
            "end": int(end.timestamp())
        }
    )

    return traces
```

**Prometheus Metrics:**
```python
@require_enterprise_mode
async def prometheus_query_range(
    self,
    query: str,
    start_time: datetime,
    end_time: datetime,
    step: str = "1m"
) -> dict:
    """
    Query Prometheus metrics for incident analysis.

    Args:
        query: PromQL query (e.g., "rate(http_requests_total[5m])")
        start_time: Query start time
        end_time: Query end time
        step: Resolution step (e.g., "1m", "5m")

    Returns:
        Time series data with metric values
    """
    # Use Prometheus HTTP API
    prometheus_url = os.getenv("PROMETHEUS_URL", "http://prometheus.aura.local:9090")

    response = await self.http_client.get(
        f"{prometheus_url}/api/v1/query_range",
        params={
            "query": query,
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "step": step
        }
    )

    return response.json()
```

### RuntimeIncidentAgent Implementation

**Class Structure:**
```python
# src/agents/runtime_incident_agent.py

from typing import Optional, Dict, List
from datetime import datetime, timedelta
import boto3
from src.services.context_retrieval_service import ContextRetrievalService
from src.services.mcp_tool_adapters import MCPToolAdapters
from src.utils.llm_client import BedrockLLMClient

class RuntimeIncidentAgent:
    """
    Autonomous agent for runtime incident investigation with code-aware RCA.

    Unique capabilities:
    - Correlates runtime metrics with Neptune code graph
    - Searches OpenSearch for recent code changes
    - Links incidents to deployment events
    - Generates RCA hypotheses with confidence scores
    - Proposes mitigations with rollback plans
    """

    def __init__(
        self,
        llm_client: BedrockLLMClient,
        context_service: ContextRetrievalService,
        mcp_adapters: MCPToolAdapters
    ):
        self.llm = llm_client
        self.context = context_service
        self.mcp = mcp_adapters
        self.dynamodb = boto3.resource('dynamodb')
        self.deployments_table = self.dynamodb.Table(
            f"aura-deployments-{os.getenv('ENVIRONMENT', 'dev')}"
        )
        self.investigations_table = self.dynamodb.Table(
            f"aura-incident-investigations-{os.getenv('ENVIRONMENT', 'dev')}"
        )

    async def investigate(self, incident_event: Dict) -> Dict:
        """
        Main investigation workflow.

        Args:
            incident_event: EventBridge event containing incident details

        Returns:
            Investigation results with RCA hypothesis, confidence, and mitigation plan
        """
        incident_id = incident_event['id']
        source = incident_event['source']
        detail = incident_event['detail']

        # Step 1: Parse incident context
        incident_context = self._parse_incident_context(source, detail)

        # Step 2: Query observability platforms
        metrics = await self._query_observability(incident_context)

        # Step 3: Correlate with deployment history
        recent_deployments = await self._query_recent_deployments(
            incident_context['affected_service'],
            incident_context['timestamp']
        )

        # Step 4: Map to code entities in Neptune
        code_entities = await self._correlate_with_code_graph(
            incident_context['error_message'],
            incident_context['stack_trace']
        )

        # Step 5: Search for related code changes in OpenSearch
        git_commits = await self._search_recent_changes(
            code_entities,
            incident_context['timestamp']
        )

        # Step 6: Generate RCA hypothesis using LLM
        rca_result = await self._generate_rca_hypothesis(
            incident_context=incident_context,
            metrics=metrics,
            deployments=recent_deployments,
            code_entities=code_entities,
            git_commits=git_commits
        )

        # Step 7: Propose mitigation plan
        mitigation_plan = await self._generate_mitigation_plan(
            rca_result,
            recent_deployments
        )

        # Step 8: Store investigation results
        investigation = {
            'incident_id': incident_id,
            'timestamp': datetime.utcnow().isoformat(),
            'source': source,
            'alert_name': incident_context.get('alert_name'),
            'affected_service': incident_context['affected_service'],
            'rca_hypothesis': rca_result['hypothesis'],
            'confidence_score': rca_result['confidence'],
            'deployment_correlation': recent_deployments,
            'code_entities': code_entities,
            'git_commits': git_commits,
            'mitigation_plan': mitigation_plan,
            'hitl_status': 'pending'
        }

        self.investigations_table.put_item(Item=investigation)

        return investigation

    def _parse_incident_context(self, source: str, detail: Dict) -> Dict:
        """Extract standardized incident context from various sources."""
        if source == 'aws.cloudwatch':
            return {
                'alert_name': detail['alarmName'],
                'affected_service': self._extract_service_from_alarm(detail['alarmName']),
                'timestamp': detail['stateChangeTime'],
                'error_message': detail.get('newStateReason', ''),
                'stack_trace': None,
                'metric_name': detail.get('configuration', {}).get('metrics', [{}])[0].get('metricStat', {}).get('metric', {}).get('name')
            }
        elif source == 'pagerduty':
            return {
                'alert_name': detail['incident']['title'],
                'affected_service': detail['incident']['service']['name'],
                'timestamp': detail['incident']['created_at'],
                'error_message': detail['incident']['body']['details'],
                'stack_trace': None
            }
        else:
            raise ValueError(f"Unsupported incident source: {source}")

    async def _query_observability(self, incident_context: Dict) -> Dict:
        """Query CloudWatch, Datadog, Prometheus for incident window metrics."""
        incident_time = datetime.fromisoformat(incident_context['timestamp'].replace('Z', '+00:00'))
        start_time = incident_time - timedelta(minutes=30)
        end_time = incident_time + timedelta(minutes=5)

        metrics = {}

        # CloudWatch Logs (errors in incident window)
        cloudwatch_logs = await self._query_cloudwatch_logs(
            log_group=f"/ecs/{incident_context['affected_service']}",
            start_time=start_time,
            end_time=end_time,
            filter_pattern='ERROR'
        )
        metrics['cloudwatch_logs'] = cloudwatch_logs

        # Datadog APM traces (if Enterprise mode)
        if self.mcp.is_enterprise_mode():
            datadog_traces = await self.mcp.datadog_query_traces(
                service=incident_context['affected_service'],
                time_range=(start_time, end_time),
                error_only=True
            )
            metrics['datadog_traces'] = datadog_traces

        # Prometheus metrics (Kubernetes pod metrics)
        prometheus_metrics = await self.mcp.prometheus_query_range(
            query=f'rate(container_cpu_usage_seconds_total{{pod=~"{incident_context["affected_service"]}.*"}}[5m])',
            start_time=start_time,
            end_time=end_time
        )
        metrics['prometheus_cpu'] = prometheus_metrics

        return metrics

    async def _query_recent_deployments(
        self,
        service_name: str,
        incident_time: str,
        lookback_hours: int = 24
    ) -> List[Dict]:
        """Query deployment history to find recent changes."""
        incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        cutoff_time = incident_dt - timedelta(hours=lookback_hours)

        response = self.deployments_table.query(
            IndexName='by-application',
            KeyConditionExpression='application_name = :app AND #ts > :cutoff',
            ExpressionAttributeNames={'#ts': 'timestamp'},
            ExpressionAttributeValues={
                ':app': service_name,
                ':cutoff': cutoff_time.isoformat()
            },
            ScanIndexForward=False  # Most recent first
        )

        return response.get('Items', [])

    async def _correlate_with_code_graph(
        self,
        error_message: Optional[str],
        stack_trace: Optional[str]
    ) -> List[Dict]:
        """
        Map error messages and stack traces to Neptune code entities.

        This is Aura's unique capability vs AWS DevOps Agent.
        """
        if not error_message and not stack_trace:
            return []

        code_entities = []

        # Extract function names from stack trace
        if stack_trace:
            function_names = self._extract_function_names(stack_trace)
            for func_name in function_names:
                # Query Neptune for function node
                entity = await self.context.graph_store.get_entity_by_name(
                    entity_type='function',
                    name=func_name
                )
                if entity:
                    code_entities.append(entity)

        # Semantic search in OpenSearch for error message
        if error_message:
            similar_code = await self.context.vector_store.semantic_search(
                query=error_message,
                top_k=5,
                filters={'entity_type': 'function'}
            )
            code_entities.extend(similar_code)

        return code_entities

    async def _search_recent_changes(
        self,
        code_entities: List[Dict],
        incident_time: str,
        lookback_days: int = 7
    ) -> List[Dict]:
        """Search OpenSearch for recent commits affecting code entities."""
        incident_dt = datetime.fromisoformat(incident_time.replace('Z', '+00:00'))
        cutoff_time = incident_dt - timedelta(days=lookback_days)

        git_commits = []

        for entity in code_entities:
            file_path = entity.get('file_path')
            if file_path:
                # Search OpenSearch for commits modifying this file
                commits = await self.context.vector_store.search_commits(
                    file_path=file_path,
                    after=cutoff_time
                )
                git_commits.extend(commits)

        # Deduplicate by commit SHA
        unique_commits = {c['sha']: c for c in git_commits}.values()
        return list(unique_commits)

    async def _generate_rca_hypothesis(
        self,
        incident_context: Dict,
        metrics: Dict,
        deployments: List[Dict],
        code_entities: List[Dict],
        git_commits: List[Dict]
    ) -> Dict:
        """
        Use LLM to generate root cause analysis hypothesis.

        Returns:
            {
                'hypothesis': str,
                'confidence': int (0-100),
                'evidence': List[str]
            }
        """
        prompt = self._build_rca_prompt(
            incident_context=incident_context,
            metrics=metrics,
            deployments=deployments,
            code_entities=code_entities,
            git_commits=git_commits
        )

        response = await self.llm.generate(
            prompt=prompt,
            max_tokens=2000,
            temperature=0.3  # Lower temperature for analytical tasks
        )

        # Parse structured response
        rca_result = self._parse_rca_response(response)
        return rca_result

    def _build_rca_prompt(
        self,
        incident_context: Dict,
        metrics: Dict,
        deployments: List[Dict],
        code_entities: List[Dict],
        git_commits: List[Dict]
    ) -> str:
        """Construct LLM prompt for RCA generation."""
        return f"""You are a senior SRE investigating a production incident. Analyze the following data and generate a root cause analysis hypothesis.

**Incident Details:**
- Alert: {incident_context.get('alert_name')}
- Service: {incident_context['affected_service']}
- Timestamp: {incident_context['timestamp']}
- Error Message: {incident_context.get('error_message', 'N/A')}
- Metric Triggered: {incident_context.get('metric_name', 'N/A')}

**Recent Deployments (Last 24 Hours):**
{self._format_deployments(deployments)}

**Code Entities Involved:**
{self._format_code_entities(code_entities)}

**Recent Code Changes (Last 7 Days):**
{self._format_git_commits(git_commits)}

**Observability Data:**
- CloudWatch Errors: {len(metrics.get('cloudwatch_logs', []))} log entries
- Datadog Traces: {len(metrics.get('datadog_traces', []))} error traces
- CPU Usage: {self._summarize_prometheus_data(metrics.get('prometheus_cpu', {}))}

**Task:**
Generate a root cause analysis hypothesis following this structure:

1. **Hypothesis**: Single sentence describing the likely root cause
2. **Confidence**: Integer 0-100 indicating confidence in this hypothesis
3. **Evidence**: Bulleted list of supporting evidence from the data above
4. **Alternative Hypotheses**: 1-2 alternative explanations if confidence < 80%

Format your response as JSON:
{{
  "hypothesis": "...",
  "confidence": 85,
  "evidence": ["...", "...", "..."],
  "alternatives": ["...", "..."]
}}
"""

    async def _generate_mitigation_plan(
        self,
        rca_result: Dict,
        recent_deployments: List[Dict]
    ) -> str:
        """Generate mitigation plan based on RCA hypothesis."""
        prompt = f"""Based on the following root cause analysis, generate a step-by-step mitigation plan.

**RCA Hypothesis:** {rca_result['hypothesis']}
**Confidence:** {rca_result['confidence']}%
**Evidence:** {', '.join(rca_result['evidence'])}

**Recent Deployments:**
{self._format_deployments(recent_deployments)}

**Task:**
Generate a mitigation plan with:
1. Immediate actions to restore service (if applicable)
2. Verification steps to confirm mitigation success
3. Rollback plan if mitigation fails
4. Long-term fixes to prevent recurrence

Format as a numbered list.
"""

        response = await self.llm.generate(
            prompt=prompt,
            max_tokens=1500,
            temperature=0.4
        )

        return response

    # Helper methods
    def _extract_service_from_alarm(self, alarm_name: str) -> str:
        """Extract service name from CloudWatch alarm name."""
        # Example: "aura-api-high-cpu-dev" -> "aura-api"
        parts = alarm_name.split('-')
        if len(parts) >= 2:
            return '-'.join(parts[:2])
        return 'unknown'

    def _extract_function_names(self, stack_trace: str) -> List[str]:
        """Parse stack trace to extract function names."""
        # Simple regex for Python stack traces
        # Example: "  File \"/app/src/api.py\", line 45, in handle_request"
        import re
        pattern = r'in (\w+)'
        matches = re.findall(pattern, stack_trace)
        return list(set(matches))

    def _format_deployments(self, deployments: List[Dict]) -> str:
        """Format deployment data for LLM prompt."""
        if not deployments:
            return "No recent deployments found."

        lines = []
        for d in deployments[:5]:  # Limit to 5 most recent
            lines.append(
                f"- {d['timestamp']}: {d['application_name']} → {d['image_tag']} "
                f"(commit: {d['commit_sha'][:7]}, status: {d['rollout_status']})"
            )
        return '\n'.join(lines)

    def _format_code_entities(self, code_entities: List[Dict]) -> str:
        """Format code entity data for LLM prompt."""
        if not code_entities:
            return "No code entities identified in incident."

        lines = []
        for entity in code_entities[:10]:  # Limit to 10
            lines.append(
                f"- {entity.get('name')} ({entity.get('entity_type')}) "
                f"in {entity.get('file_path', 'unknown file')}"
            )
        return '\n'.join(lines)

    def _format_git_commits(self, git_commits: List[Dict]) -> str:
        """Format git commit data for LLM prompt."""
        if not git_commits:
            return "No recent code changes affecting incident scope."

        lines = []
        for commit in git_commits[:5]:  # Limit to 5 most recent
            lines.append(
                f"- {commit['timestamp']}: {commit['message']} "
                f"(SHA: {commit['sha'][:7]}, author: {commit['author']})"
            )
        return '\n'.join(lines)

    def _summarize_prometheus_data(self, prometheus_data: Dict) -> str:
        """Summarize Prometheus time series data."""
        if not prometheus_data or 'data' not in prometheus_data:
            return "No data"

        # Calculate avg/max from time series
        values = [float(v[1]) for result in prometheus_data['data']['result']
                  for v in result.get('values', [])]
        if not values:
            return "No data"

        avg = sum(values) / len(values)
        max_val = max(values)
        return f"avg={avg:.2f}, max={max_val:.2f}"

    def _parse_rca_response(self, response: str) -> Dict:
        """Parse LLM response into structured RCA result."""
        import json
        try:
            # Extract JSON from response (handle markdown code blocks)
            if '```json' in response:
                json_start = response.index('```json') + 7
                json_end = response.rindex('```')
                json_str = response[json_start:json_end].strip()
            elif '```' in response:
                json_start = response.index('```') + 3
                json_end = response.rindex('```')
                json_str = response[json_start:json_end].strip()
            else:
                json_str = response.strip()

            result = json.loads(json_str)

            # Validate required fields
            if 'hypothesis' not in result or 'confidence' not in result:
                raise ValueError("Missing required fields in RCA response")

            # Ensure confidence is in valid range
            result['confidence'] = max(0, min(100, int(result['confidence'])))

            return result
        except Exception as e:
            # Fallback for parsing errors
            return {
                'hypothesis': 'Unable to determine root cause (parsing error)',
                'confidence': 0,
                'evidence': [str(e)],
                'alternatives': []
            }

    async def _query_cloudwatch_logs(
        self,
        log_group: str,
        start_time: datetime,
        end_time: datetime,
        filter_pattern: str
    ) -> List[Dict]:
        """Query CloudWatch Logs for incident window."""
        logs_client = boto3.client('logs')

        try:
            response = logs_client.filter_log_events(
                logGroupName=log_group,
                startTime=int(start_time.timestamp() * 1000),
                endTime=int(end_time.timestamp() * 1000),
                filterPattern=filter_pattern,
                limit=100
            )
            return response.get('events', [])
        except Exception as e:
            # Log group may not exist or no permissions
            return []
```

### HITL Dashboard Integration

**React Component:** `frontend/src/components/IncidentInvestigations.jsx`

**Features:**
- Display pending investigations in table format
- Show RCA hypothesis with confidence score
- Visualize deployment correlation timeline
- Link to code entities in Neptune graph
- Approve/reject mitigation plans
- Execute approved mitigations (rollback, config change, hotfix)

**API Endpoints:** `src/api/incidents.py`

```python
from fastapi import APIRouter, HTTPException
from typing import List
import boto3

router = APIRouter(prefix="/api/incidents", tags=["incidents"])

@router.get("/investigations")
async def list_investigations(
    hitl_status: Optional[str] = None,
    limit: int = 50
) -> List[Dict]:
    """List incident investigations, optionally filtered by HITL status."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(f"aura-incident-investigations-{os.getenv('ENVIRONMENT')}")

    if hitl_status:
        response = table.query(
            IndexName='by-hitl-status',
            KeyConditionExpression='hitl_status = :status',
            ExpressionAttributeValues={':status': hitl_status},
            Limit=limit,
            ScanIndexForward=False
        )
    else:
        response = table.scan(Limit=limit)

    return response.get('Items', [])

@router.get("/investigations/{incident_id}")
async def get_investigation(incident_id: str) -> Dict:
    """Get detailed investigation results."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(f"aura-incident-investigations-{os.getenv('ENVIRONMENT')}")

    # Query by incident_id (HASH key)
    response = table.query(
        KeyConditionExpression='incident_id = :id',
        ExpressionAttributeValues={':id': incident_id},
        Limit=1
    )

    items = response.get('Items', [])
    if not items:
        raise HTTPException(status_code=404, detail="Investigation not found")

    return items[0]

@router.post("/investigations/{incident_id}/approve")
async def approve_mitigation(
    incident_id: str,
    approver_email: str
) -> Dict:
    """Approve mitigation plan for execution."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(f"aura-incident-investigations-{os.getenv('ENVIRONMENT')}")

    # Update HITL status to approved
    table.update_item(
        Key={'incident_id': incident_id},
        UpdateExpression='SET hitl_status = :approved, hitl_approver = :email, hitl_timestamp = :ts',
        ExpressionAttributeValues={
            ':approved': 'approved',
            ':email': approver_email,
            ':ts': datetime.utcnow().isoformat()
        }
    )

    # TODO: Trigger mitigation execution (Step Functions or direct action)

    return {'status': 'approved', 'incident_id': incident_id}

@router.post("/investigations/{incident_id}/reject")
async def reject_mitigation(
    incident_id: str,
    approver_email: str,
    reason: str
) -> Dict:
    """Reject mitigation plan."""
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table(f"aura-incident-investigations-{os.getenv('ENVIRONMENT')}")

    table.update_item(
        Key={'incident_id': incident_id},
        UpdateExpression='SET hitl_status = :rejected, hitl_approver = :email, hitl_timestamp = :ts, rejection_reason = :reason',
        ExpressionAttributeValues={
            ':rejected': 'rejected',
            ':email': approver_email,
            ':ts': datetime.utcnow().isoformat(),
            ':reason': reason
        }
    )

    return {'status': 'rejected', 'incident_id': incident_id}
```

## Consequences

### Positive

1. **Closes Capability Gap**: Aura gains runtime incident response to complement proactive security
2. **Unique Differentiation**: Code-aware RCA that AWS DevOps Agent cannot provide
3. **MTTR Reduction**: Automated investigation reduces mean time to resolution from hours to minutes
4. **GovCloud Advantage**: No AWS DevOps Agent competition in federal/defense market
5. **Deployment Correlation**: Links incidents to recent changes for faster diagnosis
6. **HITL Governance**: Maintains human oversight consistent with ADR-005
7. **Compliance Audit Trail**: DynamoDB logging with 365-day retention for SOX/CMMC

### Negative

1. **Operational Complexity**: Adds new EventBridge rules, Step Functions, DynamoDB tables, Lambda functions
2. **Cost Increase**: ~$50-100/month for additional infrastructure (Step Functions executions, DynamoDB storage)
3. **LLM Token Usage**: RCA generation increases Bedrock costs (estimated $0.05-0.10 per investigation)
4. **False Positives**: Low-confidence RCA hypotheses may burden HITL reviewers
5. **Dependency on Observability Integration**: Requires CloudWatch, Datadog, Prometheus to be properly configured

### Risks

1. **Alert Fatigue**: Too many low-severity incidents trigger investigations
   - **Mitigation**: Add severity filtering in EventBridge rules (only ALARM state, critical services)

2. **Code Correlation Accuracy**: Neptune/OpenSearch queries may not always find relevant code
   - **Mitigation**: Implement confidence scoring, surface "no code found" cases separately

3. **Deployment Data Staleness**: ArgoCD events may not be captured if EventBridge integration fails
   - **Mitigation**: Add health check Lambda to verify deployment table freshness

4. **HITL Bottleneck**: Too many pending investigations overwhelm approvers
   - **Mitigation**: Auto-approve high-confidence (>90%) mitigations with post-execution notification

## Alternatives Considered

### Alternative 1: Integrate AWS DevOps Agent via API

**Description**: Use AWS DevOps Agent as a black-box service, forward Aura's incidents to it

**Pros:**
- Faster implementation (no custom agent code)
- Leverage AWS-managed infrastructure

**Cons:**
- No GovCloud availability (dealbreaker for federal customers)
- Cannot access Neptune/OpenSearch code context
- Vendor lock-in to AWS service pricing
- No control over RCA prompt engineering

**Decision**: Rejected due to GovCloud incompatibility and lack of code intelligence

### Alternative 2: Extend Existing Security Agents Instead of New Agent

**Description**: Add incident response to `AdaptiveIntelligenceAgent` rather than creating RuntimeIncidentAgent

**Pros:**
- Fewer agent classes to maintain
- Reuses existing infrastructure

**Cons:**
- AdaptiveIntelligenceAgent is proactive (threat monitoring), not reactive (incident response)
- Mixing concerns violates single responsibility principle
- Different HITL workflows (security approval vs incident mitigation)

**Decision**: Rejected to maintain clear separation of concerns

### Alternative 3: Manual Incident Response (No Automation)

**Description**: Keep current state, rely on human operators for incident investigation

**Pros:**
- No development cost
- No risk of incorrect automated mitigations

**Cons:**
- Loses competitive positioning vs AWS DevOps Agent
- MTTR remains hours instead of minutes
- Does not scale for enterprise customers with 24/7 operations

**Decision**: Rejected due to market competitiveness and scalability requirements

## Implementation Plan

### Phase 1: Foundation (Week 1-2)

**Deliverables:**
- [ ] CloudFormation template for `aura-deployments-{env}` DynamoDB table
- [ ] CloudFormation template for `aura-incident-investigations-{env}` DynamoDB table
- [ ] EventBridge rule for ArgoCD deployment events
- [ ] Lambda function to record deployments (`DeploymentRecorderFunction`)

**Acceptance Criteria:**
- Deployment events captured in DynamoDB within 30 seconds of ArgoCD sync
- Table supports queries by application name and timestamp

### Phase 2: RuntimeIncidentAgent Core (Week 3-4)

**Deliverables:**
- [ ] `src/agents/runtime_incident_agent.py` implementation
- [ ] Unit tests for agent methods (>80% coverage)
- [ ] Integration tests with mocked Neptune/OpenSearch
- [ ] Docker image for ECS Fargate deployment

**Acceptance Criteria:**
- Agent successfully parses CloudWatch alarm events
- Agent queries Neptune graph for code entities
- Agent searches OpenSearch for git commits
- Agent generates RCA hypothesis with confidence score

### Phase 3: Step Functions Workflow (Week 5)

**Deliverables:**
- [ ] CloudFormation template for `aura-incident-investigation-{env}` state machine
- [ ] EventBridge rules for CloudWatch alarms, PagerDuty webhooks
- [ ] SNS topic for HITL notifications (`aura-incident-alerts-{env}`)
- [ ] IAM roles for EventBridge → Step Functions → ECS

**Acceptance Criteria:**
- CloudWatch alarm triggers Step Functions execution
- ECS Fargate task runs RuntimeIncidentAgent successfully
- Investigation results stored in DynamoDB
- SNS notification sent to approvers

### Phase 4: HITL Dashboard Integration (Week 6-7)

**Deliverables:**
- [ ] React component `IncidentInvestigations.jsx`
- [ ] FastAPI endpoints in `src/api/incidents.py`
- [ ] Approve/reject workflow with DynamoDB updates

**Acceptance Criteria:**
- Dashboard displays pending investigations in table
- Users can view RCA details, code entities, deployment correlation
- Approve/reject actions update DynamoDB and send notifications

### Phase 5: MCP Observability Adapters (Week 8)

**Deliverables:**
- [ ] Datadog APM traces adapter (`datadog_query_traces`)
- [ ] Prometheus metrics adapter (`prometheus_query_range`)
- [ ] CloudWatch Logs integration (already in agent)

**Acceptance Criteria:**
- Datadog traces retrieved for incident window (Enterprise mode)
- Prometheus metrics included in RCA analysis
- Multi-vendor observability data enriches LLM prompt

### Phase 6: Testing & Validation (Week 9-10)

**Deliverables:**
- [ ] End-to-end test: CloudWatch alarm → Investigation → HITL approval
- [ ] Performance test: Handle 10 concurrent incidents
- [ ] Security audit: Verify IAM least privilege, encryption at rest
- [ ] Documentation: Update `SYSTEM_ARCHITECTURE.md`, `PROJECT_STATUS.md`

**Acceptance Criteria:**
- E2E test completes in <5 minutes
- No IAM wildcard permissions in new resources
- All DynamoDB tables use KMS encryption
- Architecture diagrams updated

## Success Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Mean Time to Investigation (MTTI)** | <5 minutes | DynamoDB timestamp: incident trigger → investigation complete |
| **RCA Confidence Score** | >70% average | Average `confidence_score` field across all investigations |
| **Code Correlation Rate** | >60% | % of investigations with `code_entities` found |
| **Deployment Correlation Rate** | >40% | % of investigations with deployments in 24-hour window |
| **HITL Approval Rate** | >80% | % of investigations approved vs rejected |
| **False Positive Rate** | <20% | % of investigations marked "not actionable" by approvers |

## Dependencies

### Internal Dependencies

- **ADR-005 (HITL Sandbox Architecture)**: Reuse HITL approval workflow patterns
- **ADR-022 (GitOps with ArgoCD)**: Deployment events source for correlation
- **ADR-023 (AgentCore Gateway)**: MCP adapters for observability platforms
- **Context Retrieval Service**: Neptune graph queries, OpenSearch semantic search
- **Anomaly Detection Service**: May trigger incident events in future

### External Dependencies

- **AWS EventBridge**: Incident event routing
- **AWS Step Functions**: Investigation workflow orchestration
- **AWS DynamoDB**: Deployments and investigations storage
- **AWS ECS Fargate**: RuntimeIncidentAgent task execution
- **AWS SNS**: HITL notifications
- **ArgoCD**: Deployment event source
- **CloudWatch**: Alarms, Logs, Metrics
- **Datadog (optional)**: APM traces in Enterprise mode
- **Prometheus (optional)**: Kubernetes metrics

## Open Questions

1. **Auto-Approval Threshold**: Should high-confidence (>90%) mitigations be auto-approved?
   - **Recommendation**: Start with manual approval for all, collect data on confidence accuracy, then enable auto-approval in Phase 2

2. **Incident Severity Filtering**: Should we investigate all CloudWatch alarms or only critical ones?
   - **Recommendation**: Use alarm tags (e.g., `severity: critical`) to filter EventBridge rules

3. **Mitigation Execution**: Who executes approved mitigations (agent, human, or hybrid)?
   - **Recommendation**: Start with manual execution (agent provides runbook), add automation in Phase 2

4. **Integration with PagerDuty**: Should we suppress PagerDuty alerts if agent auto-resolves?
   - **Recommendation**: No suppression initially, log agent resolution as PagerDuty note

5. **Cost Budget**: What's acceptable monthly cost for RuntimeIncidentAgent infrastructure?
   - **Recommendation**: Target <$100/month additional cost (Step Functions + DynamoDB + ECS)

## References

- [AWS DevOps Agent Announcement](https://aws.amazon.com/blogs/aws/aws-devops-agent-helps-you-accelerate-incident-response-and-improve-system-reliability-preview/)
- [AWS DevOps Agent with Datadog MCP](https://aws.amazon.com/blogs/devops/accelerate-autonomous-incident-resolutions-using-the-datadog-mcp-server-and-aws-devops-agent-in-preview/)
- ADR-005: HITL Sandbox Architecture
- ADR-022: GitOps for Kubernetes Deployment with ArgoCD
- ADR-023: AgentCore Gateway Integration for Multi-Agent Orchestration
- `agent-config/agents/security-code-reviewer.md`: Adaptive Security Intelligence Workflow
- `docs/design/HITL_SANDBOX_ARCHITECTURE.md`: Human-in-the-loop approval patterns
