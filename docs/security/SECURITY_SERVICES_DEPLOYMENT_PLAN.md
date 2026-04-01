# Security Services Deployment Plan

**Document Version:** 1.0
**Created:** 2025-12-12
**Author:** Project Aura Infrastructure Team
**Status:** Ready for Review

---

## Executive Summary

This document provides a comprehensive deployment plan for the new security services added to Project Aura. The services implement defense-in-depth security controls covering input validation, secrets detection, audit logging, rate limiting, LLM prompt sanitization, and secure command execution.

### Services Overview

| Service | Purpose | AWS Dependencies |
|---------|---------|------------------|
| `input_validation_service.py` | SQL/XSS/Command injection detection | CloudWatch Logs |
| `secrets_detection_service.py` | 30+ secret patterns + entropy analysis | CloudWatch Logs, SNS |
| `security_audit_service.py` | CMMC/SOC2/NIST compliance logging | CloudWatch Logs, DynamoDB |
| `security_alerts_service.py` | HITL workflow integration | SNS, EventBridge, DynamoDB |
| `api_rate_limiter.py` | Token bucket rate limiting | ElastiCache Redis (future), CloudWatch |
| `llm_prompt_sanitizer.py` | Prompt injection prevention | CloudWatch Logs, Bedrock Guardrails |
| `secure_command_executor.py` | Sandboxed command execution | CloudWatch Logs |

---

## 1. New AWS Resources Required

### 1.1 CloudWatch Log Groups

Create dedicated log groups for security event streams with extended retention for compliance.

**Template Addition:** `deploy/cloudformation/monitoring.yaml`

```yaml
# Security Audit Log Group
SecurityAuditLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub '/aura/${Environment}/security/audit'
    RetentionInDays: !If [IsProduction, 365, 90]
    KmsKeyId: !ImportValue
      Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
    Tags:
      - Key: Compliance
        Value: 'CMMC-SOC2-NIST'

# Security Threats Log Group
SecurityThreatsLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub '/aura/${Environment}/security/threats'
    RetentionInDays: !If [IsProduction, 365, 90]
    KmsKeyId: !ImportValue
      Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'

# Rate Limiting Log Group
RateLimitingLogGroup:
  Type: AWS::Logs::LogGroup
  Properties:
    LogGroupName: !Sub '/aura/${Environment}/security/rate-limiting'
    RetentionInDays: 30
```

**Rationale:** Separate log groups enable:
- Independent retention policies per compliance requirement
- Targeted CloudWatch Insights queries
- Isolated metric filters and alarms
- Cost-effective log storage tiers

### 1.2 SNS Topics for Security Alerts

**Template Addition:** `deploy/cloudformation/monitoring.yaml`

```yaml
# Security Alerts SNS Topic (P1/P2 alerts)
SecurityAlertsTopic:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub '${ProjectName}-security-alerts-${Environment}'
    DisplayName: 'Aura Security Alerts'
    KmsMasterKeyId: !ImportValue
      Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
    Subscription:
      - Endpoint: !Ref SecurityAlertEmail
        Protocol: email
    Tags:
      - Key: AlertType
        Value: Security

# Security Incidents SNS Topic (P1 Critical only)
SecurityIncidentsTopic:
  Type: AWS::SNS::Topic
  Properties:
    TopicName: !Sub '${ProjectName}-security-incidents-${Environment}'
    DisplayName: 'Aura Security Incidents - URGENT'
    KmsMasterKeyId: !ImportValue
      Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
    Subscription:
      - Endpoint: !Ref SecurityIncidentEmail
        Protocol: email
      # PagerDuty integration for production
      - !If
        - IsProduction
        - Endpoint: !Ref PagerDutyEndpoint
          Protocol: https
        - !Ref AWS::NoValue
```

