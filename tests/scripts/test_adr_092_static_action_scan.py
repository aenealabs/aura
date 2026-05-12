"""Tests for ``scripts/adr_092_static_action_scan.py``.

Covers:
- CFN-tag-aware YAML loading (``!Sub``, ``!Ref``, ``!If`` don't crash the parser)
- Action extraction from every shape of ``Action:`` field
- Wildcard-aware coverage matching (``s3:*`` covers ``s3:GetObject``, etc.)
- End-to-end scan with fixture templates
- ``--fail-on-gap`` exit code
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from textwrap import dedent

import pytest

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "adr_092_static_action_scan.py"
)
_spec = importlib.util.spec_from_file_location("adr_092_static_action_scan", _SCRIPT)
scan_mod = importlib.util.module_from_spec(_spec)
# Register in sys.modules before exec so dataclasses can resolve __module__.
sys.modules["adr_092_static_action_scan"] = scan_mod
_spec.loader.exec_module(scan_mod)


# ---------------------------------------------------------------------------
# CFN YAML loader
# ---------------------------------------------------------------------------


class TestCfnLoader:
    def test_loader_accepts_sub_tag(self, tmp_path: Path) -> None:
        p = tmp_path / "t.yaml"
        p.write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::S3::Bucket
                    Properties:
                      BucketName: !Sub '${ProjectName}-${Environment}'
                """).strip(),
            encoding="utf-8",
        )
        import yaml

        doc = yaml.load(p.read_text(), Loader=scan_mod.CfnLoader)  # noqa: S506
        assert doc["Resources"]["R"]["Type"] == "AWS::S3::Bucket"
        # !Sub payload is preserved as the scalar string
        assert (
            doc["Resources"]["R"]["Properties"]["BucketName"]
            == "${ProjectName}-${Environment}"
        )

    def test_loader_accepts_ref_and_findinmap(self, tmp_path: Path) -> None:
        p = tmp_path / "t.yaml"
        p.write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      RoleName: !Ref ProjectName
                      ManagedPolicyArns:
                        - !FindInMap [PartitionMap, !Ref 'AWS::Partition', Partition]
                """).strip(),
            encoding="utf-8",
        )
        import yaml

        doc = yaml.load(p.read_text(), Loader=scan_mod.CfnLoader)  # noqa: S506
        # The parser should not crash; the precise structure of intrinsic
        # payloads doesn't matter for downstream Action extraction.
        assert doc["Resources"]["R"]["Type"] == "AWS::IAM::Role"


# ---------------------------------------------------------------------------
# _normalize_actions
# ---------------------------------------------------------------------------


class TestNormalizeActions:
    def test_single_string(self) -> None:
        assert scan_mod._normalize_actions("s3:GetObject") == ["s3:GetObject"]

    def test_list_of_strings(self) -> None:
        assert scan_mod._normalize_actions(["s3:GetObject", "s3:PutObject"]) == [
            "s3:GetObject",
            "s3:PutObject",
        ]

    def test_none_returns_empty(self) -> None:
        assert scan_mod._normalize_actions(None) == []

    def test_unrecognized_shape_returns_empty(self) -> None:
        assert scan_mod._normalize_actions({"weird": "shape"}) == []

    def test_nested_list_flattened(self) -> None:
        # rare but possible via !If intrinsic
        assert scan_mod._normalize_actions([["s3:GetObject", "s3:PutObject"]]) == [
            "s3:GetObject",
            "s3:PutObject",
        ]


# ---------------------------------------------------------------------------
# action_is_covered (wildcard matching)
# ---------------------------------------------------------------------------


class TestActionIsCovered:
    def test_exact_match(self) -> None:
        assert scan_mod.action_is_covered("s3:GetObject", {"s3:GetObject"})

    def test_full_service_wildcard(self) -> None:
        assert scan_mod.action_is_covered("s3:GetObject", {"s3:*"})

    def test_prefix_wildcard(self) -> None:
        assert scan_mod.action_is_covered("s3:GetObject", {"s3:Get*"})

    def test_admin_wildcard(self) -> None:
        assert scan_mod.action_is_covered("s3:GetObject", {"*"})

    def test_case_insensitive(self) -> None:
        # IAM is case-insensitive on action names
        assert scan_mod.action_is_covered("S3:GETOBJECT", {"s3:GetObject"})

    def test_no_match(self) -> None:
        assert not scan_mod.action_is_covered("kms:Decrypt", {"s3:*"})

    def test_empty_granted_set(self) -> None:
        assert not scan_mod.action_is_covered("s3:GetObject", set())

    def test_service_match_does_not_imply_action(self) -> None:
        # 's3:Put*' must not match 's3:GetObject'
        assert not scan_mod.action_is_covered("s3:GetObject", {"s3:Put*"})


# ---------------------------------------------------------------------------
# extract_actions_from_template
# ---------------------------------------------------------------------------


class TestExtractActionsFromTemplate:
    def _write(self, tmp_path: Path, name: str, content: str) -> Path:
        p = tmp_path / name
        p.write_text(dedent(content).strip(), encoding="utf-8")
        return p

    def test_role_inline_policy(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "role.yaml",
            """
            Resources:
              MyRole:
                Type: AWS::IAM::Role
                Properties:
                  Policies:
                    - PolicyName: Inline
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Sid: AllowS3
                            Effect: Allow
                            Action:
                              - s3:GetObject
                              - s3:PutObject
                            Resource: '*'
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        actions = sorted(r.action for r in refs)
        assert actions == ["s3:GetObject", "s3:PutObject"]
        assert all(r.resource_logical_id == "MyRole" for r in refs)
        assert all(r.statement_sid == "AllowS3" for r in refs)

    def test_managed_policy(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "mp.yaml",
            """
            Resources:
              MyMP:
                Type: AWS::IAM::ManagedPolicy
                Properties:
                  PolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Action: kms:Decrypt
                        Resource: '*'
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        assert [r.action for r in refs] == ["kms:Decrypt"]

    def test_standalone_policy(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "p.yaml",
            """
            Resources:
              MyP:
                Type: AWS::IAM::Policy
                Properties:
                  PolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Action: ['dynamodb:GetItem', 'dynamodb:Query']
                        Resource: '*'
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        assert sorted(r.action for r in refs) == ["dynamodb:GetItem", "dynamodb:Query"]

    def test_deny_statements_skipped(self, tmp_path: Path) -> None:
        """Deny actions don't grant anything; they should not be reported."""
        p = self._write(
            tmp_path,
            "d.yaml",
            """
            Resources:
              MyRole:
                Type: AWS::IAM::Role
                Properties:
                  Policies:
                    - PolicyName: Inline
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: s3:GetObject
                            Resource: '*'
                          - Effect: Deny
                            Action: s3:DeleteBucket
                            Resource: '*'
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        assert [r.action for r in refs] == ["s3:GetObject"]

    def test_non_iam_resources_skipped(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "x.yaml",
            """
            Resources:
              MyBucket:
                Type: AWS::S3::Bucket
                Properties:
                  BucketName: foo
              MyRole:
                Type: AWS::IAM::Role
                Properties:
                  Policies:
                    - PolicyName: Inline
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: s3:GetObject
                            Resource: '*'
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        assert len(refs) == 1
        assert refs[0].resource_logical_id == "MyRole"

    def test_assume_role_policy_trust(self, tmp_path: Path) -> None:
        """Trust-policy actions (typically sts:AssumeRole) are captured."""
        p = self._write(
            tmp_path,
            "trust.yaml",
            """
            Resources:
              MyRole:
                Type: AWS::IAM::Role
                Properties:
                  AssumeRolePolicyDocument:
                    Version: '2012-10-17'
                    Statement:
                      - Effect: Allow
                        Principal:
                          Service: lambda.amazonaws.com
                        Action: sts:AssumeRole
            """,
        )
        refs = scan_mod.extract_actions_from_template(p, tmp_path)
        assert [r.action for r in refs] == ["sts:AssumeRole"]

    def test_malformed_yaml_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "broken.yaml"
        p.write_text("not: valid: yaml: [", encoding="utf-8")
        assert scan_mod.extract_actions_from_template(p, tmp_path) == []

    def test_missing_resources_block(self, tmp_path: Path) -> None:
        p = self._write(
            tmp_path,
            "noresources.yaml",
            """
            Parameters:
              Foo:
                Type: String
            """,
        )
        assert scan_mod.extract_actions_from_template(p, tmp_path) == []


# ---------------------------------------------------------------------------
# extract_scoped_policy_actions
# ---------------------------------------------------------------------------


class TestExtractScopedPolicyActions:
    def test_extracts_from_scoped_managed_policy(self, tmp_path: Path) -> None:
        p = tmp_path / "iam.yaml"
        p.write_text(
            dedent("""
                Resources:
                  CloudFormationScopedManagedPolicy:
                    Type: AWS::IAM::ManagedPolicy
                    Properties:
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: [s3:CreateBucket, s3:DeleteBucket]
                            Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        granted = scan_mod.extract_scoped_policy_actions(p)
        assert granted == {"s3:CreateBucket", "s3:DeleteBucket"}

    def test_unions_scoped_and_inline_role_policy(self, tmp_path: Path) -> None:
        p = tmp_path / "iam.yaml"
        p.write_text(
            dedent("""
                Resources:
                  CloudFormationScopedManagedPolicy:
                    Type: AWS::IAM::ManagedPolicy
                    Properties:
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: s3:CreateBucket
                            Resource: '*'
                  CloudFormationServiceRole:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: Inline
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: kms:CreateKey
                                Resource: '*'
                              - Effect: Deny
                                Action: iam:DeleteUser
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        granted = scan_mod.extract_scoped_policy_actions(p)
        # Allow union; Deny excluded
        assert granted == {"s3:CreateBucket", "kms:CreateKey"}

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert (
            scan_mod.extract_scoped_policy_actions(tmp_path / "noexist.yaml") == set()
        )


# ---------------------------------------------------------------------------
# End-to-end scan
# ---------------------------------------------------------------------------


class TestEndToEndScan:
    def _setup(self, tmp_path: Path) -> tuple[Path, Path]:
        cfn_dir = tmp_path / "cfn"
        cfn_dir.mkdir()
        iam = cfn_dir / "iam.yaml"
        iam.write_text(
            dedent("""
                Resources:
                  CloudFormationScopedManagedPolicy:
                    Type: AWS::IAM::ManagedPolicy
                    Properties:
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: [s3:*, kms:Decrypt]
                            Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        return cfn_dir, iam

    def test_no_gaps_when_all_covered(self, tmp_path: Path) -> None:
        cfn_dir, iam = self._setup(tmp_path)
        (cfn_dir / "t.yaml").write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: P
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: [s3:GetObject, kms:Decrypt]
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        report = scan_mod.scan(cfn_dir, iam)
        assert not report.has_gaps
        assert report.total_templates_scanned == 1  # iam.yaml excluded
        assert len(report.covered) == 2

    def test_gaps_when_action_missing(self, tmp_path: Path) -> None:
        cfn_dir, iam = self._setup(tmp_path)
        (cfn_dir / "t.yaml").write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: P
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: [s3:GetObject, dynamodb:GetItem]
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        report = scan_mod.scan(cfn_dir, iam)
        assert report.has_gaps
        assert report.unique_uncovered_actions == {"dynamodb:GetItem"}

    def test_services_filter(self, tmp_path: Path) -> None:
        cfn_dir, iam = self._setup(tmp_path)
        (cfn_dir / "t.yaml").write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: P
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: [s3:GetObject, dynamodb:GetItem, rds:DescribeDBInstances]
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        report = scan_mod.scan(cfn_dir, iam, services_filter={"dynamodb"})
        # Only dynamodb actions considered; s3 + rds dropped from analysis
        all_refs = report.covered + report.uncovered
        assert {r.service for r in all_refs} == {"dynamodb"}

    def test_recursive_subdir_scan(self, tmp_path: Path) -> None:
        """Templates in subdirectories (e.g. service-catalog-products/) are scanned."""
        cfn_dir, iam = self._setup(tmp_path)
        sub = cfn_dir / "subdir"
        sub.mkdir()
        (sub / "nested.yaml").write_text(
            dedent("""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: P
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: s3:GetObject
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        report = scan_mod.scan(cfn_dir, iam)
        # iam.yaml is excluded; nested.yaml counted
        assert report.total_templates_scanned == 1
        assert len(report.covered) == 1


# ---------------------------------------------------------------------------
# CLI main()
# ---------------------------------------------------------------------------


class TestMainCLI:
    def _setup(self, tmp_path: Path, with_gap: bool) -> tuple[Path, Path]:
        cfn_dir = tmp_path / "cfn"
        cfn_dir.mkdir()
        iam = cfn_dir / "iam.yaml"
        iam.write_text(
            dedent("""
                Resources:
                  CloudFormationScopedManagedPolicy:
                    Type: AWS::IAM::ManagedPolicy
                    Properties:
                      PolicyDocument:
                        Version: '2012-10-17'
                        Statement:
                          - Effect: Allow
                            Action: s3:*
                            Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        gap_action = "dynamodb:GetItem" if with_gap else "s3:GetObject"
        (cfn_dir / "t.yaml").write_text(
            dedent(f"""
                Resources:
                  R:
                    Type: AWS::IAM::Role
                    Properties:
                      Policies:
                        - PolicyName: P
                          PolicyDocument:
                            Version: '2012-10-17'
                            Statement:
                              - Effect: Allow
                                Action: {gap_action}
                                Resource: '*'
                """).strip(),
            encoding="utf-8",
        )
        return cfn_dir, iam

    def test_exit_zero_when_no_gaps(self, tmp_path: Path, capsys) -> None:
        cfn_dir, iam = self._setup(tmp_path, with_gap=False)
        rc = scan_mod.main(
            ["--cfn-dir", str(cfn_dir), "--iam-yaml", str(iam), "--fail-on-gap"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "NO GAPS" in out

    def test_exit_one_when_gaps_and_fail_flag(self, tmp_path: Path, capsys) -> None:
        cfn_dir, iam = self._setup(tmp_path, with_gap=True)
        rc = scan_mod.main(
            ["--cfn-dir", str(cfn_dir), "--iam-yaml", str(iam), "--fail-on-gap"]
        )
        assert rc == 1
        out = capsys.readouterr().out
        assert "GAPS FOUND" in out

    def test_exit_zero_when_gaps_without_fail_flag(
        self, tmp_path: Path, capsys
    ) -> None:
        """Default behavior: report gaps but exit 0 so the script can be used informationally."""
        cfn_dir, iam = self._setup(tmp_path, with_gap=True)
        rc = scan_mod.main(["--cfn-dir", str(cfn_dir), "--iam-yaml", str(iam)])
        assert rc == 0

    def test_markdown_report_written(self, tmp_path: Path) -> None:
        cfn_dir, iam = self._setup(tmp_path, with_gap=True)
        report_path = tmp_path / "report.md"
        rc = scan_mod.main(
            [
                "--cfn-dir",
                str(cfn_dir),
                "--iam-yaml",
                str(iam),
                "--report-markdown",
                str(report_path),
            ]
        )
        assert rc == 0
        assert report_path.is_file()
        content = report_path.read_text(encoding="utf-8")
        assert "ADR-092 Static Action Scan Report" in content
        assert "dynamodb:GetItem" in content

    def test_json_report_written(self, tmp_path: Path) -> None:
        cfn_dir, iam = self._setup(tmp_path, with_gap=True)
        json_path = tmp_path / "report.json"
        rc = scan_mod.main(
            [
                "--cfn-dir",
                str(cfn_dir),
                "--iam-yaml",
                str(iam),
                "--report-json",
                str(json_path),
            ]
        )
        assert rc == 0
        import json

        payload = json.loads(json_path.read_text())
        assert payload["uncovered_count"] == 1
        assert "dynamodb:GetItem" in payload["unique_uncovered_actions"]

    def test_missing_cfn_dir(self, tmp_path: Path, capsys) -> None:
        rc = scan_mod.main(
            ["--cfn-dir", str(tmp_path / "nope"), "--iam-yaml", str(tmp_path)]
        )
        assert rc == 2

    def test_missing_iam_yaml(self, tmp_path: Path, capsys) -> None:
        cfn_dir, _ = self._setup(tmp_path, with_gap=False)
        rc = scan_mod.main(
            ["--cfn-dir", str(cfn_dir), "--iam-yaml", str(tmp_path / "noexist.yaml")]
        )
        assert rc == 2


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
