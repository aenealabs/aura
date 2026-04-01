# ADR-072: ML-Based Anomaly Detection for Agent Behavior

## Status

Deployed

## Date

2026-01-27

## Implementation Summary

| Component | File | LOC | Tests |
|-----------|------|-----|-------|
| Anomaly Contracts | `src/services/capability_governance/anomaly_contracts.py` | ~350 | 40 |
| Statistical Detector | `src/services/capability_governance/statistical_detector.py` | ~400 | 30 |
| Honeypot Detector | `src/services/capability_governance/honeypot_detector.py` | ~350 | 28 |
| Anomaly Explainer | `src/services/capability_governance/anomaly_explainer.py` | ~250 | 15 |
| **Total** | | ~1,350 | 113 |

**Features Implemented:**
- Statistical anomaly detection (Z-score, sequence n-grams, temporal patterns)
- Honeypot capabilities with automatic quarantine (zero false positives)
- Cross-agent coordinated behavior detection
- Anomaly score fusion with configurable weights
- Natural language explanations (Bedrock-ready with fallback)
- Quarantine management with HITL release workflow
- Forensic logging and alert history

## Reviews

| Reviewer | Role | Date | Verdict |
|----------|------|------|---------|
| Pending | AWS AI SaaS Architect | - | - |
| Pending | Principal ML Engineer | - | - |
| Pending | Cybersecurity Analyst | - | - |
| Pending | Test Architect | - | - |

### Review Summary

_Awaiting review._

## Context

### Current State

ADR-066 implements static capability policies with runtime enforcement. However, policy compliance alone doesn't detect:

| Threat | Detection Gap |
|--------|---------------|
| Prompt injection | Agent calls allowed tools with malicious intent |
| Agent confusion | Unusual tool sequences indicating compromised reasoning |
| Resource exhaustion | High-frequency invocations within rate limits |
| Coordinated attacks | Multiple agents exhibiting correlated suspicious behavior |
| Capability probing | Systematic testing of policy boundaries |
| Exfiltration attempts | Legitimate tools used for unauthorized data extraction |

### Attack Patterns Invisible to Static Policies

```text
Anomaly Detection Targets:
├── Volume Anomalies
│   ├── Agent suddenly invoking 10x normal DANGEROUS tool calls
│   ├── Spike in CRITICAL capability requests near rate limit
│   └── Unusual burst patterns (100 calls in 1 minute, then silence)
├── Sequence Anomalies
│   ├── Tool invocation order deviating from learned workflows
│   ├── Skipping prerequisite tools (query before authenticate)
│   └── Unusual tool combinations not seen in training data
├── Temporal Anomalies
│   ├── Agent activity outside normal operational hours
│   ├── Sudden capability usage after long dormancy
│   └── Timing patterns matching known attack signatures
├── Context Anomalies
│   ├── Production agent using sandbox-typical patterns
│   ├── Test agent accessing production-like resources
│   └── Environment confusion indicators
└── Cross-Agent Anomalies
    ├── Multiple agents simultaneously accessing same sensitive resource
    ├── Coordinated capability escalation attempts
    └── Agent-to-agent communication pattern changes
```

### Why ML Is Necessary

Static rules cannot capture:
- Normal behavioral baselines per agent type
- Seasonal/temporal patterns in legitimate usage
- Complex multi-dimensional anomaly signatures
- Evolving attack techniques

## Decision

Implement ML-based anomaly detection for agent behavior using a phased approach: statistical baselines first, then custom ML models as needed.

## Architecture