**New Parameters Required:**
```yaml
SecurityAlertEmail:
  Type: String
  Description: Email for security alerts (P1-P3)

SecurityIncidentEmail:
  Type: String
  Description: Email for critical security incidents (P1 only)

PagerDutyEndpoint:
  Type: String
  Default: ''
  Description: PagerDuty HTTPS endpoint for P1 incidents (production only)
```

### 1.3 DynamoDB Tables for Audit Persistence

**Template Addition:** `deploy/cloudformation/dynamodb.yaml`

```yaml
# Security Audit Events Table
SecurityAuditEventsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub '${ProjectName}-security-audit-events-${Environment}'
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: eventId
        AttributeType: S
      - AttributeName: timestamp
        AttributeType: N
      - AttributeName: eventType
        AttributeType: S
      - AttributeName: userId
        AttributeType: S
      - AttributeName: severity
        AttributeType: S
    KeySchema:
      - AttributeName: eventId
        KeyType: HASH
      - AttributeName: timestamp
        KeyType: RANGE
    GlobalSecondaryIndexes:
      - IndexName: EventTypeIndex
        KeySchema:
          - AttributeName: eventType
            KeyType: HASH
          - AttributeName: timestamp
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
      - IndexName: UserIdIndex
        KeySchema:
          - AttributeName: userId
            KeyType: HASH
          - AttributeName: timestamp
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
      - IndexName: SeverityIndex
        KeySchema:
          - AttributeName: severity
            KeyType: HASH
          - AttributeName: timestamp
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
    StreamSpecification:
      StreamViewType: NEW_IMAGE
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    SSESpecification:
      SSEEnabled: true
      SSEType: KMS
      KMSMasterKeyId: !ImportValue
        Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true
    Tags:
      - Key: Compliance
        Value: 'CMMC-SOC2-NIST'

# Security HITL Requests Table
SecurityHITLRequestsTable:
  Type: AWS::DynamoDB::Table
  Properties:
    TableName: !Sub '${ProjectName}-security-hitl-requests-${Environment}'
    BillingMode: PAY_PER_REQUEST
    AttributeDefinitions:
      - AttributeName: requestId
        AttributeType: S
      - AttributeName: alertId
        AttributeType: S
      - AttributeName: status
        AttributeType: S
      - AttributeName: priority
        AttributeType: S
      - AttributeName: createdAt
        AttributeType: N
    KeySchema:
      - AttributeName: requestId
        KeyType: HASH
    GlobalSecondaryIndexes:
      - IndexName: AlertIdIndex
        KeySchema:
          - AttributeName: alertId
            KeyType: HASH
        Projection:
          ProjectionType: ALL
      - IndexName: StatusPriorityIndex
        KeySchema:
          - AttributeName: status
            KeyType: HASH
          - AttributeName: priority
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
      - IndexName: PriorityCreatedIndex
        KeySchema:
          - AttributeName: priority
            KeyType: HASH
          - AttributeName: createdAt
            KeyType: RANGE
        Projection:
          ProjectionType: ALL
    StreamSpecification:
      StreamViewType: NEW_AND_OLD_IMAGES
    PointInTimeRecoverySpecification:
      PointInTimeRecoveryEnabled: true
    SSESpecification:
      SSEEnabled: true
      SSEType: KMS
    TimeToLiveSpecification:
      AttributeName: ttl
      Enabled: true
```

### 1.4 EventBridge Event Bus

**Template Addition:** `deploy/cloudformation/a2a-infrastructure.yaml` or new `security-events.yaml`

