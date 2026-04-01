# Phase 2: Cloud Runtime Security

**Duration:** Weeks 11-20
**Market Focus:** Wiz, Google, Microsoft
**Dependencies:** Phase 1 SBOM services, existing `ResourceTopologyMapper`

---

## Service 1: Kubernetes Admission Controller

### Overview

A validating admission webhook that integrates with EKS/AKS/GKE to block vulnerable deployments at the API server level, before workloads are scheduled.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Kubernetes Admission Flow                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   kubectl apply                                                          │
│        │                                                                 │
│        ▼                                                                 │
│   ┌─────────────────┐                                                   │
│   │ K8s API Server  │                                                   │
│   └────────┬────────┘                                                   │
│            │ ValidatingWebhookConfiguration                             │
│            ▼                                                             │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │              Aura Admission Controller (Pod)                     │   │
│   │  ┌──────────────────────────────────────────────────────────┐   │   │
│   │  │ Layer 1: Image Signature Verification                     │   │   │
│   │  │ - Cosign signature check                                  │   │   │
│   │  │ - Attestation verification from Phase 1                   │   │   │
│   │  └──────────────────────────────────────────────────────────┘   │   │
│   │                         │ PASS                                   │   │
│   │                         ▼                                        │   │
│   │  ┌──────────────────────────────────────────────────────────┐   │   │
│   │  │ Layer 2: Vulnerability Scan                               │   │   │
│   │  │ - Check SBOM against CVE database                         │   │   │
│   │  │ - Block CRITICAL/HIGH based on policy                     │   │   │
│   │  │ - Grace period for existing workloads                     │   │   │
│   │  └──────────────────────────────────────────────────────────┘   │   │
│   │                         │ PASS                                   │   │
│   │                         ▼                                        │   │
│   │  ┌──────────────────────────────────────────────────────────┐   │   │
│   │  │ Layer 3: Security Context Validation                      │   │   │
│   │  │ - runAsNonRoot enforcement                                │   │   │
│   │  │ - Privileged container blocking                           │   │   │
│   │  │ - Host namespace restrictions                             │   │   │
│   │  └──────────────────────────────────────────────────────────┘   │   │
│   │                         │ PASS                                   │
│   │                         ▼                                        │   │
│   │  ┌──────────────────────────────────────────────────────────┐   │   │
│   │  │ Layer 4: Policy Enforcement (OPA/Gatekeeper)              │   │   │
│   │  │ - Custom organization policies                            │   │   │
│   │  │ - Compliance rule validation                              │   │   │
│   │  └──────────────────────────────────────────────────────────┘   │   │
│   │                         │                                        │   │
│   │                    ┌────┴────┐                                   │   │
│   │                    ▼         ▼                                   │   │
│   │              [ALLOW]     [DENY + Reason]                         │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│        → Audit log to CloudWatch/Neptune                                │
│        → Alert to SNS if DENY                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### API Contract

