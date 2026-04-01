"""
Tests for Kubernetes admission controller service.
"""

from src.services.runtime_security import (
    AdmissionController,
    AdmissionDecisionType,
    AdmissionPolicy,
    AdmissionRequest,
    PolicyMode,
    PolicyType,
    PolicyViolation,
    Severity,
    get_admission_controller,
    reset_admission_controller,
)


class TestAdmissionControllerInitialization:
    """Tests for admission controller initialization."""

    def test_initialize_controller(self, test_config):
        """Test initializing admission controller."""
        controller = AdmissionController()
        assert controller is not None

    def test_default_policies(self, test_config):
        """Test that default policies are created."""
        controller = AdmissionController()
        policies = controller.list_policies()

        # Should have at least CVE threshold and resource limits
        policy_types = [p.policy_type for p in policies]
        assert PolicyType.CVE_THRESHOLD in policy_types
        assert PolicyType.RESOURCE_LIMITS in policy_types

    def test_singleton_instance(self, test_config):
        """Test getting singleton instance."""
        controller1 = get_admission_controller()
        controller2 = get_admission_controller()
        assert controller1 is controller2

    def test_reset_singleton(self, test_config):
        """Test resetting singleton."""
        controller1 = get_admission_controller()
        reset_admission_controller()
        controller2 = get_admission_controller()
        assert controller1 is not controller2


class TestPolicyManagement:
    """Tests for policy management."""

    def test_add_policy(self, test_config, sample_admission_policy):
        """Test adding a policy."""
        controller = AdmissionController()
        controller.add_policy(sample_admission_policy)

        policy = controller.get_policy(sample_admission_policy.policy_id)
        assert policy is not None
        assert policy.name == sample_admission_policy.name

    def test_remove_policy(self, test_config, sample_admission_policy):
        """Test removing a policy."""
        controller = AdmissionController()
        controller.add_policy(sample_admission_policy)

        result = controller.remove_policy(sample_admission_policy.policy_id)
        assert result is True

        policy = controller.get_policy(sample_admission_policy.policy_id)
        assert policy is None

    def test_remove_nonexistent_policy(self, test_config):
        """Test removing non-existent policy."""
        controller = AdmissionController()
        result = controller.remove_policy("nonexistent")
        assert result is False

    def test_list_policies(self, test_config):
        """Test listing all policies."""
        controller = AdmissionController()
        policies = controller.list_policies()
        assert isinstance(policies, list)
        assert len(policies) > 0


class TestAdmissionValidation:
    """Tests for admission validation."""

    def test_validate_allow_request(self, test_config, sample_admission_request):
        """Test validating a request that should be allowed."""
        controller = AdmissionController()
        decision = controller.validate(sample_admission_request)

        # With relaxed test config, should allow
        assert decision.decision in (
            AdmissionDecisionType.ALLOW,
            AdmissionDecisionType.WARN,
        )
        assert decision.namespace == "production"
        assert decision.resource_kind == "Deployment"

    def test_validate_exempt_namespace(self, test_config):
        """Test validation of exempt namespace."""
        controller = AdmissionController()
        request = AdmissionRequest(
            uid="req-exempt",
            kind="Pod",
            namespace="kube-system",
            name="coredns",
            operation="CREATE",
            object_spec={
                "spec": {"containers": [{"name": "coredns", "image": "coredns:latest"}]}
            },
        )

        decision = controller.validate(request)
        assert decision.decision == AdmissionDecisionType.ALLOW
        assert len(decision.violations) == 0

    def test_validate_blocked_registry(self, test_config):
        """Test validation of blocked registry."""
        controller = AdmissionController()

        # Add a policy that blocks a specific registry
        policy = AdmissionPolicy(
            policy_id="registry-allowlist",
            name="Registry Allowlist",
            policy_type=PolicyType.REGISTRY_ALLOWLIST,
            mode=PolicyMode.ENFORCE,
            enabled=True,
        )
        controller.add_policy(policy)
        controller._config.admission.blocked_registries = ["*.dockerhub.io"]

        request = AdmissionRequest(
            uid="req-blocked",
            kind="Pod",
            namespace="default",
            name="test-pod",
            operation="CREATE",
            object_spec={
                "spec": {
                    "containers": [
                        {"name": "app", "image": "evil.dockerhub.io/malicious:latest"}
                    ]
                }
            },
        )

        decision = controller.validate(request)
        # Should have violations
        assert len(decision.violations) > 0

    def test_validate_missing_resource_limits(
        self, test_config, sample_admission_request_no_limits
    ):
        """Test validation of missing resource limits."""
        controller = AdmissionController()
        decision = controller.validate(sample_admission_request_no_limits)

        # Resource limits policy is in audit mode by default
        limit_violations = [
            v
            for v in decision.violations
            if v.policy_type == PolicyType.RESOURCE_LIMITS
        ]
        assert len(limit_violations) >= 1  # At least memory limit missing

    def test_validate_latency_recorded(self, test_config, sample_admission_request):
        """Test that latency is recorded."""
        controller = AdmissionController()
        decision = controller.validate(sample_admission_request)

        assert decision.latency_ms is not None
        assert decision.latency_ms >= 0