```yaml
# Security Events Bus
SecurityEventBus:
  Type: AWS::Events::EventBus
  Properties:
    Name: !Sub '${ProjectName}-security-events-${Environment}'
    Tags:
      - Key: Project
        Value: !Ref ProjectName

# Rule: Route P1 Critical Alerts to Incident Response
CriticalAlertRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-critical-security-alert-${Environment}'
    Description: Route P1 critical security alerts to incident response
    EventBusName: !Ref SecurityEventBus
    EventPattern:
      source:
        - 'aura.security'
      detail-type:
        - 'SecurityAlert'
      detail:
        priority:
          - 'P1'
    State: ENABLED
    Targets:
      - Id: SNSIncidents
        Arn: !Ref SecurityIncidentsTopic
      - Id: IncidentResponseLambda
        Arn: !ImportValue
          Fn::Sub: '${ProjectName}-incident-response-lambda-arn-${Environment}'

# Rule: Route High Severity to Security Team
HighSeverityAlertRule:
  Type: AWS::Events::Rule
  Properties:
    Name: !Sub '${ProjectName}-high-severity-alert-${Environment}'
    Description: Route P2 high severity alerts to security team
    EventBusName: !Ref SecurityEventBus
    EventPattern:
      source:
        - 'aura.security'
      detail-type:
        - 'SecurityAlert'
      detail:
        priority:
          - 'P2'
    State: ENABLED
    Targets:
      - Id: SNSAlerts
        Arn: !Ref SecurityAlertsTopic
```

### 1.5 CloudWatch Metric Filters and Alarms

**Template Addition:** `deploy/cloudformation/realtime-monitoring.yaml`

```yaml
# Metric Filter: Injection Attempts
InjectionAttemptMetricFilter:
  Type: AWS::Logs::MetricFilter
  Properties:
    FilterPattern: '{ $.event_type = "input.injection.attempt" || $.event_type = "input.xss.attempt" }'
    LogGroupName: !Ref SecurityThreatsLogGroup
    MetricTransformations:
      - MetricName: InjectionAttempts
        MetricNamespace: Aura/Security
        MetricValue: '1'
        Unit: Count

# Metric Filter: Prompt Injection Attempts
PromptInjectionMetricFilter:
  Type: AWS::Logs::MetricFilter
  Properties:
    FilterPattern: '{ $.event_type = "threat.prompt_injection" }'
    LogGroupName: !Ref SecurityThreatsLogGroup
    MetricTransformations:
      - MetricName: PromptInjectionAttempts
        MetricNamespace: Aura/Security
        MetricValue: '1'
        Unit: Count

# Metric Filter: Secrets Exposure
SecretsExposureMetricFilter:
  Type: AWS::Logs::MetricFilter
  Properties:
    FilterPattern: '{ $.event_type = "threat.secrets.exposure" }'
    LogGroupName: !Ref SecurityThreatsLogGroup
    MetricTransformations:
      - MetricName: SecretsExposureAttempts
        MetricNamespace: Aura/Security
        MetricValue: '1'
        Unit: Count

# Metric Filter: Rate Limit Exceeded
RateLimitExceededMetricFilter:
  Type: AWS::Logs::MetricFilter
  Properties:
    FilterPattern: '{ $.event_type = "rate_limit.exceeded" }'
    LogGroupName: !Ref RateLimitingLogGroup
    MetricTransformations:
      - MetricName: RateLimitExceeded
        MetricNamespace: Aura/Security
        MetricValue: '1'
        Unit: Count

# Alarm: High Injection Attempt Rate
HighInjectionAttemptAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-high-injection-attempts-${Environment}'
    AlarmDescription: High rate of injection attempts detected
    MetricName: InjectionAttempts
    Namespace: Aura/Security
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 10
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref SecurityAlertsTopic
    TreatMissingData: notBreaching

# Alarm: Any Secrets Exposure
SecretsExposureAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-secrets-exposure-${Environment}'
    AlarmDescription: Secrets exposure detected - immediate review required
    MetricName: SecretsExposureAttempts
    Namespace: Aura/Security
    Statistic: Sum
    Period: 60
    EvaluationPeriods: 1
    Threshold: 0
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref SecurityIncidentsTopic
    TreatMissingData: notBreaching

# Alarm: High Rate Limit Events
HighRateLimitAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: !Sub '${ProjectName}-high-rate-limit-events-${Environment}'
    AlarmDescription: Unusually high rate limit events - possible DDoS
    MetricName: RateLimitExceeded
    Namespace: Aura/Security
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 2
    Threshold: 100
    ComparisonOperator: GreaterThanThreshold
    AlarmActions:
      - !Ref SecurityAlertsTopic
```