### Detection Pipeline

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ANOMALY DETECTION PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 1: Data Collection (Existing)                                  │   │
│  │                                                                      │   │
│  │  Capability Audit Trail ──► Kinesis Data Stream                     │   │
│  │  • agent_id, tool_name, classification, decision                    │   │
│  │  • timestamp, context, parameters_hash                              │   │
│  │  • latency, parent_agent, session_id                                │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 2: Feature Engineering                                         │   │
│  │                                                                      │   │
│  │  Kinesis Data Analytics / Lambda                                    │   │
│  │  ├── Windowed aggregations (1min, 5min, 1hr)                       │   │
│  │  ├── Tool invocation counts by classification                       │   │
│  │  ├── Sequence n-grams (tool_a → tool_b → tool_c)                   │   │
│  │  ├── Time-of-day encoding                                          │   │
│  │  ├── Inter-invocation timing statistics                             │   │
│  │  └── Cross-agent correlation features                               │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 3: Anomaly Detection                                           │   │
│  │                                                                      │   │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │   │
│  │  │ Statistical     │  │ ML-Based        │  │ Rule-Based      │     │   │
│  │  │ (Phase 1)       │  │ (Phase 2)       │  │ (Honeypots)     │     │   │
│  │  │                 │  │                 │  │                 │     │   │
│  │  │ • CloudWatch    │  │ • SageMaker     │  │ • Honeypot      │     │   │
│  │  │   Anomaly Det.  │  │   Random Cut    │  │   tool access   │     │   │
│  │  │ • Z-score       │  │   Forest        │  │ • Known attack  │     │   │
│  │  │ • IQR outliers  │  │ • Isolation     │  │   patterns      │     │   │
│  │  │ • EWMA          │  │   Forest        │  │ • Policy        │     │   │
│  │  │                 │  │ • Autoencoder   │  │   violations    │     │   │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │   │
│  │           │                   │                   │                 │   │
│  │           └───────────────────┼───────────────────┘                 │   │
│  │                               │                                      │   │
│  │                               ▼                                      │   │
│  │                      Anomaly Score Fusion                           │   │
│  │                      (weighted ensemble)                            │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                      │
│       ▼                                                                      │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ Layer 4: Response                                                    │   │
│  │                                                                      │   │
│  │  Score Thresholds (ML/Statistical - NO auto-quarantine):            │   │
│  │  ├── < 0.5: Normal (log only)                                       │   │
│  │  ├── 0.5 - 0.7: Suspicious (enhanced logging)                       │   │
│  │  ├── 0.7 - 0.9: Alert (notify security team)                        │   │
│  │  └── > 0.9: Critical (rate-limit + HITL quarantine approval)        │   │
│  │                                                                      │   │
│  │  IMPORTANT: Only honeypot triggers allow auto-quarantine            │   │
│  │  (zero false positive by design). ML detections require             │   │
│  │  human-in-the-loop approval per ADR-032 autonomy framework.         │   │
│  │                                                                      │   │
│  │  Actions:                                                           │   │
│  │  ├── Log to security audit trail                                   │   │
│  │  ├── Publish to SNS (security-alerts topic)                        │   │
│  │  ├── Update agent risk score in DynamoDB                           │   │
│  │  ├── Rate-limit agent (reduce to 10% capacity on critical)         │   │
│  │  ├── Request HITL quarantine approval (Step Functions)             │   │
│  │  └── Generate explanation via Bedrock                              │   │
│  │                                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Statistical Baseline (Quick Win)

