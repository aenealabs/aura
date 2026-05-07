"""End-to-end SandboxProvisioner lifecycle tests (ADR-088 Phase 2.4)."""

from __future__ import annotations

import pytest

from src.services.model_assurance.sandbox import (
    EgressPolicy,
    IAMConstraint,
    IAMPolicyDocument,
    SandboxLifecycleState,
    SandboxProvisioner,
    SandboxSpec,
)


def _spec(sandbox_id: str = "sb-1") -> SandboxSpec:
    return SandboxSpec(
        sandbox_id=sandbox_id,
        candidate_model_id="m1",
        egress_policy=EgressPolicy(region="us-east-1"),
    )


class TestSpecValidation:
    def test_empty_id_rejected(self) -> None:
        with pytest.raises(ValueError, match="sandbox_id"):
            SandboxSpec(
                sandbox_id="",
                candidate_model_id="m",
                egress_policy=EgressPolicy(),
            )

    def test_zero_storage_rejected(self) -> None:
        with pytest.raises(ValueError, match="ephemeral_storage"):
            SandboxSpec(
                sandbox_id="sb",
                candidate_model_id="m",
                egress_policy=EgressPolicy(),
                ephemeral_storage_mb=0,
            )

    def test_zero_runtime_rejected(self) -> None:
        with pytest.raises(ValueError, match="max_runtime"):
            SandboxSpec(
                sandbox_id="sb",
                candidate_model_id="m",
                egress_policy=EgressPolicy(),
                max_runtime_seconds=0,
            )


class TestLifecycleHappyPath:
    def test_no_op_run_destroys_cleanly(self) -> None:
        out = SandboxProvisioner().execute(_spec())
        assert out.state is SandboxLifecycleState.DESTROYED
        assert out.is_clean is True

    def test_planned_egress_validated(self) -> None:
        out = SandboxProvisioner().execute(
            _spec(),
            planned_egress=[
                ("bedrock-runtime.us-east-1.amazonaws.com", 443),
            ],
        )
        assert out.state is SandboxLifecycleState.DESTROYED


class TestEgressGate:
    def test_egress_gate_blocks_provisioning(self) -> None:
        out = SandboxProvisioner().execute(
            _spec(),
            planned_egress=[("evil.com", 443)],
        )
        assert out.state is SandboxLifecycleState.FAILED
        assert "evil.com:443" in out.egress_violations

    def test_partial_denial_lists_each(self) -> None:
        out = SandboxProvisioner().execute(
            _spec(),
            planned_egress=[
                ("bedrock-runtime.us-east-1.amazonaws.com", 443),
                ("attacker.example.com", 80),
            ],
        )
        assert "attacker.example.com:80" in out.egress_violations


class TestIAMGate:
    def test_iam_violations_block_provisioning(self) -> None:
        bad_policy = IAMPolicyDocument(
            actions=("secretsmanager:GetSecretValue",),
        )
        out = SandboxProvisioner(
            iam_policy_fetcher=lambda spec: bad_policy,
        ).execute(_spec())
        assert out.state is SandboxLifecycleState.FAILED
        assert "secretsmanager:GetSecretValue" in out.iam_violations

    def test_clean_iam_passes(self) -> None:
        clean_policy = IAMPolicyDocument(actions=("s3:GetObject",))
        out = SandboxProvisioner(
            iam_policy_fetcher=lambda spec: clean_policy,
        ).execute(_spec())
        assert out.state is SandboxLifecycleState.DESTROYED


class TestTeardownInvariant:
    def test_teardown_runs_on_work_failure(self) -> None:
        teardown_calls = []

        def teardown(spec, handle):
            teardown_calls.append(spec.sandbox_id)

        def boom(spec, handle):
            raise RuntimeError("oracle worker crashed")

        out = SandboxProvisioner(
            teardown_fn=teardown,
        ).execute(_spec("sb-fail"), work=boom)
        assert out.state is SandboxLifecycleState.FAILED
        assert "oracle worker crashed" in (out.error or "")
        assert teardown_calls == ["sb-fail"]

    def test_teardown_runs_on_success(self) -> None:
        calls = []

        def teardown(spec, handle):
            calls.append("teardown")

        out = SandboxProvisioner(teardown_fn=teardown).execute(_spec())
        assert out.state is SandboxLifecycleState.DESTROYED
        assert calls == ["teardown"]

    def test_teardown_failure_does_not_change_outcome(self) -> None:
        """A teardown that itself raises must not mask the work outcome."""
        def teardown(spec, handle):
            raise RuntimeError("teardown error")

        out = SandboxProvisioner(teardown_fn=teardown).execute(_spec())
        assert out.state is SandboxLifecycleState.DESTROYED


class TestProvisionFailure:
    def test_provision_exception_returns_failed(self) -> None:
        def provision(spec):
            raise RuntimeError("ECS service unavailable")

        out = SandboxProvisioner(provision_fn=provision).execute(_spec())
        assert out.state is SandboxLifecycleState.FAILED
        assert "ECS service unavailable" in (out.error or "")

    def test_provision_failure_skips_teardown(self) -> None:
        teardown_calls = []

        def provision(spec):
            raise RuntimeError("boom")

        def teardown(spec, handle):
            teardown_calls.append("ran")

        SandboxProvisioner(
            provision_fn=provision, teardown_fn=teardown,
        ).execute(_spec())
        # No handle to teardown if provisioning never succeeded.
        assert teardown_calls == []


class TestCustomDimensions:
    def test_spec_accepts_custom_resource_sizes(self) -> None:
        spec = SandboxSpec(
            sandbox_id="sb-big",
            candidate_model_id="m1",
            egress_policy=EgressPolicy(),
            ephemeral_storage_mb=20480,  # 20GB
            cpu_units=8192,
            memory_mb=16384,
            max_runtime_seconds=3600,
        )
        assert spec.ephemeral_storage_mb == 20480

    def test_runtime_baseline_monitoring_default_on(self) -> None:
        spec = _spec()
        assert spec.enable_runtime_baseline_monitoring is True

    def test_container_escape_detection_default_on(self) -> None:
        spec = _spec()
        assert spec.enable_container_escape_detection is True


class TestAuditDict:
    def test_audit_dict_includes_violations(self) -> None:
        out = SandboxProvisioner().execute(
            _spec(),
            planned_egress=[("evil.com", 443)],
        )
        d = out.to_audit_dict()
        assert d["state"] == "failed"
        assert d["egress_violations"] == ["evil.com:443"]
        assert "duration_seconds" in d