---

## 2. Updates to Existing CloudFormation Templates

### 2.1 IAM Role Updates (`iam.yaml`)

Add permissions for the API service to write to security resources:

```yaml
# Add to AuraAPIServicePolicy
- Sid: SecurityAuditAccess
  Effect: Allow
  Action:
    - logs:CreateLogStream
    - logs:PutLogEvents
    - logs:DescribeLogStreams
  Resource:
    - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/aura/${Environment}/security/*'

- Sid: SecurityDynamoDBAccess
  Effect: Allow
  Action:
    - dynamodb:PutItem
    - dynamodb:GetItem
    - dynamodb:Query
    - dynamodb:UpdateItem
  Resource:
    - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-security-audit-events-${Environment}'
    - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-security-audit-events-${Environment}/index/*'
    - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-security-hitl-requests-${Environment}'
    - !Sub 'arn:${AWS::Partition}:dynamodb:${AWS::Region}:${AWS::AccountId}:table/${ProjectName}-security-hitl-requests-${Environment}/index/*'

- Sid: SecuritySNSPublish
  Effect: Allow
  Action:
    - sns:Publish
  Resource:
    - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-security-alerts-${Environment}'
    - !Sub 'arn:${AWS::Partition}:sns:${AWS::Region}:${AWS::AccountId}:${ProjectName}-security-incidents-${Environment}'

- Sid: SecurityEventBridgePublish
  Effect: Allow
  Action:
    - events:PutEvents
  Resource:
    - !Sub 'arn:${AWS::Partition}:events:${AWS::Region}:${AWS::AccountId}:event-bus/${ProjectName}-security-events-${Environment}'
```

### 2.2 Secrets Manager Updates (`secrets.yaml`)

Add security service configuration secret:

```yaml
# Security Services Configuration
SecurityServicesConfigSecret:
  Type: AWS::SecretsManager::Secret
  Properties:
    Name: !Sub '${ProjectName}/${Environment}/security-services-config'
    Description: Security services configuration
    SecretString: !Sub |
      {
        "input_validation": {
          "strict_mode": false,
          "max_string_length": 10000,
          "log_threats": true
        },
        "secrets_detection": {
          "entropy_threshold": 4.5,
          "enable_entropy_detection": true,
          "min_secret_length": 8
        },
        "rate_limiting": {
          "public_limit": 100,
          "standard_limit": 60,
          "sensitive_limit": 10,
          "admin_limit": 5,
          "critical_limit": 2
        },
        "prompt_sanitization": {
          "strict_mode": false,
          "max_prompt_length": 100000
        },
        "audit_logging": {
          "enable_console": true,
          "enable_file": false,
          "log_retention_days": ${!If [IsProduction, 365, 90]}
        }
      }
```

### 2.3 Monitoring Dashboard Updates (`monitoring.yaml`)

Add security metrics panel to main dashboard:

```yaml
# Add to DashboardBody widgets array
{
  "type": "metric",
  "x": 0,
  "y": 12,
  "width": 12,
  "height": 6,
  "properties": {
    "metrics": [
      ["Aura/Security", "InjectionAttempts", {"stat": "Sum", "color": "#d62728"}],
      [".", "PromptInjectionAttempts", {"stat": "Sum", "color": "#ff7f0e"}],
      [".", "SecretsExposureAttempts", {"stat": "Sum", "color": "#9467bd"}],
      [".", "RateLimitExceeded", {"stat": "Sum", "color": "#8c564b"}]
    ],
    "period": 300,
    "stat": "Sum",
    "region": "${AWS::Region}",
    "title": "Security Events",
    "view": "timeSeries",
    "stacked": false
  }
}
```

---

## 3. EKS Deployment Considerations