```python
# src/services/capability_governance/statistical_detector.py

from dataclasses import dataclass
from datetime import datetime, timedelta
import numpy as np

@dataclass
class StatisticalBaseline:
    agent_type: str
    tool_classification: str
    mean_hourly_count: float
    std_hourly_count: float
    mean_daily_count: float
    std_daily_count: float
    typical_sequences: list[tuple[str, str, str]]  # 3-grams
    active_hours: list[int]  # 0-23
    updated_at: datetime

class StatisticalAnomalyDetector:
    """Phase 1: Statistical anomaly detection using CloudWatch and Z-scores."""

    def __init__(self, baseline_service: BaselineService):
        self.baselines = baseline_service

    async def detect_volume_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        tool_classification: str,
        current_count: int,
        window_hours: int = 1,
    ) -> AnomalyResult:
        """
        Detect unusual invocation volume using Z-score.

        Z > 3.0 = Anomaly (99.7% confidence)
        Z > 2.5 = Suspicious
        """
        baseline = await self.baselines.get_baseline(
            agent_type=agent_type,
            tool_classification=tool_classification,
        )

        if baseline.std_hourly_count == 0:
            return AnomalyResult(is_anomaly=False, score=0.0)

        z_score = (current_count - baseline.mean_hourly_count) / baseline.std_hourly_count

        return AnomalyResult(
            is_anomaly=z_score > 3.0,
            score=min(1.0, z_score / 5.0),  # Normalize to 0-1
            anomaly_type="volume",
            details={
                "z_score": z_score,
                "current_count": current_count,
                "expected_mean": baseline.mean_hourly_count,
                "expected_std": baseline.std_hourly_count,
                "threshold": 3.0,
            },
        )

    async def detect_sequence_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        recent_tools: list[str],
    ) -> AnomalyResult:
        """
        Detect unusual tool invocation sequences using n-gram analysis.
        """
        baseline = await self.baselines.get_baseline(agent_type=agent_type)

        # Extract 3-grams from recent tools
        trigrams = [
            tuple(recent_tools[i:i+3])
            for i in range(len(recent_tools) - 2)
        ]

        # Count unseen trigrams
        unseen_count = sum(
            1 for tg in trigrams
            if tg not in baseline.typical_sequences
        )

        unseen_ratio = unseen_count / max(len(trigrams), 1)

        return AnomalyResult(
            is_anomaly=unseen_ratio > 0.5,
            score=unseen_ratio,
            anomaly_type="sequence",
            details={
                "unseen_trigrams": unseen_count,
                "total_trigrams": len(trigrams),
                "unseen_ratio": unseen_ratio,
            },
        )

    async def detect_temporal_anomaly(
        self,
        agent_id: str,
        agent_type: str,
        current_hour: int,
    ) -> AnomalyResult:
        """
        Detect activity outside normal operational hours.
        """
        baseline = await self.baselines.get_baseline(agent_type=agent_type)

        is_unusual_hour = current_hour not in baseline.active_hours

        return AnomalyResult(
            is_anomaly=is_unusual_hour,
            score=1.0 if is_unusual_hour else 0.0,
            anomaly_type="temporal",
            details={
                "current_hour": current_hour,
                "typical_hours": baseline.active_hours,
                "is_unusual": is_unusual_hour,
            },
        )
```

### Phase 2: ML-Based Detection (SageMaker - Optional/Deferred)

**Important:** SageMaker deployment is optional and should only be pursued if Phase 1 statistical detection proves insufficient. CloudWatch Anomaly Detection provides substantial value without the cost and complexity of custom ML models.

**When to consider SageMaker:**
- False positive rate from statistical methods exceeds 10%
- Complex multi-dimensional patterns require custom features
- Volume justifies $0.06/hour minimum endpoint cost

**Deployment considerations:**
- Use async analysis (not real-time blocking) initially
- SageMaker Serverless Inference has 5-30s cold start - not suitable for real-time
- Consider SageMaker Multi-Model Endpoint for cost optimization

```python
# src/services/capability_governance/ml_detector.py

import boto3
from sagemaker.predictor import Predictor

class MLAnomalyDetector:
    """Phase 2 (Optional): ML-based anomaly detection using SageMaker."""

    def __init__(self, endpoint_name: str):
        self.predictor = Predictor(
            endpoint_name=endpoint_name,
            sagemaker_session=boto3.Session().client('sagemaker-runtime'),
        )

    async def detect_anomaly(
        self,
        features: AgentBehaviorFeatures,
    ) -> AnomalyResult:
        """
        Use trained Random Cut Forest model for anomaly detection.

        Features:
        - invocations_1min, invocations_5min, invocations_1hr
        - dangerous_ratio, critical_ratio
        - sequence_entropy
        - hour_of_day, day_of_week
        - time_since_last_invocation
        - denial_rate_1hr
        """
        feature_vector = self._encode_features(features)

        response = self.predictor.predict(
            data=feature_vector,
            initial_args={'ContentType': 'text/csv'},
        )

        anomaly_score = float(response['score'])

        return AnomalyResult(
            is_anomaly=anomaly_score > 0.7,
            score=anomaly_score,
            anomaly_type="ml_ensemble",
            details={
                "model": "random_cut_forest",
                "features": features.to_dict(),
            },
        )

    def _encode_features(self, features: AgentBehaviorFeatures) -> str:
        """Encode features as CSV for SageMaker inference."""
        return ",".join([
            str(features.invocations_1min),
            str(features.invocations_5min),
            str(features.invocations_1hr),
            str(features.dangerous_ratio),
            str(features.critical_ratio),
            str(features.sequence_entropy),
            str(features.hour_of_day),
            str(features.day_of_week),
            str(features.time_since_last_invocation),
            str(features.denial_rate_1hr),
        ])
```

### Honeypot Capabilities (Immediate Win - Only Auto-Quarantine Source)