```python
# src/services/k8s_admission/admission_controller.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import base64
import json


class AdmissionDecision(str, Enum):
    """Admission webhook decision."""
    ALLOW = "allow"
    DENY = "deny"
    WARN = "warn"  # Allow with warning annotation


class DenyReason(str, Enum):
    """Reasons for denying admission."""
    UNSIGNED_IMAGE = "unsigned_image"
    CRITICAL_CVE = "critical_cve"
    HIGH_CVE = "high_cve"
    PRIVILEGED_CONTAINER = "privileged_container"
    ROOT_USER = "root_user"
    HOST_NETWORK = "host_network"
    HOST_PID = "host_pid"
    POLICY_VIOLATION = "policy_violation"
    NO_RESOURCE_LIMITS = "no_resource_limits"
    FORBIDDEN_REGISTRY = "forbidden_registry"


@dataclass
class AdmissionRequest:
    """Kubernetes AdmissionReview request."""
    uid: str
    kind: dict  # {"group": "", "version": "v1", "kind": "Pod"}
    resource: dict  # {"group": "", "version": "v1", "resource": "pods"}
    name: str
    namespace: str
    operation: str  # CREATE, UPDATE, DELETE
    user_info: dict
    object: dict  # The K8s resource being admitted
    old_object: Optional[dict] = None  # For UPDATE operations
    dry_run: bool = False


@dataclass
class AdmissionResponse:
    """Kubernetes AdmissionReview response."""
    uid: str
    allowed: bool
    status: Optional[dict] = None  # {"code": 403, "message": "..."}
    warnings: list[str] = field(default_factory=list)
    patch: Optional[str] = None  # Base64 JSON Patch
    patch_type: Optional[str] = None  # "JSONPatch"

    def to_admission_review(self) -> dict:
        """Convert to AdmissionReview response format."""
        response = {
            "apiVersion": "admission.k8s.io/v1",
            "kind": "AdmissionReview",
            "response": {
                "uid": self.uid,
                "allowed": self.allowed,
            }
        }
        if self.status:
            response["response"]["status"] = self.status
        if self.warnings:
            response["response"]["warnings"] = self.warnings
        if self.patch:
            response["response"]["patch"] = self.patch
            response["response"]["patchType"] = self.patch_type
        return response


@dataclass
class VulnerabilityScanResult:
    """Result of image vulnerability scan."""
    image: str
    digest: str
    sbom_id: Optional[str]
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    top_cves: list[dict]  # Top 5 most severe
    scan_timestamp: datetime
    within_grace_period: bool = False


@dataclass
class AdmissionPolicy:
    """Admission policy configuration."""
    id: str
    name: str
    namespaces: list[str]  # Empty = all namespaces
    block_unsigned_images: bool = True
    max_critical_cves: int = 0
    max_high_cves: int = 5
    cve_grace_period_days: int = 7
    require_non_root: bool = True
    block_privileged: bool = True
    block_host_network: bool = True
    block_host_pid: bool = True
    allowed_registries: list[str] = field(default_factory=list)
    custom_opa_policies: list[str] = field(default_factory=list)


class K8sAdmissionController:
    """
    Kubernetes Validating Admission Controller.

    Integrates with:
    - Phase 1 SBOM Attestation Service for signature verification
    - SemanticGuardrailsEngine (ADR-065) for policy evaluation
    - Neptune for audit trail
    """

    def __init__(
        self,
        sbom_service: "SBOMAttestationService",
        vuln_scanner: "VulnerabilityScanner",
        policy_engine: "OPAPolicyEngine",
        neptune_client: "NeptuneGraphService",
    ):
        self.sbom_service = sbom_service
        self.vuln_scanner = vuln_scanner
        self.policy_engine = policy_engine
        self.neptune = neptune_client

    async def validate(
        self,
        request: AdmissionRequest,
    ) -> AdmissionResponse:
        """
        Validate admission request through all layers.

        Returns AdmissionResponse with decision and reasoning.
        """
        pass

    async def _verify_image_signature(
        self,
        image: str,
        policy: AdmissionPolicy,
    ) -> tuple[bool, Optional[str]]:
        """Verify image has valid cosign signature."""
        pass

    async def _scan_image_vulnerabilities(
        self,
        image: str,
        policy: AdmissionPolicy,
    ) -> VulnerabilityScanResult:
        """Scan image for vulnerabilities using SBOM."""
        pass

    async def _validate_security_context(
        self,
        pod_spec: dict,
        policy: AdmissionPolicy,
    ) -> list[DenyReason]:
        """Validate pod security context."""
        pass

    async def _evaluate_opa_policies(
        self,
        resource: dict,
        policy: AdmissionPolicy,
    ) -> list[dict]:
        """Evaluate custom OPA policies."""
        pass

    async def _audit_decision(
        self,
        request: AdmissionRequest,
        response: AdmissionResponse,
        scan_result: Optional[VulnerabilityScanResult],
    ) -> None:
        """Record admission decision in Neptune audit graph."""
        pass
```

### FastAPI Webhook Endpoint