### 3.1 ConfigMaps

Create ConfigMap for security service configuration:

**File:** `deploy/kubernetes/security/security-config.yaml`

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: aura-security-config
  namespace: aura
  labels:
    app: aura-api
    component: security
data:
  # Security Services Configuration
  INPUT_VALIDATION_STRICT_MODE: "false"
  INPUT_VALIDATION_MAX_LENGTH: "10000"
  SECRETS_DETECTION_ENABLED: "true"
  SECRETS_DETECTION_ENTROPY_THRESHOLD: "4.5"
  RATE_LIMIT_ENABLED: "true"
  PROMPT_SANITIZATION_STRICT_MODE: "false"
  PROMPT_SANITIZATION_MAX_LENGTH: "100000"
  AUDIT_LOGGING_ENABLED: "true"

  # AWS Resource References (populated by deployment script)
  SECURITY_SNS_TOPIC_ARN: ""  # Set during deployment
  SECURITY_EVENTBRIDGE_BUS: "aura-security-events-${ENVIRONMENT}"
  SECURITY_AUDIT_TABLE: "aura-security-audit-events-${ENVIRONMENT}"
  SECURITY_HITL_TABLE: "aura-security-hitl-requests-${ENVIRONMENT}"
```

### 3.2 Secrets (External Secrets Operator)

**File:** `deploy/kubernetes/security/security-secrets.yaml`

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: aura-security-secrets
  namespace: aura
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: aws-secrets-manager
    kind: ClusterSecretStore
  target:
    name: aura-security-secrets
    creationPolicy: Owner
  data:
    - secretKey: SECURITY_SERVICES_CONFIG
      remoteRef:
        key: aura/${ENVIRONMENT}/security-services-config
```

### 3.3 API Deployment Updates

Update the API deployment to mount security configuration:

**File:** `deploy/kubernetes/api/deployment.yaml` (additions)

```yaml
spec:
  template:
    spec:
      containers:
        - name: aura-api
          envFrom:
            - configMapRef:
                name: aura-security-config
            - secretRef:
                name: aura-security-secrets
          env:
            # Security log group references
            - name: SECURITY_AUDIT_LOG_GROUP
              value: "/aura/${ENVIRONMENT}/security/audit"
            - name: SECURITY_THREATS_LOG_GROUP
              value: "/aura/${ENVIRONMENT}/security/threats"
            - name: RATE_LIMIT_LOG_GROUP
              value: "/aura/${ENVIRONMENT}/security/rate-limiting"
```

### 3.4 NetworkPolicy Updates

Ensure API pods can reach security-related AWS services:

**File:** `deploy/kubernetes/security/network-policy.yaml`

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: aura-api-security-egress
  namespace: aura
spec:
  podSelector:
    matchLabels:
      app: aura-api
  policyTypes:
    - Egress
  egress:
    # Allow CloudWatch Logs
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
    # Allow DynamoDB
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
    # Allow SNS
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
```

**Note:** The above NetworkPolicy allows egress to 0.0.0.0/0 on 443. In production, use VPC endpoints and restrict to specific CIDR blocks.

---

## 4. Integration with Existing Observability Stack

### 4.1 OpenTelemetry Collector Updates

Add security metrics to the OTEL collector configuration:

**File:** `deploy/config/otel-collector-config.yaml` (additions)

```yaml
receivers:
  # Add custom security metrics receiver
  prometheus/security:
    config:
      scrape_configs:
        - job_name: 'aura-security-metrics'
          scrape_interval: 30s
          static_configs:
            - targets: ['localhost:9090']
          metric_relabel_configs:
            - source_labels: [__name__]
              regex: 'security_.*'
              action: keep

processors:
  attributes/security:
    actions:
      - key: service.name
        value: aura-security
        action: upsert
      - key: environment
        value: ${ENVIRONMENT}
        action: upsert

