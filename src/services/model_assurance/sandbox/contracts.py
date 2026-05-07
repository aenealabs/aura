"""Evaluation sandbox contracts (ADR-088 Phase 2.4).

The evaluation sandbox is a tightly-restricted execution environment
where the Oracle's Lambda judges run the candidate model against the
golden test set. The sandbox is the only place untrusted candidate-
model output executes during the assurance pipeline, so the security
posture is intentionally narrower than the ADR-083 production
sandbox: zero network egress, no production credentials, ephemeral
storage only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class SandboxLifecycleState(Enum):
    """Lifecycle states the provisioner walks through."""

    PROVISIONING = "provisioning"
    READY = "ready"
    EXECUTING = "executing"
    TEARDOWN = "teardown"
    DESTROYED = "destroyed"
    FAILED = "failed"


class EgressDecision(Enum):
    """One egress check outcome.

    ALLOW          — destination is on the explicit allowlist
                     (Bedrock endpoint in this region).
    DENY           — destination not on the allowlist; security
                     group + NACL must block.
    SUSPICIOUS     — destination matches a partially-known pattern
                     (e.g. AWS IP range but not Bedrock); flag for
                     audit but still deny.
    """

    ALLOW = "allow"
    DENY = "deny"
    SUSPICIOUS = "suspicious"


@dataclass(frozen=True)
class EgressEndpoint:
    """One endpoint the sandbox is permitted to reach."""

    host: str                  # e.g. "bedrock.us-east-1.amazonaws.com"
    port: int = 443
    description: str = ""


# Bedrock-only allowlist used for the v1 evaluation sandbox.
# Endpoints are region-templated; the actual hosts are filled in by
# the CloudFormation deployment with the deployment-region's
# Bedrock endpoint.
DEFAULT_EGRESS_ALLOWLIST: tuple[EgressEndpoint, ...] = (
    EgressEndpoint(
        host="bedrock-runtime.{region}.amazonaws.com",
        port=443,
        description="Bedrock invocation endpoint (regional)",
    ),
    EgressEndpoint(
        host="bedrock.{region}.amazonaws.com",
        port=443,
        description="Bedrock control-plane endpoint (regional)",
    ),
)


@dataclass(frozen=True)
class EgressPolicy:
    """Egress allowlist for an evaluation sandbox.

    All other destinations must be denied at the security-group +
    NACL level. The policy is consumed by both the Python check
    (validate_destination) and the CloudFormation security-group
    builder so the IaC stays in sync with the runtime check.
    """

    allowlist: tuple[EgressEndpoint, ...] = DEFAULT_EGRESS_ALLOWLIST
    region: str = "us-east-1"

    def validate_destination(
        self, host: str, port: int = 443
    ) -> EgressDecision:
        host = host.lower()
        for ep in self.allowlist:
            allowed_host = ep.host.format(region=self.region).lower()
            if host == allowed_host and port == ep.port:
                return EgressDecision.ALLOW
        # Suspicious heuristic: AWS-namespace destination but not on
        # our allowlist. Worth flagging in audit even though we'll
        # deny anyway.
        if "amazonaws.com" in host:
            return EgressDecision.SUSPICIOUS
        return EgressDecision.DENY

    def with_region(self, region: str) -> "EgressPolicy":
        return EgressPolicy(allowlist=self.allowlist, region=region)


@dataclass(frozen=True)
class IAMConstraint:
    """The IAM constraints the sandbox runs under.

    ``forbidden_actions`` is checked at provisioning time against
    the sandbox role's policy document. ``required_session_tag``
    forces a session-tag scope so even a misconfigured role can't
    accidentally see production data — the production data stores
    additionally require the tag on every Get/Describe call.
    """

    forbidden_actions: tuple[str, ...] = (
        "secretsmanager:GetSecretValue",
        "ssm:GetParameter*",
        "rds:*",
        "dynamodb:Scan",
        "dynamodb:Query",
        "neptune-db:*",
        "es:ESHttpGet",
        "es:ESHttpPost",
    )
    required_session_tag: str = "aura:context=evaluation-sandbox"
    deny_production_access: bool = True


@dataclass(frozen=True)
class SandboxSpec:
    """Declarative spec for one evaluation sandbox.

    The provisioner reads the spec, validates against policy,
    creates the ephemeral environment, and tears it down on
    completion regardless of outcome (no orphan storage).
    """

    sandbox_id: str
    candidate_model_id: str
    egress_policy: EgressPolicy
    iam_constraint: IAMConstraint = field(default_factory=IAMConstraint)
    ephemeral_storage_mb: int = 4096        # max scratch space
    cpu_units: int = 2048                   # 2 vCPU
    memory_mb: int = 4096                   # 4 GB
    max_runtime_seconds: int = 1_800        # 30 min hard cap
    enable_runtime_baseline_monitoring: bool = True   # ADR-083 hook
    enable_container_escape_detection: bool = True    # ADR-077 hook

    def __post_init__(self) -> None:
        if not self.sandbox_id:
            raise ValueError("SandboxSpec.sandbox_id is required")
        if self.ephemeral_storage_mb <= 0:
            raise ValueError("ephemeral_storage_mb must be positive")
        if self.max_runtime_seconds <= 0:
            raise ValueError("max_runtime_seconds must be positive")


@dataclass(frozen=True)
class SandboxOutcome:
    """Result of one sandbox lifecycle.

    Always returned, even on failure, so the orchestrator's audit
    trail is complete and the operator can see the lifecycle state
    transitions.
    """

    sandbox_id: str
    state: SandboxLifecycleState
    egress_violations: tuple[str, ...] = ()
    iam_violations: tuple[str, ...] = ()
    error: str | None = None
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def is_clean(self) -> bool:
        """Sandbox completed successfully with no policy violations."""
        return (
            self.state is SandboxLifecycleState.DESTROYED
            and not self.egress_violations
            and not self.iam_violations
            and self.error is None
        )

    def to_audit_dict(self) -> dict:
        return {
            "sandbox_id": self.sandbox_id,
            "state": self.state.value,
            "egress_violations": list(self.egress_violations),
            "iam_violations": list(self.iam_violations),
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "duration_seconds": (
                self.completed_at - self.started_at
            ).total_seconds(),
        }