```python
# src/api/k8s_admission_endpoints.py

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import structlog

router = APIRouter(prefix="/api/v1/admission", tags=["admission"])
logger = structlog.get_logger(__name__)


@router.post("/validate")
async def validate_admission(
    request: Request,
    controller: K8sAdmissionController = Depends(get_admission_controller),
):
    """
    Kubernetes ValidatingWebhook endpoint.

    Receives AdmissionReview requests and returns decisions.
    """
    body = await request.json()

    if body.get("kind") != "AdmissionReview":
        raise HTTPException(400, "Expected AdmissionReview")

    admission_request = AdmissionRequest(
        uid=body["request"]["uid"],
        kind=body["request"]["kind"],
        resource=body["request"]["resource"],
        name=body["request"].get("name", ""),
        namespace=body["request"].get("namespace", "default"),
        operation=body["request"]["operation"],
        user_info=body["request"]["userInfo"],
        object=body["request"].get("object"),
        old_object=body["request"].get("oldObject"),
        dry_run=body["request"].get("dryRun", False),
    )

    logger.info(
        "admission_request_received",
        uid=admission_request.uid,
        kind=admission_request.kind,
        namespace=admission_request.namespace,
        operation=admission_request.operation,
    )

    response = await controller.validate(admission_request)

    logger.info(
        "admission_decision",
        uid=response.uid,
        allowed=response.allowed,
        warnings=len(response.warnings),
    )

    return JSONResponse(content=response.to_admission_review())


@router.get("/health")
async def health():
    """Health check for admission controller."""
    return {"status": "healthy"}


@router.get("/policies")
async def list_policies(
    controller: K8sAdmissionController = Depends(get_admission_controller),
):
    """List configured admission policies."""
    pass


@router.post("/policies")
async def create_policy(
    policy: AdmissionPolicy,
    controller: K8sAdmissionController = Depends(get_admission_controller),
):
    """Create new admission policy."""
    pass
```

### Kubernetes Manifests

```yaml
# deploy/kubernetes/admission-controller/base/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: aura-admission-controller
  namespace: aura-system
  labels:
    app: aura-admission-controller
spec:
  replicas: 3
  selector:
    matchLabels:
      app: aura-admission-controller
  template:
    metadata:
      labels:
        app: aura-admission-controller
    spec:
      serviceAccountName: aura-admission-controller
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      containers:
        - name: controller
          image: ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/aura-admission-controller:latest
          ports:
            - containerPort: 8443
              name: https
          env:
            - name: NEPTUNE_ENDPOINT
              valueFrom:
                configMapKeyRef:
                  name: aura-config
                  key: neptune_endpoint
            - name: SBOM_SERVICE_URL
              value: "http://aura-sbom-service.aura-system:8080"
          resources:
            requests:
              cpu: 100m
              memory: 256Mi
            limits:
              cpu: 500m
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /api/v1/admission/health
              port: 8443
              scheme: HTTPS
            initialDelaySeconds: 10
            periodSeconds: 10
          readinessProbe:
            httpGet:
              path: /api/v1/admission/health
              port: 8443
              scheme: HTTPS
            initialDelaySeconds: 5
            periodSeconds: 5
          volumeMounts:
            - name: tls-certs
              mountPath: /etc/admission-controller/tls
              readOnly: true
      volumes:
        - name: tls-certs
          secret:
            secretName: aura-admission-controller-tls

---
apiVersion: v1
kind: Service
metadata:
  name: aura-admission-controller
  namespace: aura-system
spec:
  selector:
    app: aura-admission-controller
  ports:
    - port: 443
      targetPort: 8443
      name: https

---
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: aura-admission-controller
webhooks:
  - name: validate.aura.aenealabs.com
    clientConfig:
      service:
        name: aura-admission-controller
        namespace: aura-system
        path: /api/v1/admission/validate
      caBundle: ${CA_BUNDLE}
    rules:
      - operations: ["CREATE", "UPDATE"]
        apiGroups: [""]
        apiVersions: ["v1"]
        resources: ["pods"]
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["apps"]
        apiVersions: ["v1"]
        resources: ["deployments", "replicasets", "statefulsets", "daemonsets"]
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["batch"]
        apiVersions: ["v1"]
        resources: ["jobs", "cronjobs"]
    admissionReviewVersions: ["v1"]
    sideEffects: None
    timeoutSeconds: 10
    failurePolicy: Fail  # or Ignore for non-blocking mode
    namespaceSelector:
      matchExpressions:
        - key: aura.io/admission
          operator: NotIn
          values: ["disabled"]
```

---

## Service 2: Runtime-to-Code Correlator

### Overview