exporters:
  awscloudwatch/security:
    namespace: Aura/Security
    region: ${AWS_REGION}
    log_group_name: /aura/${ENVIRONMENT}/security/metrics
    dimension_rollup_option: NoDimensionRollup

service:
  pipelines:
    metrics/security:
      receivers: [prometheus/security]
      processors: [attributes/security, batch]
      exporters: [awscloudwatch/security]
```

### 4.2 Prometheus ServiceMonitor

**File:** `deploy/kubernetes/monitoring/security-servicemonitor.yaml`

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: aura-security-metrics
  namespace: aura
  labels:
    release: prometheus
spec:
  selector:
    matchLabels:
      app: aura-api
  endpoints:
    - port: metrics
      interval: 30s
      path: /metrics/security
      scheme: http
```

### 4.3 Grafana Dashboard

Create a dedicated security dashboard JSON that can be imported:

**File:** `deploy/config/grafana/security-dashboard.json`

Key panels to include:
- Injection attempts over time (by type)
- Rate limiting events by tier
- Secrets detection findings
- Prompt injection attempts
- HITL request queue depth
- Security audit event volume
- Authentication success/failure ratio

---

## 5. Deployment Order and Dependencies

### 5.1 Deployment Sequence

Execute deployments in the following order to respect dependencies:

| Phase | Stack/Resource | Depends On | Buildspec |
|-------|----------------|------------|-----------|
| 1 | KMS Key (if not exists) | None | buildspec-foundation.yml |
| 2 | CloudWatch Log Groups | KMS Key | buildspec-observability.yml |
| 3 | SNS Topics | KMS Key | buildspec-observability.yml |
| 4 | DynamoDB Tables | KMS Key | buildspec-data.yml |
| 5 | EventBridge Event Bus | SNS Topics | buildspec-serverless.yml |
| 6 | IAM Policy Updates | DynamoDB, SNS, EventBridge | buildspec-foundation.yml |
| 7 | Secrets Manager | None | buildspec-observability.yml |
| 8 | Metric Filters & Alarms | Log Groups, SNS | buildspec-observability.yml |
| 9 | EKS ConfigMaps/Secrets | Secrets Manager | Manual kubectl / ArgoCD |
| 10 | API Deployment Update | All above | Manual kubectl / ArgoCD |

### 5.2 Pre-Deployment Checklist

- [ ] Verify KMS key exists and has correct permissions
- [ ] Confirm SNS subscription emails are valid
- [ ] Validate IAM role has sufficient permissions for new resources
- [ ] Test DynamoDB table access from local environment
- [ ] Verify VPC endpoints for CloudWatch, DynamoDB, SNS exist
- [ ] Backup current EKS deployment manifests
- [ ] Document current CloudWatch alarm thresholds

### 5.3 Deployment Commands

```bash
# Phase 1-2: Foundation and Log Groups
aws codebuild start-build --project-name aura-foundation-deploy-dev
aws codebuild start-build --project-name aura-observability-deploy-dev

# Phase 3-4: SNS and DynamoDB
aws codebuild start-build --project-name aura-data-deploy-dev

# Phase 5-6: EventBridge and IAM Updates
aws codebuild start-build --project-name aura-serverless-deploy-dev
aws codebuild start-build --project-name aura-foundation-deploy-dev  # IAM updates

# Phase 7-8: Secrets and Monitoring
aws codebuild start-build --project-name aura-observability-deploy-dev

# Phase 9-10: EKS Updates (via ArgoCD or kubectl)
kubectl apply -f deploy/kubernetes/security/
kubectl rollout restart deployment/aura-api -n aura
```

---

## 6. Rollback Strategy

### 6.1 CloudFormation Rollback

CloudFormation automatically rolls back failed deployments. For manual rollback:

```bash
# Rollback to previous stack version
aws cloudformation cancel-update-stack --stack-name aura-monitoring-dev

# Delete newly created resources (if needed)
aws cloudformation delete-stack --stack-name aura-security-events-dev

# Restore from backup
aws cloudformation create-stack \
  --stack-name aura-monitoring-dev \
  --template-body file://backup/monitoring-backup.yaml \
  --parameters file://backup/monitoring-params.json
```