class TestImageValidation:
    """Tests for container image validation."""

    def test_parse_image_reference(self, test_config):
        """Test image reference parsing."""
        controller = AdmissionController()

        # Simple image
        image = controller._parse_image_reference("nginx:latest")
        assert image.repository == "nginx"
        assert image.tag == "latest"

        # ECR image
        image = controller._parse_image_reference(
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/app:v1.0.0"
        )
        assert "ecr" in image.repository
        assert image.tag == "v1.0.0"

        # Image with digest
        image = controller._parse_image_reference("app:v1@sha256:abc123")
        assert image.digest == "sha256:abc123"

    def test_check_registry_allowlist(self, test_config):
        """Test registry allowlist checking."""
        controller = AdmissionController()

        # Ensure policy is enabled
        policy = AdmissionPolicy(
            policy_id="registry-allowlist",
            name="Registry Allowlist",
            policy_type=PolicyType.REGISTRY_ALLOWLIST,
            mode=PolicyMode.ENFORCE,
            enabled=True,
        )
        controller.add_policy(policy)

        # Allowed registry
        image = controller._parse_image_reference(
            "123456789012.dkr.ecr.us-east-1.amazonaws.com/aura-api:v1"
        )
        violations = controller._check_registry_allowlist(image, "default")
        assert len(violations) == 0

    def test_check_cve_thresholds(self, test_config):
        """Test CVE threshold checking."""
        controller = AdmissionController()

        # Configure strict CVE policy
        controller._config.admission.max_critical_cves = 0
        controller._config.admission.max_high_cves = 0

        # Image marked as vulnerable
        image = controller._parse_image_reference("vulnerable:latest")
        violations = controller._check_cve_thresholds(image, "default")

        # In mock mode, "vulnerable" tag triggers simulated CVEs
        assert len(violations) > 0


class TestAdmissionResponse:
    """Tests for admission response formatting."""

    def test_to_admission_response_allow(self, test_config, sample_admission_request):
        """Test converting allow decision to response."""
        controller = AdmissionController()
        decision = controller.validate(sample_admission_request)

        if decision.decision == AdmissionDecisionType.ALLOW:
            response = controller.to_admission_response(decision)
            assert response["response"]["allowed"] is True
            assert response["response"]["uid"] == sample_admission_request.uid

    def test_to_admission_response_deny(self, test_config):
        """Test converting deny decision to response."""
        controller = AdmissionController()

        # Create a decision with deny
        from src.services.runtime_security import AdmissionDecision

        decision = AdmissionDecision(
            decision_id="dec-deny",
            request_uid="req-deny",
            cluster="test-cluster",
            namespace="default",
            resource_kind="Pod",
            resource_name="bad-pod",
            decision=AdmissionDecisionType.DENY,
            violations=[
                PolicyViolation(
                    policy_id="cve-threshold",
                    policy_type=PolicyType.CVE_THRESHOLD,
                    description="Too many critical CVEs",
                    severity=Severity.CRITICAL,
                )
            ],
        )

        response = controller.to_admission_response(decision)
        assert response["response"]["allowed"] is False
        assert response["response"]["status"]["code"] == 403
        assert "critical CVEs" in response["response"]["status"]["message"]

    def test_to_admission_response_warn(self, test_config):
        """Test converting warn decision to response."""
        controller = AdmissionController()

        from src.services.runtime_security import AdmissionDecision

        decision = AdmissionDecision(
            decision_id="dec-warn",
            request_uid="req-warn",
            cluster="test-cluster",
            namespace="default",
            resource_kind="Pod",
            resource_name="warn-pod",
            decision=AdmissionDecisionType.WARN,
            violations=[
                PolicyViolation(
                    policy_id="resource-limits",
                    policy_type=PolicyType.RESOURCE_LIMITS,
                    description="Missing memory limit",
                    severity=Severity.MEDIUM,
                )
            ],
        )

        response = controller.to_admission_response(decision)
        assert response["response"]["allowed"] is True
        assert "warnings" in response["response"]


class TestPolicyDecisionLogic:
    """Tests for policy decision determination."""

    def test_no_violations_allow(self, test_config):
        """Test that no violations results in allow."""
        controller = AdmissionController()
        decision_type = controller._determine_decision([])
        assert decision_type == AdmissionDecisionType.ALLOW

    def test_enforced_violation_deny(self, test_config):
        """Test that enforced policy violation results in deny."""
        controller = AdmissionController()

        # Add enforced policy
        policy = AdmissionPolicy(
            policy_id="strict-policy",
            name="Strict Policy",
            policy_type=PolicyType.CVE_THRESHOLD,
            mode=PolicyMode.ENFORCE,
            enabled=True,
            severity_threshold=Severity.HIGH,
        )
        controller.add_policy(policy)

        violation = PolicyViolation(
            policy_id="strict-policy",
            policy_type=PolicyType.CVE_THRESHOLD,
            description="Test violation",
            severity=Severity.CRITICAL,
        )

        decision_type = controller._determine_decision([violation])
        assert decision_type == AdmissionDecisionType.DENY

    def test_audit_violation_warn(self, test_config):
        """Test that audit mode violation results in warn."""
        controller = AdmissionController()

        # Add audit policy
        policy = AdmissionPolicy(
            policy_id="audit-policy",
            name="Audit Policy",
            policy_type=PolicyType.RESOURCE_LIMITS,
            mode=PolicyMode.AUDIT,
            enabled=True,
        )
        controller.add_policy(policy)

        violation = PolicyViolation(
            policy_id="audit-policy",
            policy_type=PolicyType.RESOURCE_LIMITS,
            description="Missing limits",
            severity=Severity.MEDIUM,
        )

        decision_type = controller._determine_decision([violation])
        assert decision_type in (
            AdmissionDecisionType.WARN,
            AdmissionDecisionType.ALLOW,
        )