Links cloud runtime events (CloudTrail, K8s audit logs, GuardDuty findings) back to the specific IaC templates, application code, and commits that caused them.

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Runtime-to-Code Correlation Flow                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │ CloudTrail  │  │ K8s Audit   │  │ GuardDuty   │  │ Config      │    │
│  │ Events      │  │ Logs        │  │ Findings    │  │ Violations  │    │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │                │            │
│         └────────────────┼────────────────┼────────────────┘            │
│                          ▼                                               │
│              ┌───────────────────────┐                                  │
│              │ EventBridge Bus       │                                  │
│              │ (aura-runtime-events) │                                  │
│              └───────────┬───────────┘                                  │
│                          │                                               │
│                          ▼                                               │
│              ┌───────────────────────────────────────────────────────┐  │
│              │           Runtime-to-Code Correlator                   │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Step 1: Event Parsing & Normalization           │  │  │
│              │  │ - Extract resource ARN/identifiers              │  │  │
│              │  │ - Normalize across event sources                │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              │                          │                             │  │
│              │                          ▼                             │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Step 2: Resource Topology Lookup                │  │  │
│              │  │ - Query ResourceTopologyMapper (existing)       │  │  │
│              │  │ - Resolve resource to deployment/stack          │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              │                          │                             │  │
│              │                          ▼                             │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Step 3: IaC Template Identification             │  │  │
│              │  │ - Map CloudFormation logical ID                 │  │  │
│              │  │ - Find Terraform resource address               │  │  │
│              │  │ - Identify Kubernetes manifest                  │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              │                          │                             │  │
│              │                          ▼                             │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Step 4: Git Blame Analysis                      │  │  │
│              │  │ - Find file + line in repository                │  │  │
│              │  │ - Git blame to identify commit/author           │  │  │
│              │  │ - Link PR/issue if available                    │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              │                          │                             │  │
│              │                          ▼                             │  │
│              │  ┌─────────────────────────────────────────────────┐  │  │
│              │  │ Step 5: Neptune Graph Update                    │  │  │
│              │  │ - Create RuntimeEvent vertex                    │  │  │
│              │  │ - Create CAUSED_BY edge to CodeCommit           │  │  │
│              │  │ - Link to affected Resource vertices            │  │  │
│              │  └─────────────────────────────────────────────────┘  │  │
│              └───────────────────────────────────────────────────────┘  │
│                          │                                               │
│                          ▼                                               │
│              ┌───────────────────────────────────────────────────────┐  │
│              │                Correlation Result                      │  │
│              │                                                        │  │
│              │  RuntimeEvent                                          │  │
│              │    ├── source: cloudtrail                              │  │
│              │    ├── event_type: CreateSecurityGroup                 │  │
│              │    ├── resource_arn: arn:aws:ec2:...:sg-xxx            │  │
│              │    └── CAUSED_BY ──────────────────────────────────┐   │  │
│              │                                                    │   │  │
│              │  IaCResource                                       │   │  │
│              │    ├── file: deploy/cloudformation/networking.yaml │   │  │
│              │    ├── line: 245                                   │   │  │
│              │    ├── logical_id: EKSNodeSecurityGroup            │   │  │
│              │    └── DEFINED_IN ─────────────────────────────┐   │   │  │
│              │                                                │   │   │  │
│              │  CodeCommit ◄──────────────────────────────────┘   │   │  │
│              │    ├── sha: abc123                                 │   │  │
│              │    ├── author: jane@company.com                    │   │  │
│              │    ├── message: "Update EKS node SG rules"         │   │  │
│              │    └── pr_number: #456                             │   │  │
│              └───────────────────────────────────────────────────────┘  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### API Contract