### 6.2 EKS Rollback

```bash
# Rollback API deployment to previous revision
kubectl rollout undo deployment/aura-api -n aura

# Rollback to specific revision
kubectl rollout undo deployment/aura-api -n aura --to-revision=3

# Verify rollback status
kubectl rollout status deployment/aura-api -n aura
```

### 6.3 DynamoDB Table Rollback

DynamoDB tables have Point-in-Time Recovery enabled. To restore:

```bash
# Restore to point in time
aws dynamodb restore-table-to-point-in-time \
  --source-table-name aura-security-audit-events-dev \
  --target-table-name aura-security-audit-events-dev-restored \
  --restore-date-time "2025-12-12T10:00:00Z"
```

### 6.4 Rollback Decision Matrix

| Symptom | Severity | Action |
|---------|----------|--------|
| API 500 errors spike | Critical | Immediate EKS rollback |
| CloudWatch log delivery fails | High | Verify IAM permissions, rollback if needed |
| DynamoDB throttling | Medium | Increase capacity, no rollback |
| SNS delivery failures | Medium | Check subscription, no rollback |
| Rate limiter false positives | Low | Adjust thresholds, no rollback |

---

## 7. Post-Deployment Verification

### 7.1 Health Check Endpoints

After deployment, verify the following endpoints:

```bash
# API Health Check
curl -X GET https://api.aura.dev.aenealabs.com/health

# Security Stats Endpoint (internal)
curl -X GET https://api.aura.dev.aenealabs.com/api/v1/security/stats \
  -H "Authorization: Bearer ${API_TOKEN}"
```

### 7.2 CloudWatch Verification

```bash
# Verify log groups exist
aws logs describe-log-groups --log-group-name-prefix /aura/dev/security

# Verify metric filters
aws logs describe-metric-filters --log-group-name /aura/dev/security/threats

# Verify alarms
aws cloudwatch describe-alarms --alarm-name-prefix aura-
```

### 7.3 DynamoDB Verification

```bash
# Verify tables exist
aws dynamodb describe-table --table-name aura-security-audit-events-dev
aws dynamodb describe-table --table-name aura-security-hitl-requests-dev

# Test write access
aws dynamodb put-item \
  --table-name aura-security-audit-events-dev \
  --item '{"eventId": {"S": "test-event-123"}, "timestamp": {"N": "1702400000"}}'
```

### 7.4 Integration Test Suite

Run the security services integration tests:

```bash
# Run security service tests
pytest tests/services/test_security_services_integration.py -v

# Run API security tests
pytest tests/api/test_security_middleware.py -v
pytest tests/api/test_security_integration.py -v
```

---

## 8. Cost Estimates

### 8.1 Monthly Cost Breakdown (dev environment)

| Resource | Unit Cost | Estimated Usage | Monthly Cost |
|----------|-----------|-----------------|--------------|
| CloudWatch Logs (3 groups) | $0.50/GB ingested | ~5 GB/month | $2.50 |
| CloudWatch Log Retention (90 days) | $0.03/GB stored | ~15 GB stored | $0.45 |
| SNS (2 topics) | $0.50/million requests | ~10K requests | $0.01 |
| DynamoDB (2 tables, on-demand) | $1.25/million WCU | ~50K writes | $0.06 |
| DynamoDB Storage | $0.25/GB | ~1 GB | $0.25 |
| EventBridge | $1.00/million events | ~10K events | $0.01 |
| CloudWatch Alarms (5 alarms) | $0.10/alarm/month | 5 alarms | $0.50 |
| **Total (dev)** | | | **~$4/month** |

### 8.2 Production Cost Estimate

Production costs will be higher due to:
- 365-day log retention (~4x storage cost)
- Higher event volume (~10x)
- Additional PagerDuty SNS subscriptions