Honeypots are the ONLY detection mechanism that can trigger automatic quarantine. This is because honeypot access has zero false positives by design - if an agent attempts to access a honeypot capability, it is definitively malicious or confused.

**Rationale for honeypot-only auto-quarantine:**
- ML models have inherent false positive rates (target <5%, but non-zero)
- Auto-quarantine from ML could denial-of-service legitimate agents
- Adversaries could craft inputs that trigger ML false positives
- Honeypots are binary: any access is unauthorized (zero false positives)

```python
# src/services/capability_governance/honeypots.py

HONEYPOT_CAPABILITIES = {
    "admin_override": {
        "description": "Emergency administrative override",
        "classification": "CRITICAL",
        "legitimate_use": False,
        "alert_severity": "P1",
    },
    "export_all_credentials": {
        "description": "Bulk credential export",
        "classification": "CRITICAL",
        "legitimate_use": False,
        "alert_severity": "P1",
    },
    "disable_audit_logging": {
        "description": "Disable audit trail",
        "classification": "CRITICAL",
        "legitimate_use": False,
        "alert_severity": "P1",
    },
    "bypass_hitl_approval": {
        "description": "Skip human approval for CRITICAL operations",
        "classification": "CRITICAL",
        "legitimate_use": False,
        "alert_severity": "P1",
    },
    "access_all_tenants": {
        "description": "Cross-tenant data access",
        "classification": "CRITICAL",
        "legitimate_use": False,
        "alert_severity": "P1",
    },
}

class HoneypotDetector:
    """
    Honeypot capabilities that should never be called.

    Any invocation immediately triggers security alert + quarantine.
    Zero false positives - if called, it's malicious or confused.
    """

    async def check_honeypot_access(
        self,
        agent_id: str,
        tool_name: str,
        context: InvocationContext,
    ) -> HoneypotResult:
        if tool_name not in HONEYPOT_CAPABILITIES:
            return HoneypotResult(triggered=False)

        honeypot = HONEYPOT_CAPABILITIES[tool_name]

        # Immediate alert
        await self._publish_security_alert(
            severity=honeypot["alert_severity"],
            event_type="HONEYPOT_TRIGGERED",
            agent_id=agent_id,
            tool_name=tool_name,
            context=context,
            message=(
                f"Agent {agent_id} attempted to access honeypot capability "
                f"'{tool_name}'. This indicates potential prompt injection, "
                f"agent confusion, or malicious activity."
            ),
        )

        # Quarantine agent
        await self._quarantine_agent(
            agent_id=agent_id,
            reason="honeypot_triggered",
            tool_name=tool_name,
        )

        # Log for forensics
        await self._log_forensic_event(
            agent_id=agent_id,
            tool_name=tool_name,
            context=context,
            recent_history=await self._get_recent_invocations(agent_id, limit=50),
        )

        return HoneypotResult(
            triggered=True,
            honeypot_name=tool_name,
            action_taken="quarantine",
        )
```

### Natural Language Explanations (Bedrock)

```python
# src/services/capability_governance/anomaly_explainer.py

class AnomalyExplainer:
    """Generate human-readable explanations for anomalies using Bedrock."""

    def __init__(self, bedrock_client):
        self.bedrock = bedrock_client

    async def explain_anomaly(
        self,
        anomaly: AnomalyResult,
        agent_context: AgentContext,
        recent_history: list[CapabilityInvocation],
    ) -> str:
        """
        Generate natural language explanation of detected anomaly.
        """
        prompt = f"""You are a security analyst explaining an anomaly detected in an AI agent's behavior.

Agent: {agent_context.agent_name} (type: {agent_context.agent_type})
Anomaly Type: {anomaly.anomaly_type}
Anomaly Score: {anomaly.score:.2f}
Detection Details: {anomaly.details}

Recent Activity (last 10 invocations):
{self._format_history(recent_history[-10:])}

Provide a brief (2-3 sentence) explanation of:
1. What unusual behavior was detected
2. Why this might be concerning
3. Recommended next steps

Be concise and actionable. Do not speculate beyond the data provided."""

        response = await self.bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body={
                "prompt": prompt,
                "max_tokens": 200,
            },
        )

        return response["completion"]
```

## Implementation

### Phase 1: Statistical + Honeypots (Week 1-3)

