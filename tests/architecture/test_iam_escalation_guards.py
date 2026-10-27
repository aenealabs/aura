"""IAM privilege-escalation guards for the build and deploy pipeline.

The layer CodeBuild roles are the identities that actually deploy Aura's
stacks, and they hold IAM write permissions on project roles. Without guards,
a build could rewrite its own role or create a new role with broader rights
and pass it to a service it controls (MITRE ATT&CK T1098.001 / T1078.004).
ADR-092 closed those paths for the CloudFormation service role; these tests
keep them closed for every role the pipeline creates.

Invariants:

1. Every IAM role carries a permission boundary, except roles in templates
   deployed outside this account's pipeline (management account, customer
   Service Catalog launches).
2. Build and deploy roles use the deployer boundary; all other roles use an
   approved runtime boundary.
3. The deployer boundary keeps its escalation denies.
4. Every ``iam:PassRole`` grant on a CodeBuild role is limited by
   ``iam:PassedToService`` and is not bundled with other actions.
5. Every layer buildspec deploy honors the opt-in CloudFormation service role.

The checks are static: they parse templates and buildspecs, and make no AWS
calls.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from cfnlint.decode import decode

REPO = Path(__file__).resolve().parents[2]
CFN_DIR = REPO / "deploy" / "cloudformation"
BUILDSPEC_DIR = REPO / "deploy" / "buildspecs"

# Templates whose roles are created outside this account's pipeline, before
# the boundaries stack exists, or in another account.
EXEMPT_TEMPLATES = {
    "account-bootstrap.yaml",
    "account-migration-bootstrap.yaml",
    "org-cloudtrail.yaml",
    "route53-cross-account-role.yaml",
}
EXEMPT_DIRS = {"archive", "service-catalog-products"}

DEPLOYER_ROLES_IN_IAM_TEMPLATE = {"CloudFormationServiceRole", "CodeBuildServiceRole"}

APPROVED_RUNTIME_BOUNDARIES = {
    "workload-boundary",
    "serverless-permission-boundary",
    "test-env-permission-boundary",
    # Tighter purpose-built boundaries defined alongside their roles.
    "ma-sandbox-permissions-boundary",
    "taint-resolver-writer-boundary",
}

REQUIRED_DEPLOYER_DENIES = {
    "DenyModifyPipelineIdentities",
    "DenyModifyBootstrapRole",
    "DenyAssumeSameAccountRoles",
    "DenyModifyBoundaryPolicies",
    "DenyRoleWithoutApprovedBoundary",
    "DenyBoundaryRemoval",
    "DenyAdminPolicyAttachment",
    "DenyLongLivedCredentials",
    "DenyDataPlaneReads",
    "DenyObjectReadsOutsideProjectBuckets",
}

# Buildspecs that must not deploy through the CloudFormation service role.
ROLE_ARN_EXEMPT_BUILDSPECS = {
    # Deploys the CodeBuild stacks themselves; the deployer boundary forbids
    # the CloudFormation service role from changing CodeBuild roles.
    "buildspec-bootstrap.yml",
}

DEPLOY_COMMAND = re.compile(
    r"(^\s*-?\s*if\s+|^\s*-?\s*|\$\(\s*|&&\s*|\|\|\s*|;\s*)"
    r"aws cloudformation (deploy|create-stack|update-stack)\b(?P<rest>.*)$",
    re.M,
)


def _templates() -> list[Path]:
    paths = []
    for path in sorted(CFN_DIR.rglob("*.yaml")):
        rel = path.relative_to(CFN_DIR)
        if rel.parts[0] in EXEMPT_DIRS or rel.name in EXEMPT_TEMPLATES:
            continue
        paths.append(path)
    return paths


def _load(path: Path) -> dict:
    template, matches = decode(str(path))
    assert template is not None, f"{path.name} failed to parse: {matches}"
    return template


def _roles(template: dict) -> dict[str, dict]:
    return {
        logical_id: resource
        for logical_id, resource in (template.get("Resources") or {}).items()
        if isinstance(resource, dict) and resource.get("Type") == "AWS::IAM::Role"
    }


BOUNDARY_NAME = re.compile(
    r"(deployer-boundary|workload-boundary|serverless-permission-boundary|"
    r"test-env-permission-boundary|ma-sandbox-permissions-boundary|"
    r"taint-resolver-writer-boundary)-\$\{Environment\}"
)


def _boundary_names(boundary, template: dict) -> set[str]:
    """Return the boundary policy names a PermissionsBoundary value can resolve to.

    Handles ARNs built with ``!Sub``, ``!If`` branches, and ``!Ref`` to a
    managed policy defined in the same template.
    """
    text = repr(boundary)
    for ref in re.findall(r"'Ref': '([A-Za-z0-9]+)'", text):
        policy = (template.get("Resources") or {}).get(ref) or {}
        text += repr((policy.get("Properties") or {}).get("ManagedPolicyName"))
    return set(BOUNDARY_NAME.findall(text))


def _expected_kind(template_name: str, logical_id: str) -> str:
    if template_name.startswith("codebuild-"):
        return "deployer"
    if template_name == "iam.yaml" and logical_id in DEPLOYER_ROLES_IN_IAM_TEMPLATE:
        return "deployer"
    return "runtime"


ROLE_CASES = [
    pytest.param(
        path.name, logical_id, resource, template, id=f"{path.name}::{logical_id}"
    )
    for path in _templates()
    for template in [_load(path)]
    for logical_id, resource in _roles(template).items()
]


@pytest.mark.parametrize("template_name,logical_id,resource,template", ROLE_CASES)
def test_every_role_has_an_approved_permission_boundary(
    template_name, logical_id, resource, template
):
    boundary = (resource.get("Properties") or {}).get("PermissionsBoundary")
    assert boundary, (
        f"{template_name}:{logical_id} has no PermissionsBoundary. Every role the "
        "pipeline creates must carry one; the deployer boundary refuses CreateRole "
        "without it."
    )
    names = _boundary_names(boundary, template)
    if _expected_kind(template_name, logical_id) == "deployer":
        assert names == {"deployer-boundary"}, (
            f"{template_name}:{logical_id} is a build/deploy role and must use the "
            f"deployer boundary, found {names or boundary!r}"
        )
    else:
        assert names and names <= APPROVED_RUNTIME_BOUNDARIES, (
            f"{template_name}:{logical_id} must use an approved runtime boundary "
            f"{sorted(APPROVED_RUNTIME_BOUNDARIES)}, found {names or boundary!r}"
        )


def test_deployer_boundary_keeps_its_escalation_denies():
    template = _load(CFN_DIR / "iam-permission-boundaries.yaml")
    policy = template["Resources"]["DeployerPermissionBoundary"]["Properties"][
        "PolicyDocument"
    ]
    deny_sids = {s.get("Sid") for s in policy["Statement"] if s.get("Effect") == "Deny"}
    missing = REQUIRED_DEPLOYER_DENIES - deny_sids
    assert (
        not missing
    ), f"Deployer boundary is missing deny statements: {sorted(missing)}"


def test_workload_boundary_denies_iam_changes():
    template = _load(CFN_DIR / "iam-permission-boundaries.yaml")
    policy = template["Resources"]["WorkloadPermissionBoundary"]["Properties"][
        "PolicyDocument"
    ]
    denied = {
        action
        for s in policy["Statement"]
        if s.get("Effect") == "Deny"
        for action in (s["Action"] if isinstance(s["Action"], list) else [s["Action"]])
    }
    for action in (
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:CreateAccessKey",
    ):
        assert action in denied, f"Workload boundary must deny {action}"
    assert (
        "iam:CreateServiceLinkedRole" not in denied
    ), "Workload roles such as the ALB controller create service-linked roles"


def _statements(template: dict):
    for resource in (template.get("Resources") or {}).values():
        props = (resource or {}).get("Properties") or {}
        docs = [p.get("PolicyDocument") for p in props.get("Policies") or []]
        if resource.get("Type") == "AWS::IAM::ManagedPolicy":
            docs.append(props.get("PolicyDocument"))
        for doc in docs:
            for statement in (doc or {}).get("Statement") or []:
                yield statement


CODEBUILD_TEMPLATES = sorted(CFN_DIR.glob("codebuild-*.yaml"))


@pytest.mark.parametrize("path", CODEBUILD_TEMPLATES, ids=lambda p: p.name)
def test_codebuild_passrole_is_service_scoped(path):
    for statement in _statements(_load(path)):
        if statement.get("Effect") != "Allow":
            continue
        actions = statement.get("Action")
        actions = actions if isinstance(actions, list) else [actions]
        if "iam:PassRole" not in actions:
            continue
        assert actions == ["iam:PassRole"], (
            f"{path.name}: iam:PassRole is bundled with {actions}; give it its own "
            "statement so the PassedToService condition cannot block other actions"
        )
        condition = repr(statement.get("Condition"))
        assert (
            "iam:PassedToService" in condition
        ), f"{path.name}: iam:PassRole without an iam:PassedToService condition"


@pytest.mark.parametrize(
    "path",
    [p for p in CODEBUILD_TEMPLATES if p.name != "codebuild-bootstrap.yaml"],
    ids=lambda p: p.name,
)
def test_layer_roles_can_pass_the_cloudformation_service_role(path):
    template = _load(path)
    policy = template["Resources"].get("CfnServiceRolePolicy")
    assert (
        policy
    ), f"{path.name} lacks CfnServiceRolePolicy (ADR-092 opt-in deploy role)"
    text = repr(policy["Properties"]["PolicyDocument"])
    assert "cfn-role-${Environment}" in text and "cloudformation.amazonaws.com" in text


BUILDSPECS = sorted(BUILDSPEC_DIR.glob("*.yml"))


@pytest.mark.parametrize("path", BUILDSPECS, ids=lambda p: p.name)
def test_buildspec_deploys_honor_the_opt_in_service_role(path):
    if path.name in ROLE_ARN_EXEMPT_BUILDSPECS:
        pytest.skip(
            "deploys CodeBuild stacks; must not use the CloudFormation service role"
        )
    text = path.read_text(encoding="utf-8")
    commands = list(DEPLOY_COMMAND.finditer(text))
    if not commands:
        pytest.skip("no CloudFormation deploy commands")
    unwired = [
        m.group(0).strip()
        for m in commands
        if not m.group("rest").lstrip().startswith("${CFN_ROLE_ARG:-}")
    ]
    assert (
        not unwired
    ), f"{path.name}: deploy commands without ${{CFN_ROLE_ARG:-}}: {unwired[:3]}"
    assert "CFN_ROLE_ARG=" in text, f"{path.name}: never resolves CFN_ROLE_ARG"


def test_cfn_deploy_helper_honors_the_opt_in_service_role():
    helper = (REPO / "deploy" / "scripts" / "cfn-deploy-helpers.sh").read_text(
        encoding="utf-8"
    )
    commands = list(DEPLOY_COMMAND.finditer(helper)) + list(
        re.finditer(r'local cmd="aws cloudformation deploy(?P<rest>[^"]*)"', helper)
    )
    assert commands, "cfn-deploy-helpers.sh no longer deploys stacks; update this test"
    unwired = [
        m.group(0).strip()
        for m in commands
        if "${CFN_ROLE_ARG:-}" not in m.group("rest")
    ]
    assert (
        not unwired
    ), f"cfn-deploy-helpers.sh deploys without ${{CFN_ROLE_ARG:-}}: {unwired}"


# Single-command deploy guard: no build role may be asked to deploy a stack
# that owns a role the deployer boundary protects from it. A hit here means
# `deploy.sh deploy <env>` would fail at that layer with AccessDenied.
DEPLOYED_TEMPLATE = re.compile(
    r'(?:--template-file|--template-body)\s+(?:file://)?"?deploy/cloudformation/([A-Za-z0-9_./-]+\.yaml)'
)
HELPER_TEMPLATE = re.compile(
    r'cfn_deploy_stack\s*\\\s*\n\s*"[^"]*"\s*\\\s*\n\s*"deploy/cloudformation/([A-Za-z0-9_./-]+\.yaml)"'
)


def _sub(value) -> str | None:
    if isinstance(value, dict) and "Fn::Sub" in value:
        value = value["Fn::Sub"]
        value = value if isinstance(value, str) else value[0]
    if not isinstance(value, str):
        return None
    return (
        value.replace("${ProjectName}", "aura")
        .replace("${Environment}", "dev")
        .replace("${AWS::Partition}", "aws")
        .replace("${AWS::AccountId}", "111111111111")
    )


def _protected_role_patterns() -> list[tuple[str, str]]:
    policy = _load(CFN_DIR / "iam-permission-boundaries.yaml")["Resources"][
        "DeployerPermissionBoundary"
    ]
    patterns = []
    for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
        if statement.get("Sid") not in (
            "DenyModifyPipelineIdentities",
            "DenyModifyBootstrapRole",
        ):
            continue
        resources = (
            statement["Resource"]
            if isinstance(statement["Resource"], list)
            else [statement["Resource"]]
        )
        patterns += [(statement["Sid"], _sub(r).split(":role/")[1]) for r in resources]
    return patterns


def _deploying_roles():
    """Yield (build role name, is bootstrap, templates its buildspec deploys)."""
    for path in CODEBUILD_TEMPLATES:
        template = _load(path)
        resources = template["Resources"].values()
        project = next(
            r for r in resources if r.get("Type") == "AWS::CodeBuild::Project"
        )
        role = next(r for r in resources if r.get("Type") == "AWS::IAM::Role")
        buildspec = project["Properties"].get("Source", {}).get("BuildSpec")
        if not isinstance(buildspec, str) or not (REPO / buildspec).exists():
            continue
        text = (REPO / buildspec).read_text(encoding="utf-8")
        deployed = set(DEPLOYED_TEMPLATE.findall(text)) | set(
            HELPER_TEMPLATE.findall(text)
        )
        is_bootstrap = path.name == "codebuild-bootstrap.yaml"
        if is_bootstrap:
            deployed |= {
                p.name
                for p in CODEBUILD_TEMPLATES
                if p.name != "codebuild-bootstrap.yaml"
            }
        yield _sub(role["Properties"]["RoleName"]), is_bootstrap, sorted(deployed)


def test_layer_deploys_do_not_touch_roles_the_boundary_protects():
    import fnmatch

    patterns = _protected_role_patterns()
    conflicts = []
    for build_role, is_bootstrap, templates in _deploying_roles():
        for name in templates:
            path = CFN_DIR / name
            if not path.exists():
                continue
            for logical_id, resource in _roles(_load(path)).items():
                role_name = (
                    _sub((resource.get("Properties") or {}).get("RoleName")) or ""
                )
                for sid, pattern in patterns:
                    if sid == "DenyModifyPipelineIdentities" and is_bootstrap:
                        continue
                    if fnmatch.fnmatch(role_name, pattern):
                        conflicts.append(
                            f"{build_role} deploys {name}:{logical_id} ({role_name}), denied by {sid}"
                        )
    assert not conflicts, "Single-command deploy would fail:\n" + "\n".join(conflicts)


def test_deploy_path_detection_finds_known_deploys():
    """Positive control: the extraction must see deploys we know exist."""
    by_role = {role: templates for role, _, templates in _deploying_roles()}
    assert "deployment-pipeline.yaml" in by_role["aura-serverless-codebuild-role-dev"]
    assert "iam.yaml" not in by_role["aura-serverless-codebuild-role-dev"]
    assert "codebuild-foundation.yaml" in by_role["aura-bootstrap-codebuild-role-dev"]
    assert len(by_role["aura-data-codebuild-role-dev"]) >= 5


# Resource properties that hand a role to a service, and the service that
# receives it (the iam:PassedToService value CloudFormation's PassRole check
# uses when a stack deploys as the layer's CodeBuild role).
ROLE_PROPS = {
    "AWS::Lambda::Function": [("Role", "lambda.amazonaws.com")],
    "AWS::StepFunctions::StateMachine": [("RoleArn", "states.amazonaws.com")],
    "AWS::ECS::TaskDefinition": [
        ("TaskRoleArn", "ecs-tasks.amazonaws.com"),
        ("ExecutionRoleArn", "ecs-tasks.amazonaws.com"),
    ],
    "AWS::CodeBuild::Project": [("ServiceRole", "codebuild.amazonaws.com")],
    "AWS::EKS::Cluster": [("RoleArn", "eks.amazonaws.com")],
    "AWS::EKS::Nodegroup": [("NodeRole", "eks.amazonaws.com")],
    "AWS::EKS::FargateProfile": [
        ("PodExecutionRoleArn", "eks-fargate-pods.amazonaws.com")
    ],
    "AWS::EC2::FlowLog": [("DeliverLogsPermissionArn", "vpc-flow-logs.amazonaws.com")],
    "AWS::Events::Rule": [
        ("RoleArn", "events.amazonaws.com"),
        ("Targets[].RoleArn", "events.amazonaws.com"),
    ],
    "AWS::Scheduler::Schedule": [("Target.RoleArn", "scheduler.amazonaws.com")],
    "AWS::Pipes::Pipe": [("RoleArn", "pipes.amazonaws.com")],
    "AWS::Backup::BackupSelection": [
        ("BackupSelection.IamRoleArn", "backup.amazonaws.com")
    ],
    "AWS::Config::ConfigurationRecorder": [("RoleARN", "config.amazonaws.com")],
    "AWS::Config::ConfigRule": [],
    "AWS::CloudTrail::Trail": [("CloudWatchLogsRoleArn", "cloudtrail.amazonaws.com")],
    "AWS::KinesisFirehose::DeliveryStream": [
        ("ExtendedS3DestinationConfiguration.RoleARN", "firehose.amazonaws.com"),
        ("S3DestinationConfiguration.RoleARN", "firehose.amazonaws.com"),
        ("KinesisStreamSourceConfiguration.RoleARN", "firehose.amazonaws.com"),
    ],
    "AWS::Logs::SubscriptionFilter": [("RoleArn", "logs.amazonaws.com")],
    "AWS::Logs::Destination": [("RoleArn", "logs.amazonaws.com")],
    "AWS::ApiGateway::Account": [("CloudWatchRoleArn", "apigateway.amazonaws.com")],
    "AWS::S3::Bucket": [("ReplicationConfiguration.Role", "s3.amazonaws.com")],
    "AWS::Neptune::DBCluster": [("AssociatedRoles[].RoleArn", "rds.amazonaws.com")],
    "AWS::RDS::DBCluster": [("AssociatedRoles[].RoleArn", "rds.amazonaws.com")],
    "AWS::RDS::DBInstance": [("MonitoringRoleArn", "monitoring.rds.amazonaws.com")],
    "AWS::Neptune::DBInstance": [],
    "AWS::Cognito::UserPool": [
        ("SmsConfiguration.SnsCallerArn", "cognito-idp.amazonaws.com")
    ],
    "AWS::Cognito::IdentityPoolRoleAttachment": [
        ("Roles.authenticated", "cognito-identity.amazonaws.com"),
        ("Roles.unauthenticated", "cognito-identity.amazonaws.com"),
    ],
    "AWS::ServiceCatalog::LaunchRoleConstraint": [
        ("RoleArn", "servicecatalog.amazonaws.com")
    ],
    "AWS::SSM::MaintenanceWindowTask": [("ServiceRoleArn", "ssm.amazonaws.com")],
    "AWS::Synthetics::Canary": [("ExecutionRoleArn", "lambda.amazonaws.com")],
    "AWS::AppSync::DataSource": [("ServiceRoleArn", "appsync.amazonaws.com")],
    "AWS::Glue::Job": [("Role", "glue.amazonaws.com")],
    "AWS::OpenSearchService::Domain": [("CognitoOptions.RoleArn", "es.amazonaws.com")],
    "AWS::Elasticsearch::Domain": [("CognitoOptions.RoleArn", "es.amazonaws.com")],
    "AWS::EC2::LaunchTemplate": [
        ("LaunchTemplateData.IamInstanceProfile", "ec2.amazonaws.com")
    ],
    "AWS::EC2::Instance": [("IamInstanceProfile", "ec2.amazonaws.com")],
    "AWS::AutoScaling::LaunchConfiguration": [
        ("IamInstanceProfile", "ec2.amazonaws.com")
    ],
    "AWS::ApiGatewayV2::Integration": [("CredentialsArn", "apigateway.amazonaws.com")],
    "AWS::ApiGateway::Method": [
        ("Integration.Credentials", "apigateway.amazonaws.com")
    ],
    "AWS::SNS::Topic": [
        ("DeliveryStatusLogging[].SuccessFeedbackRoleArn", "sns.amazonaws.com"),
        ("DeliveryStatusLogging[].FailureFeedbackRoleArn", "sns.amazonaws.com"),
    ],
    "AWS::DMS::ReplicationInstance": [],
    "AWS::Bedrock::Agent": [("AgentResourceRoleArn", "bedrock.amazonaws.com")],
    "AWS::Bedrock::KnowledgeBase": [("RoleArn", "bedrock.amazonaws.com")],
    "AWS::ECS::Service": [("Role", "ecs.amazonaws.com")],
    "AWS::GuardDuty::Detector": [],
    "AWS::SecurityHub::Hub": [],
    "AWS::CodePipeline::Pipeline": [("RoleArn", "codepipeline.amazonaws.com")],
    "AWS::DataSync::Task": [],
    "AWS::MSK::Cluster": [],
    "AWS::SageMaker::Model": [("ExecutionRoleArn", "sagemaker.amazonaws.com")],
}


def _values_at(props, path):
    values = [props]
    for part in path.split("."):
        many = part.endswith("[]")
        key = part[:-2] if many else part
        nxt = []
        for value in values:
            if isinstance(value, dict) and key in value:
                item = value[key]
                nxt.extend(item if many and isinstance(item, list) else [item])
        values = nxt
    return [v for v in values if v not in (None, "")]


def _passrole_services(template: dict) -> set[str]:
    allowed = set()
    for statement in _statements(template):
        actions = statement.get("Action")
        actions = actions if isinstance(actions, list) else [actions]
        if statement.get("Effect") != "Allow" or "iam:PassRole" not in actions:
            continue
        for operator in (statement.get("Condition") or {}).values():
            if isinstance(operator, dict) and "iam:PassedToService" in operator:
                value = operator["iam:PassedToService"]
                allowed |= set(value if isinstance(value, list) else [value])
    allowed.discard(
        "cloudformation.amazonaws.com"
    )  # the cfn-role grant, resource-scoped to that role
    return allowed


@pytest.mark.parametrize("path", CODEBUILD_TEMPLATES, ids=lambda p: p.name)
def test_passrole_covers_every_service_the_layer_hands_roles_to(path):
    roles = {r: t for r, _, t in _deploying_roles()}
    template = _load(path)
    role = next(
        r for r in template["Resources"].values() if r.get("Type") == "AWS::IAM::Role"
    )
    deployed = roles.get(_sub(role["Properties"]["RoleName"]))
    if not deployed:
        pytest.skip("buildspec deploys no stacks")
    allowed = _passrole_services(template)
    missing = {}
    for name in deployed:
        stack = CFN_DIR / name
        if not stack.exists() or name.startswith("codebuild-"):
            continue
        for logical_id, resource in (_load(stack).get("Resources") or {}).items():
            for prop, service in ROLE_PROPS.get(resource.get("Type"), []):
                if service not in allowed and _values_at(
                    resource.get("Properties") or {}, prop
                ):
                    missing.setdefault(service, []).append(f"{name}:{logical_id}")
    assert not missing, (
        f"{path.name}: stacks pass roles to services its PassRole grants do not allow "
        f"(deploy would fail with AccessDenied): {missing}"
    )


# Buildspec linting must fail the build on a template error (it previously
# swallowed every exit code with `|| echo`), and cfn-lint is pinned so a new
# upstream rule cannot fail a deploy that passed the day before.
CFN_LINT_PIN = "cfn-lint==1.57.2"


@pytest.mark.parametrize("path", BUILDSPECS, ids=lambda p: p.name)
def test_buildspec_lint_failures_fail_the_build(path):
    text = path.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    swallowed = [
        line.strip() for line in lines if re.search(r"cfn-lint\b.*\|\|\s*echo", line)
    ]
    assert (
        not swallowed
    ), f"{path.name}: cfn-lint errors swallowed by '|| echo': {swallowed[:2]}"
    raw = [line.strip() for line in lines if re.match(r"\s*(-\s+)?cfn-lint\s", line)]
    assert (
        not raw
    ), f"{path.name}: call scripts/cfn-lint-wrapper.sh, not cfn-lint directly: {raw[:2]}"
    wrapper_calls = [line for line in lines if "cfn-lint-wrapper.sh" in line]
    unchecked = [line.strip() for line in wrapper_calls if "|| exit 1" not in line]
    assert (
        not unchecked
    ), f"{path.name}: wrapper calls must end with '|| exit 1': {unchecked[:2]}"
    if wrapper_calls:
        assert (
            CFN_LINT_PIN in text
        ), f"{path.name}: calls the wrapper but does not install {CFN_LINT_PIN}"
    installs = [
        line.strip()
        for line in lines
        if re.search(r"pip3? install.*\bcfn-lint\b", line)
    ]
    unpinned = [line for line in installs if CFN_LINT_PIN not in line]
    assert not unpinned, f"{path.name}: unpinned cfn-lint install: {unpinned}"


# Operator least privilege: the AuraDeployer permission set must cover the
# single-command deploy (`deploy.sh deploy <env>` and the bootstrap scripts),
# so replacing AdministratorAccess cannot break it.
OPERATOR_STACKS = [
    "iam-permission-boundaries.yaml",
    "ecr-base-images.yaml",
    "codebuild-bootstrap.yaml",
    "deployment-pipeline.yaml",
]
RESOURCE_ACTIONS = {
    "AWS::IAM::ManagedPolicy": ["iam:CreatePolicy"],
    "AWS::IAM::Role": [
        "iam:CreateRole",
        "iam:PutRolePolicy",
        "iam:AttachRolePolicy",
        "iam:PassRole",
    ],
    "AWS::ECR::Repository": ["ecr:CreateRepository", "ecr:PutLifecyclePolicy"],
    "AWS::S3::Bucket": ["s3:CreateBucket", "s3:PutEncryptionConfiguration"],
    "AWS::Logs::LogGroup": ["logs:CreateLogGroup", "logs:PutRetentionPolicy"],
    "AWS::CodeBuild::Project": ["codebuild:CreateProject"],
    "AWS::CloudWatch::Alarm": ["cloudwatch:PutMetricAlarm"],
    "AWS::SNS::Topic": ["sns:CreateTopic"],
    "AWS::SNS::Subscription": ["sns:Subscribe"],
    "AWS::Lambda::Function": ["lambda:CreateFunction"],
    "AWS::StepFunctions::StateMachine": ["states:CreateStateMachine"],
}
# AWS CLI service names that differ from the IAM action prefix.
CLI_PREFIX = {"stepfunctions": "states"}
# CLI subcommands that map to several or differently named IAM actions.
CLI_ACTIONS = {
    ("cloudformation", "deploy"): [
        "cloudformation:CreateChangeSet",
        "cloudformation:ExecuteChangeSet",
    ],
    ("cloudformation", "wait"): ["cloudformation:DescribeStacks"],
    ("ecr", "get-login-password"): ["ecr:GetAuthorizationToken"],
}
OPERATOR_SCRIPTS = [
    REPO / "deploy" / "deploy.sh",
    REPO / "deploy" / "scripts" / "bootstrap-fresh-account.sh",
    REPO / "deploy" / "scripts" / "bootstrap-base-images.sh",
]


def _deployer_allows(action: str) -> bool:
    import fnmatch

    permission_set = _load(CFN_DIR / "identity-center-permission-sets.yaml")[
        "Resources"
    ]["AuraDeployerPermissionSet"]
    statements = permission_set["Properties"]["InlinePolicy"]["Statement"]
    for statement in statements:
        if statement.get("Effect") != "Allow":
            continue
        actions = (
            statement["Action"]
            if isinstance(statement["Action"], list)
            else [statement["Action"]]
        )
        if any(fnmatch.fnmatchcase(action, a) for a in actions):
            return True
    return False


def _cli_to_actions(service: str, verb: str) -> list[str]:
    if (service, verb) in CLI_ACTIONS:
        return CLI_ACTIONS[(service, verb)]
    prefix = CLI_PREFIX.get(service, service)
    return [f"{prefix}:" + "".join(part.capitalize() for part in verb.split("-"))]


def test_deployer_permission_set_covers_operator_stacks():
    missing = []
    for name in OPERATOR_STACKS:
        for logical_id, resource in _load(CFN_DIR / name)["Resources"].items():
            for action in RESOURCE_ACTIONS.get(resource["Type"], []):
                if not _deployer_allows(action):
                    missing.append(f"{name}:{logical_id} needs {action}")
            assert resource["Type"] in RESOURCE_ACTIONS, (
                f"{name}:{logical_id} has type {resource['Type']}; add its create actions to "
                "RESOURCE_ACTIONS and to the AuraDeployer permission set"
            )
    assert (
        not missing
    ), "AuraDeployer cannot deploy the bootstrap stacks:\n" + "\n".join(missing)


def test_deployer_permission_set_covers_operator_cli_calls():
    missing = set()
    for script in OPERATOR_SCRIPTS:
        for service, verb in re.findall(
            r"\baws ([a-z0-9-]+) ([a-z0-9-]+)", script.read_text(encoding="utf-8")
        ):
            for action in _cli_to_actions(service, verb):
                read_only = action.split(":")[1].startswith(("Describe", "List", "Get"))
                # ViewOnlyAccess covers metadata Describe/List calls; data reads must be explicit.
                if (
                    read_only
                    and not action.startswith(("ssm:", "ecr:"))
                    and service != "cloudformation"
                ):
                    continue
                if not _deployer_allows(action):
                    missing.add(f"{script.name}: aws {service} {verb} -> {action}")
    assert not missing, "AuraDeployer cannot run the operator scripts:\n" + "\n".join(
        sorted(missing)
    )


# Wrong-account guard used by the bootstrap preflight and the k8s-deploy layer.
def _run_account_check(tmp_path, env: str, caller: str, ssm_value: str | None):
    import os
    import subprocess

    fake_aws = tmp_path / "aws"
    body = f'echo "{ssm_value}"' if ssm_value is not None else "exit 254"
    fake_aws.write_text(f"#!/bin/bash\n{body}\n")
    fake_aws.chmod(0o755)
    env_vars = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    return subprocess.run(
        [str(REPO / "deploy" / "scripts" / "validate-account-id.sh"), env, caller],
        capture_output=True,
        text=True,
        env=env_vars,
        check=False,
    )


def test_account_check_prefers_ssm_and_rejects_mismatch(tmp_path):
    ok = _run_account_check(tmp_path, "dev", "111111111111", "111111111111")
    assert ok.returncode == 0 and "SSM /aura/dev/account-id" in ok.stdout
    bad = _run_account_check(tmp_path, "dev", "999999999999", "111111111111")
    assert bad.returncode == 1 and "mismatch" in bad.stdout


def test_account_check_treats_placeholder_mapping_as_unset(tmp_path):
    # No SSM parameter; the committed mapping holds documentation placeholders.
    result = _run_account_check(tmp_path, "dev", "111111111111", None)
    assert result.returncode == 1
    assert "No account ID configured" in result.stdout