**Estimated Production Cost:** ~$25-50/month

### 8.3 Cost Optimization Recommendations

1. **Log Sampling:** For high-volume environments, consider sampling INFO-level events
2. **DynamoDB TTL:** Set TTL on audit events (90 days dev, 365 days prod)
3. **S3 Archive:** Move old audit logs to S3 Glacier after 30 days
4. **Metric Resolution:** Use 1-minute resolution only for critical metrics

---

## 9. Security Considerations

### 9.1 Data Classification

| Data Element | Classification | Encryption | Retention |
|--------------|----------------|------------|-----------|
| Audit Event IDs | Internal | KMS at-rest | 1 year |
| User IDs | PII | KMS at-rest | 1 year |
| IP Addresses | PII (hashed) | KMS at-rest | 90 days |
| Threat Details | Sensitive | KMS at-rest | 1 year |
| Secrets Findings | Highly Sensitive | KMS + redacted | 1 year |

### 9.2 Access Control

- **DynamoDB Tables:** Accessible only via IRSA-authenticated API pods
- **CloudWatch Logs:** Write-only from API, read via CloudWatch console (admin only)
- **SNS Topics:** Publish from API, subscribe restricted to verified endpoints
- **EventBridge:** Publish from API, targets restricted to approved Lambda/SNS

### 9.3 Compliance Mapping

| Control | CMMC | SOC 2 | NIST 800-53 |
|---------|------|-------|-------------|
| Audit Logging | AU.L2-3.3.1 | CC7.2 | AU-2, AU-3 |
| Log Retention | AU.L2-3.3.2 | CC7.2 | AU-11 |
| Alerting | IR.L2-3.6.1 | CC7.3 | IR-4 |
| Access Control | AC.L2-3.1.1 | CC6.1 | AC-2 |

---

## 10. Appendix

### 10.1 Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `SECURITY_SNS_TOPIC_ARN` | SNS topic for security alerts | Required |
| `SECURITY_EVENTBRIDGE_BUS` | EventBridge bus name | `aura-security-events-{env}` |
| `HITL_TABLE_NAME` | DynamoDB table for HITL requests | `aura-security-hitl-requests-{env}` |
| `SECURITY_AUDIT_TABLE` | DynamoDB table for audit events | `aura-security-audit-events-{env}` |
| `INPUT_VALIDATION_STRICT_MODE` | Block on any threat detection | `false` |
| `RATE_LIMIT_ENABLED` | Enable rate limiting | `true` |
| `PROMPT_SANITIZATION_STRICT_MODE` | Block suspicious prompts | `false` |

### 10.2 CloudFormation Outputs to Export

```yaml
Outputs:
  SecurityAuditLogGroupArn:
    Value: !GetAtt SecurityAuditLogGroup.Arn
    Export:
      Name: !Sub '${ProjectName}-security-audit-log-group-arn-${Environment}'

  SecurityAlertsSNSTopicArn:
    Value: !Ref SecurityAlertsTopic
    Export:
      Name: !Sub '${ProjectName}-security-alerts-sns-arn-${Environment}'

  SecurityEventBusArn:
    Value: !GetAtt SecurityEventBus.Arn
    Export:
      Name: !Sub '${ProjectName}-security-eventbus-arn-${Environment}'

  SecurityAuditTableArn:
    Value: !GetAtt SecurityAuditEventsTable.Arn
    Export:
      Name: !Sub '${ProjectName}-security-audit-table-arn-${Environment}'
```

### 10.3 Related Documentation

- `/docs/design/HITL_SANDBOX_ARCHITECTURE.md` - HITL workflow integration
- `/docs/reference/TESTING_STRATEGY.md` - Security service test patterns
- `/agent-config/agents/security-code-reviewer.md` - Security review guidelines
- `/docs/cloud-strategy/GOVCLOUD_READINESS_TRACKER.md` - GovCloud service availability

---

**End of Document**