| Task | Deliverable |
|------|-------------|
| Implement honeypot capabilities | `HoneypotDetector` class |
| Build baseline calculation job | Lambda + EventBridge |
| Implement Z-score detector | `StatisticalAnomalyDetector` |
| CloudWatch Anomaly Detection setup | Metrics and alarms |
| Alerting pipeline | SNS + Lambda |

### Phase 2: Feature Engineering (Week 3-5)

| Task | Deliverable |
|------|-------------|
| Kinesis Data Stream setup | Audit event streaming |
| Feature extraction Lambda | Windowed aggregations |
| Historical feature backfill | S3 training dataset |
| Feature store | DynamoDB or SageMaker Feature Store |

### Phase 3: Response Automation (Week 5-7)

| Task | Deliverable |
|------|-------------|
| Rate-limit workflow | Step Functions for agent throttling |
| HITL quarantine approval | Approval workflow per ADR-032 |
| Bedrock explainer | `AnomalyExplainer` class |
| Security dashboard | CloudWatch dashboards (not QuickSight) |
| Runbook integration | Automated response playbooks |

### Phase 4: ML Model (Week 8+ - Optional/Deferred)

Only pursue if Phase 1-3 statistical detection proves insufficient.

| Task | Deliverable |
|------|-------------|
| Evaluation of Phase 1-3 effectiveness | False positive/negative analysis |
| Training data preparation | Labeled anomaly dataset |
| Random Cut Forest training | SageMaker training job |
| Async model deployment | SageMaker endpoint (async, not blocking) |
| Shadow mode comparison | A/B testing vs statistical baseline |

## AWS Services

| Service | Purpose |
|---------|---------|
| **Amazon Kinesis** | Real-time audit event streaming |
| **AWS Lambda** | Feature extraction, alerting |
| **Amazon SageMaker** | ML model training and inference |
| **CloudWatch Anomaly Detection** | Statistical baseline (Phase 1) |
| **Amazon Bedrock** | Natural language explanations |
| **Amazon SNS** | Alert notifications |
| **AWS Step Functions** | Quarantine workflow orchestration |
| **Amazon DynamoDB** | Baseline storage, agent risk scores |
| **Amazon S3** | Training data, model artifacts |

## Consequences

### Positive

- **Proactive detection**: Catch attacks before damage occurs
- **Adaptive security**: Learns normal behavior, detects deviations
- **Reduced false positives**: ML models better than static thresholds
- **Explainability**: Human-readable anomaly explanations
- **Deterrence**: Honeypots catch confused or malicious agents

### Negative

- **Complexity**: ML pipeline adds operational overhead
- **Cold start**: Models need training data to be effective
- **Cost**: SageMaker endpoints incur ongoing costs
- **Tuning required**: Threshold calibration is iterative

### Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| False positives disrupting agents | Shadow mode before enforcement; tunable thresholds |
| Model drift over time | Continuous retraining pipeline; drift detection |
| Sophisticated attacks evade detection | Defense in depth; honeypots as last line |
| Explain ability accuracy | Human review of explanations; feedback loop |

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| False positive rate | <5% of anomaly alerts | Alerts marked false positive by security team |
| Honeypot detection rate | 100% | All honeypot access triggers alert (by design) |
| Mean time to alert | <60 seconds | Time from anomalous event to alert |
| Statistical baseline coverage | 100% of agent types | All agents have behavioral baselines |
| HITL approval latency | <15 minutes (P50) | Time from critical alert to quarantine decision |

## Related ADRs

- **ADR-066**: Agent Capability Governance (audit trail source)
- **ADR-070**: Policy-as-Code with GitOps (policy baseline)
- **ADR-071**: Cross-Agent Capability Graph (graph patterns)
- **ADR-032**: Autonomy Framework (HITL approval for quarantine)

## References

- [MI9: Runtime Governance Framework for Agentic AI](https://arxiv.org/abs/2508.03858) - Drift detection using Jensen-Shannon divergence and graduated containment hierarchy
- [Amazon SageMaker Random Cut Forest](https://docs.aws.amazon.com/sagemaker/latest/dg/randomcutforest.html)
- [CloudWatch Anomaly Detection](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/CloudWatch_Anomaly_Detection.html)
- [MITRE ATT&CK for AI](https://atlas.mitre.org/)
- [Honeypot Design Patterns](https://www.sans.org/white-papers/33/)
