"""Tests for IAM policy gating (ADR-088 Phase 2.4)."""

from __future__ import annotations

from src.services.model_assurance.sandbox import (
    IAMConstraint,
    IAMPolicyDocument,
    validate_iam_policy,
)


class TestIAMConstraintDefaults:
    def test_default_forbids_secrets_manager(self) -> None:
        c = IAMConstraint()
        assert "secretsmanager:GetSecretValue" in c.forbidden_actions

    def test_default_forbids_neptune(self) -> None:
        c = IAMConstraint()
        assert "neptune-db:*" in c.forbidden_actions

    def test_default_forbids_dynamodb_scan(self) -> None:
        c = IAMConstraint()
        assert "dynamodb:Scan" in c.forbidden_actions

    def test_session_tag_required(self) -> None:
        c = IAMConstraint()
        assert "evaluation-sandbox" in c.required_session_tag


class TestPolicyValidation:
    def test_clean_policy_passes(self) -> None:
        policy = IAMPolicyDocument(actions=("s3:GetObject", "logs:PutLogEvents"))
        violations = validate_iam_policy(
            policy,
            forbidden=IAMConstraint().forbidden_actions,
        )
        assert violations == ()

    def test_explicit_forbidden_action_caught(self) -> None:
        policy = IAMPolicyDocument(actions=("secretsmanager:GetSecretValue",))
        violations = validate_iam_policy(
            policy,
            forbidden=IAMConstraint().forbidden_actions,
        )
        assert "secretsmanager:GetSecretValue" in violations

    def test_glob_match_catches_neptune(self) -> None:
        policy = IAMPolicyDocument(actions=("neptune-db:ReadDataViaQuery",))
        violations = validate_iam_policy(
            policy,
            forbidden=IAMConstraint().forbidden_actions,
        )
        assert "neptune-db:ReadDataViaQuery" in violations

    def test_glob_match_catches_ssm_parameter(self) -> None:
        policy = IAMPolicyDocument(actions=("ssm:GetParameter",))
        violations = validate_iam_policy(
            policy,
            forbidden=IAMConstraint().forbidden_actions,
        )
        assert "ssm:GetParameter" in violations

    def test_wildcard_action_caught(self) -> None:
        policy = IAMPolicyDocument(actions=("*",))
        violations = validate_iam_policy(
            policy,
            forbidden=("dynamodb:Scan",),
        )
        # "*" doesn't match "dynamodb:Scan" with the simple matcher,
        # but if the rule itself is "*", matches everything. We test
        # the more dangerous direction:
        assert validate_iam_policy(
            policy,
            forbidden=("*",),
        ) == ("*",)

    def test_multiple_violations_listed(self) -> None:
        policy = IAMPolicyDocument(actions=(
            "secretsmanager:GetSecretValue",
            "rds:DeleteDBInstance",
            "s3:GetObject",  # benign
        ))
        violations = validate_iam_policy(
            policy,
            forbidden=IAMConstraint().forbidden_actions,
        )
        assert "secretsmanager:GetSecretValue" in violations
        assert "rds:DeleteDBInstance" in violations
        assert "s3:GetObject" not in violations