```python
# src/services/runtime_correlation/correlator_service.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventSource(str, Enum):
    """Runtime event sources."""
    CLOUDTRAIL = "cloudtrail"
    K8S_AUDIT = "k8s_audit"
    GUARDDUTY = "guardduty"
    CONFIG = "aws_config"
    SECURITYHUB = "securityhub"
    CLOUDWATCH_ALARM = "cloudwatch_alarm"


class CorrelationConfidence(str, Enum):
    """Confidence level of correlation."""
    HIGH = "high"  # Direct resource match
    MEDIUM = "medium"  # Inferred from naming/tags
    LOW = "low"  # Heuristic match
    UNKNOWN = "unknown"  # Could not correlate


@dataclass
class RuntimeEvent:
    """Normalized runtime event."""
    id: str
    source: EventSource
    event_type: str
    resource_arn: Optional[str]
    resource_type: str
    account_id: str
    region: str
    timestamp: datetime
    actor: Optional[str]  # IAM principal or K8s user
    raw_event: dict
    severity: Optional[str]


@dataclass
class IaCLocation:
    """Location in Infrastructure as Code."""
    repository: str
    file_path: str
    line_start: int
    line_end: int
    logical_id: Optional[str]  # CloudFormation
    resource_address: Optional[str]  # Terraform
    iac_type: str  # cloudformation, terraform, kubernetes


@dataclass
class GitBlameResult:
    """Result of git blame analysis."""
    commit_sha: str
    author_name: str
    author_email: str
    commit_date: datetime
    commit_message: str
    pr_number: Optional[int]
    pr_url: Optional[str]


@dataclass
class CorrelationResult:
    """Complete runtime-to-code correlation."""
    event: RuntimeEvent
    confidence: CorrelationConfidence
    iac_location: Optional[IaCLocation]
    git_blame: Optional[GitBlameResult]
    related_resources: list[str]  # Other affected resource ARNs
    remediation_suggestions: list[str]
    correlation_path: list[str]  # How correlation was made


class RuntimeCodeCorrelator:
    """
    Correlates runtime events to source code.

    Uses:
    - ResourceTopologyMapper for resource discovery
    - Neptune graph for relationship traversal
    - Git integration for blame analysis
    """

    def __init__(
        self,
        topology_mapper: "ResourceTopologyMapper",
        neptune_client: "NeptuneGraphService",
        git_service: "GitIngestionService",
    ):
        self.topology = topology_mapper
        self.neptune = neptune_client
        self.git = git_service

    async def correlate_event(
        self,
        event: RuntimeEvent,
    ) -> CorrelationResult:
        """Correlate single runtime event to code."""
        pass

    async def correlate_batch(
        self,
        events: list[RuntimeEvent],
    ) -> list[CorrelationResult]:
        """Correlate batch of events efficiently."""
        pass

    async def find_related_events(
        self,
        iac_location: IaCLocation,
        time_range_hours: int = 24,
    ) -> list[RuntimeEvent]:
        """Find runtime events caused by specific IaC."""
        pass

    async def generate_remediation(
        self,
        correlation: CorrelationResult,
    ) -> str:
        """Generate remediation code/config suggestion."""
        pass

    async def _resolve_resource_to_iac(
        self,
        resource_arn: str,
    ) -> Optional[IaCLocation]:
        """Resolve AWS resource ARN to IaC definition."""
        pass

    async def _git_blame_iac_file(
        self,
        iac_location: IaCLocation,
    ) -> Optional[GitBlameResult]:
        """Run git blame on IaC file."""
        pass
```

### CloudFormation Template

```yaml
# deploy/cloudformation/runtime-correlator.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 9.2 - Runtime-to-Code Correlation Infrastructure'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]

Resources:
  # EventBridge Rule for CloudTrail Events
  CloudTrailEventRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${ProjectName}-cloudtrail-correlation-${Environment}'
      Description: Forward CloudTrail events for correlation
      EventBusName: default
      EventPattern:
        source:
          - aws.cloudtrail
        detail-type:
          - AWS API Call via CloudTrail
        detail:
          eventSource:
            - ec2.amazonaws.com
            - ecs.amazonaws.com
            - eks.amazonaws.com
            - rds.amazonaws.com
            - s3.amazonaws.com
            - iam.amazonaws.com
            - lambda.amazonaws.com
      State: ENABLED
      Targets:
        - Id: CorrelationQueue
          Arn: !GetAtt CorrelationQueue.Arn

  # EventBridge Rule for GuardDuty Findings
  GuardDutyEventRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${ProjectName}-guardduty-correlation-${Environment}'
      Description: Forward GuardDuty findings for correlation
      EventBusName: default
      EventPattern:
        source:
          - aws.guardduty
        detail-type:
          - GuardDuty Finding
      State: ENABLED
      Targets:
        - Id: CorrelationQueue
          Arn: !GetAtt CorrelationQueue.Arn

  # EventBridge Rule for Config Compliance
  ConfigEventRule:
    Type: AWS::Events::Rule
    Properties:
      Name: !Sub '${ProjectName}-config-correlation-${Environment}'
      Description: Forward Config compliance changes for correlation
      EventBusName: default
      EventPattern:
        source:
          - aws.config
        detail-type:
          - Config Rules Compliance Change
      State: ENABLED
      Targets:
        - Id: CorrelationQueue
          Arn: !GetAtt CorrelationQueue.Arn

  # SQS Queue for Correlation Processing
  CorrelationQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-runtime-correlation-${Environment}'
      VisibilityTimeout: 300
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !ImportValue
        Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt CorrelationDLQ.Arn
        maxReceiveCount: 3

  CorrelationDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-runtime-correlation-dlq-${Environment}'
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !ImportValue
        Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'

  # SQS Queue Policy for EventBridge
  CorrelationQueuePolicy:
    Type: AWS::SQS::QueuePolicy
    Properties:
      Queues:
        - !Ref CorrelationQueue
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: events.amazonaws.com
            Action: sqs:SendMessage
            Resource: !GetAtt CorrelationQueue.Arn

  # DynamoDB Table for Correlation Cache
  CorrelationCacheTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-correlation-cache-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: resource_arn
          AttributeType: S
        - AttributeName: correlation_id
          AttributeType: S
      KeySchema:
        - AttributeName: resource_arn
          KeyType: HASH
        - AttributeName: correlation_id
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
      SSESpecification:
        SSEEnabled: true
        SSEType: KMS
        KMSMasterKeyId: !ImportValue
          Fn::Sub: '${ProjectName}-kms-key-arn-${Environment}'

Outputs:
  CorrelationQueueArn:
    Value: !GetAtt CorrelationQueue.Arn
    Export:
      Name: !Sub '${ProjectName}-correlation-queue-arn-${Environment}'

  CorrelationQueueUrl:
    Value: !Ref CorrelationQueue
    Export:
      Name: !Sub '${ProjectName}-correlation-queue-url-${Environment}'
```

---

## Service 3: Container Escape Detector

### Overview

Real-time monitoring for container breakout attempts including privilege escalation, namespace escapes, and kernel exploits.

### API Contract

```python
# src/services/container_security/escape_detector.py

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class EscapeAttemptType(str, Enum):
    """Types of container escape attempts."""
    PRIVILEGE_ESCALATION = "privilege_escalation"
    NAMESPACE_ESCAPE = "namespace_escape"
    KERNEL_EXPLOIT = "kernel_exploit"
    VOLUME_MOUNT_ABUSE = "volume_mount_abuse"
    PROCESS_INJECTION = "process_injection"
    CAPABILITIES_ABUSE = "capabilities_abuse"
    CGROUP_ESCAPE = "cgroup_escape"


class DetectionSeverity(str, Enum):
    """Severity of detected escape attempt."""
    CRITICAL = "critical"  # Active exploitation
    HIGH = "high"  # Strong indicators
    MEDIUM = "medium"  # Suspicious activity
    LOW = "low"  # Potential concern


@dataclass
class EscapeAttempt:
    """Detected container escape attempt."""
    id: str
    type: EscapeAttemptType
    severity: DetectionSeverity
    container_id: str
    pod_name: str
    namespace: str
    node_name: str
    process_name: str
    process_pid: int
    syscall: Optional[str]
    capabilities_used: list[str]
    timestamp: datetime
    evidence: dict
    mitre_attack_ids: list[str]


@dataclass
class ContainerSecurityProfile:
    """Security profile for container monitoring."""
    allowed_syscalls: list[str]
    denied_capabilities: list[str]
    max_privilege_level: str
    file_integrity_paths: list[str]
    network_monitoring_enabled: bool


class ContainerEscapeDetector:
    """
    Detects container escape attempts in real-time.

    Uses:
    - eBPF-based syscall monitoring (Falco integration)
    - Audit log analysis
    - Process tree analysis
    - Network anomaly detection
    """

    async def start_monitoring(
        self,
        cluster_id: str,
        profile: ContainerSecurityProfile,
    ) -> str:
        """Start monitoring cluster for escape attempts."""
        pass

    async def stop_monitoring(
        self,
        monitoring_id: str,
    ) -> None:
        """Stop monitoring session."""
        pass

    async def get_attempts(
        self,
        cluster_id: str,
        start_time: datetime,
        end_time: datetime,
        severity: Optional[DetectionSeverity] = None,
    ) -> list[EscapeAttempt]:
        """Query detected escape attempts."""
        pass

    async def analyze_process_tree(
        self,
        container_id: str,
    ) -> dict:
        """Analyze process tree for suspicious patterns."""
        pass

    async def correlate_to_vulnerability(
        self,
        attempt: EscapeAttempt,
    ) -> Optional[str]:
        """Link escape attempt to known CVE."""
        pass
```

---

## Estimated Metrics

| Metric | Target |
|--------|--------|
| Lines of Code | 13,500 |
| Test Count | 1,500 |
| Test Coverage | 85%+ |
| CloudFormation Templates | 5 |
| API Endpoints | 18 |
| Neptune Vertex Types | 3 |
| Neptune Edge Types | 5 |
| Kubernetes Manifests | 8 |
