# ADR-092 Static Action Scan Report

Offline cross-reference of IAM actions used across `deploy/cloudformation/` templates vs. the ADR-092 scoped policy.

## Summary

- Templates scanned: **187**
- Actions granted by ADR-092 scoped policy: **661**
- Action references found in templates: **4578**
- Covered: **3490** | Uncovered (gaps): **1088** | Unique uncovered actions: **336**

## Result: ⚠️ Gaps found

Each row below is an action that one of the platform's IAM resources lists, but that the ADR-092 scoped policy does NOT grant. **Important: this does not necessarily mean the CFN deploy role needs this action.** Most of these actions are granted to OTHER principals (Lambda execution roles, EKS pods, etc.), not the CFN deploy role itself. Use this as a discovery list, not a fix list. The CFN deploy role only needs actions that the platform takes on AWS APIs at deploy time, which is a smaller subset.

## Uncovered actions by service

### `*` (1 unique actions)

- `*`
  - model-assurance-sandbox.yaml

### `acm` (2 unique actions)

- `acm:GetCertificate`
  - iam-palantir-integration.yaml
- `acm:ListCertificates`
  - alb-controller.yaml
  - codebuild-compute.yaml
  - codebuild-marketing.yaml
  - iam-palantir-integration.yaml

### `application-autoscaling` (6 unique actions)

- `application-autoscaling:DeleteScalingPolicy`
  - codebuild-serverless-symbol-resolver.yaml
- `application-autoscaling:DeregisterScalableTarget`
  - codebuild-serverless-symbol-resolver.yaml
- `application-autoscaling:DescribeScalableTargets`
  - codebuild-serverless-symbol-resolver.yaml
- `application-autoscaling:DescribeScalingPolicies`
  - codebuild-serverless-symbol-resolver.yaml
- `application-autoscaling:PutScalingPolicy`
  - codebuild-serverless-symbol-resolver.yaml
- `application-autoscaling:RegisterScalableTarget`
  - codebuild-serverless-symbol-resolver.yaml

### `autoscaling` (3 unique actions)

- `autoscaling:DeletePolicy`
  - codebuild-compute.yaml
- `autoscaling:PutScalingPolicy`
  - codebuild-compute.yaml
- `autoscaling:TerminateInstanceInAutoScalingGroup`
  - codebuild-compute.yaml
  - irsa-cluster-autoscaler.yaml

### `aws-marketplace` (4 unique actions)

- `aws-marketplace:BatchMeterUsage`
  - archive/marketplace.yaml
- `aws-marketplace:GetEntitlements`
  - archive/marketplace.yaml
- `aws-marketplace:MeterUsage`
  - archive/marketplace.yaml
- `aws-marketplace:ResolveCustomer`
  - archive/marketplace.yaml

### `backup-storage` (8 unique actions)

- `backup-storage:GetChunk`
  - codebuild-observability.yaml
- `backup-storage:GetObjectMetadata`
  - codebuild-observability.yaml
- `backup-storage:ListChunks`
  - codebuild-observability.yaml
- `backup-storage:MountBackupStorage`
  - codebuild-observability.yaml
- `backup-storage:MountCapsule`
  - codebuild-observability.yaml
- `backup-storage:NotifyObjectComplete`
  - codebuild-observability.yaml
- `backup-storage:PutObject`
  - codebuild-observability.yaml
- `backup-storage:StartObject`
  - codebuild-observability.yaml

### `bedrock` (13 unique actions)

- `bedrock:ApplyGuardrail`
  - incident-investigation-workflow.yaml
- `bedrock:CreateProvisionedModelThroughput`
  - codebuild-application.yaml
- `bedrock:DeleteGuardrailVersion`
  - codebuild-application.yaml
- `bedrock:DeleteProvisionedModelThroughput`
  - codebuild-application.yaml
- `bedrock:GetFoundationModel`
  - codebuild-application.yaml
- `bedrock:GetGuardrailVersion`
  - codebuild-application.yaml
- `bedrock:GetProvisionedModelThroughput`
  - codebuild-application.yaml
- `bedrock:InvokeModel`
  - archive/ecs-dev-cluster.yaml
  - aura-bedrock-infrastructure.yaml
  - chat-assistant.yaml
  - codebuild-application.yaml
  - codebuild-runbook-agent.yaml
  - ...and 10 more templates
- `bedrock:InvokeModelWithResponseStream`
  - archive/ecs-dev-cluster.yaml
  - aura-bedrock-infrastructure.yaml
  - chat-assistant.yaml
  - codebuild-application.yaml
  - constitutional-ai-evaluation.yaml
  - ...and 8 more templates
- `bedrock:ListFoundationModels`
  - codebuild-application.yaml
- `bedrock:ListGuardrailVersions`
  - codebuild-application.yaml
- `bedrock:ListProvisionedModelThroughputs`
  - codebuild-application.yaml
- `bedrock:UpdateProvisionedModelThroughput`
  - codebuild-application.yaml

### `budgets` (7 unique actions)

- `budgets:Describe*`
  - account-bootstrap.yaml
- `budgets:DescribeBudgets`
  - codebuild-observability.yaml
- `budgets:TagResource`
  - codebuild-application.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - codebuild-ssr.yaml
- `budgets:UntagResource`
  - codebuild-application.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - codebuild-ssr.yaml
- `budgets:UpdateBudget`
  - codebuild-observability.yaml
- `budgets:View*`
  - account-bootstrap.yaml
- `budgets:ViewBudget`
  - codebuild-application.yaml
  - codebuild-sandbox.yaml
  - codebuild-ssr.yaml

### `ce` (15 unique actions)

- `ce:CreateAnomalyMonitor`
  - codebuild-observability.yaml
- `ce:CreateAnomalySubscription`
  - codebuild-observability.yaml
- `ce:DeleteAnomalyMonitor`
  - codebuild-observability.yaml
- `ce:DeleteAnomalySubscription`
  - codebuild-observability.yaml
- `ce:Describe*`
  - account-bootstrap.yaml
- `ce:Get*`
  - account-bootstrap.yaml
- `ce:GetAnomalyMonitors`
  - codebuild-observability.yaml
- `ce:GetAnomalySubscriptions`
  - codebuild-observability.yaml
- `ce:GetCostAndUsage`
  - org-cost-monitoring.yaml
- `ce:GetCostForecast`
  - org-cost-monitoring.yaml
- `ce:List*`
  - account-bootstrap.yaml
- `ce:TagResource`
  - codebuild-observability.yaml
- `ce:UntagResource`
  - codebuild-observability.yaml
- `ce:UpdateAnomalyMonitor`
  - codebuild-observability.yaml
- `ce:UpdateAnomalySubscription`
  - codebuild-observability.yaml

### `cloudformation` (5 unique actions)

- `cloudformation:DescribeStackDriftDetectionStatus`
  - archive/drift-detection.yaml
  - dr-monitoring.yaml
  - drift-detection.yaml
- `cloudformation:DescribeStackResourceDrifts`
  - archive/drift-detection.yaml
  - dr-monitoring.yaml
  - drift-detection.yaml
- `cloudformation:DetectStackDrift`
  - archive/drift-detection.yaml
  - dr-monitoring.yaml
  - drift-detection.yaml
- `cloudformation:ListExports`
  - codebuild-marketing.yaml
- `cloudformation:ListStacks`
  - archive/drift-detection.yaml
  - codebuild-runbook-agent.yaml
  - deployment-pipeline.yaml
  - drift-detection.yaml

### `cloudfront` (10 unique actions)

- `cloudfront:CreateFunction`
  - codebuild-marketing.yaml
- `cloudfront:DeleteFunction`
  - codebuild-marketing.yaml
- `cloudfront:DescribeFunction`
  - codebuild-marketing.yaml
- `cloudfront:GetFunction`
  - codebuild-marketing.yaml
- `cloudfront:GetInvalidation`
  - codebuild-marketing.yaml
- `cloudfront:GetOriginAccessControl`
  - codebuild-marketing.yaml
- `cloudfront:ListDistributions`
  - codebuild-marketing.yaml
- `cloudfront:ListFunctions`
  - codebuild-marketing.yaml
- `cloudfront:PublishFunction`
  - codebuild-marketing.yaml
- `cloudfront:UpdateFunction`
  - codebuild-marketing.yaml

### `cloudtrail` (12 unique actions)

- `cloudtrail:AddTags`
  - codebuild-serverless.yaml
- `cloudtrail:CreateTrail`
  - codebuild-serverless.yaml
- `cloudtrail:DeleteTrail`
  - codebuild-serverless.yaml
- `cloudtrail:DescribeTrails`
  - codebuild-serverless.yaml
- `cloudtrail:GetEventSelectors`
  - codebuild-serverless.yaml
- `cloudtrail:GetTrail`
  - codebuild-serverless.yaml
- `cloudtrail:ListTags`
  - codebuild-serverless.yaml
- `cloudtrail:PutEventSelectors`
  - codebuild-serverless.yaml
- `cloudtrail:RemoveTags`
  - codebuild-serverless.yaml
- `cloudtrail:StartLogging`
  - codebuild-serverless.yaml
- `cloudtrail:StopLogging`
  - codebuild-serverless.yaml
- `cloudtrail:UpdateTrail`
  - codebuild-serverless.yaml

### `cloudwatch` (2 unique actions)

- `cloudwatch:DisableAlarmActions`
  - codebuild-compute.yaml
  - codebuild-data.yaml
  - codebuild-observability.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - ...and 4 more templates
- `cloudwatch:EnableAlarmActions`
  - codebuild-compute.yaml
  - codebuild-data.yaml
  - codebuild-observability.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - ...and 4 more templates

### `codebuild` (10 unique actions)

- `codebuild:BatchGetBuilds`
  - codebuild-runbook-agent.yaml
  - deployment-pipeline.yaml
- `codebuild:BatchPutCodeCoverages`
  - codebuild-foundation.yaml
  - codebuild-integration-test.yaml
  - codebuild-runbook-agent.yaml
- `codebuild:BatchPutTestCases`
  - codebuild-foundation.yaml
  - codebuild-integration-test.yaml
  - codebuild-runbook-agent.yaml
- `codebuild:CreateReport`
  - codebuild-foundation.yaml
  - codebuild-integration-test.yaml
  - codebuild-runbook-agent.yaml
- `codebuild:ListBuilds`
  - codebuild-runbook-agent.yaml
- `codebuild:ListBuildsForProject`
  - codebuild-runbook-agent.yaml
- `codebuild:ListProjects`
  - codebuild-runbook-agent.yaml
- `codebuild:StartBuild`
  - deployment-pipeline.yaml
  - runbook-agent.yaml
- `codebuild:StopBuild`
  - deployment-pipeline.yaml
- `codebuild:UpdateReport`
  - codebuild-foundation.yaml
  - codebuild-integration-test.yaml
  - codebuild-runbook-agent.yaml

### `cognito-idp` (9 unique actions)

- `cognito-idp:AdminAddUserToGroup`
  - cognito-dr-hydrator.yaml
  - iam-palantir-integration.yaml
- `cognito-idp:AdminCreateUser`
  - cognito-dr-hydrator.yaml
  - iam-palantir-integration.yaml
- `cognito-idp:AdminGetUser`
  - cognito-dr-hydrator.yaml
  - cognito.yaml
  - iam-palantir-integration.yaml
- `cognito-idp:AdminListGroupsForUser`
  - cognito-dr-hydrator.yaml
  - cognito.yaml
  - iam-palantir-integration.yaml
- `cognito-idp:AdminRemoveUserFromGroup`
  - iam-palantir-integration.yaml
- `cognito-idp:AdminResetUserPassword`
  - cognito-dr-hydrator.yaml
- `cognito-idp:AdminUpdateUserAttributes`
  - iam-palantir-integration.yaml
- `cognito-idp:GetIdentityProviderByIdentifier`
  - iam-palantir-integration.yaml
- `cognito-idp:ListIdentityProviders`
  - iam-palantir-integration.yaml

### `config` (5 unique actions)

- `config:DescribeComplianceByConfigRule`
  - codebuild-security.yaml
- `config:DescribeConfigurationRecorderStatus`
  - codebuild-security.yaml
- `config:DescribeDeliveryChannelStatus`
  - codebuild-security.yaml
- `config:GetComplianceDetailsByConfigRule`
  - codebuild-security.yaml
- `config:PutEvaluations`
  - codebuild-security.yaml

### `cur` (2 unique actions)

- `cur:DescribeReportDefinitions`
  - account-bootstrap.yaml
- `cur:GetUsageReport`
  - account-bootstrap.yaml

### `dynamodb` (14 unique actions)

- `dynamodb:*`
  - test-env-iam.yaml
- `dynamodb:BatchGetItem`
  - capability-governance.yaml
  - gpu-scheduler-irsa.yaml
  - iam-palantir-integration.yaml
  - irsa-aura-api.yaml
  - irsa-memory-service.yaml
  - ...and 1 more templates
- `dynamodb:BatchWriteItem`
  - archive/marketplace.yaml
  - capability-governance.yaml
  - constitutional-audit-queue.yaml
  - env-validator-irsa.yaml
  - gpu-scheduler-irsa.yaml
  - ...and 7 more templates
- `dynamodb:CreateGlobalSecondaryIndex`
  - codebuild-application-identity.yaml
  - codebuild-serverless-documentation.yaml
- `dynamodb:DeleteGlobalSecondaryIndex`
  - codebuild-application-identity.yaml
  - codebuild-serverless-documentation.yaml
- `dynamodb:DeleteItem`
  - archive/marketplace.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - checkpoint-websocket.yaml
  - cloud-discovery.yaml
  - ...and 12 more templates
- `dynamodb:GetItem`
  - archive/marketplace.yaml
  - aura-bedrock-infrastructure.yaml
  - calibration-pipeline.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - ...and 33 more templates
- `dynamodb:GetRecords`
  - dashboard-dynamodb.yaml
- `dynamodb:GetShardIterator`
  - dashboard-dynamodb.yaml
- `dynamodb:PutItem`
  - archive/marketplace.yaml
  - aura-bedrock-infrastructure.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - checkpoint-websocket.yaml
  - ...and 32 more templates
- `dynamodb:Query`
  - archive/marketplace.yaml
  - aura-bedrock-infrastructure.yaml
  - calibration-pipeline.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - ...and 33 more templates
- `dynamodb:Scan`
  - archive/marketplace.yaml
  - aura-bedrock-infrastructure.yaml
  - calibration-pipeline.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - ...and 19 more templates
- `dynamodb:UpdateGlobalSecondaryIndex`
  - codebuild-application-identity.yaml
  - codebuild-serverless-documentation.yaml
- `dynamodb:UpdateItem`
  - archive/marketplace.yaml
  - capability-governance.yaml
  - chat-assistant.yaml
  - checkpoint-websocket.yaml
  - cloud-discovery.yaml
  - ...and 28 more templates

### `ecr` (7 unique actions)

- `ecr:BatchCheckLayerAvailability`
  - account-migration-bootstrap.yaml
  - codebuild-application.yaml
  - codebuild-docker.yaml
  - codebuild-foundation.yaml
  - codebuild-frontend.yaml
  - ...and 6 more templates
- `ecr:BatchDeleteImage`
  - codebuild-sandbox.yaml
- `ecr:CompleteLayerUpload`
  - account-migration-bootstrap.yaml
  - codebuild-application.yaml
  - codebuild-docker.yaml
  - codebuild-foundation.yaml
  - codebuild-frontend.yaml
  - ...and 1 more templates
- `ecr:InitiateLayerUpload`
  - account-migration-bootstrap.yaml
  - codebuild-application.yaml
  - codebuild-docker.yaml
  - codebuild-foundation.yaml
  - codebuild-frontend.yaml
  - ...and 1 more templates
- `ecr:PutImage`
  - account-migration-bootstrap.yaml
  - codebuild-application.yaml
  - codebuild-docker.yaml
  - codebuild-foundation.yaml
  - codebuild-frontend.yaml
  - ...and 1 more templates
- `ecr:StartImageScan`
  - codebuild-foundation.yaml
- `ecr:UploadLayerPart`
  - account-migration-bootstrap.yaml
  - codebuild-application.yaml
  - codebuild-docker.yaml
  - codebuild-foundation.yaml
  - codebuild-frontend.yaml
  - ...and 1 more templates

### `ecs` (5 unique actions)

- `ecs:*`
  - test-env-iam.yaml
- `ecs:RunTask`
  - codebuild-incident-response.yaml
  - incident-investigation-workflow.yaml
  - sandbox.yaml
  - ssr-training-pipeline.yaml
  - test-env-iam.yaml
  - ...and 1 more templates
- `ecs:StopTask`
  - aura-cost-alerts.yaml
  - codebuild-incident-response.yaml
  - incident-investigation-workflow.yaml
  - sandbox.yaml
  - ssr-training-pipeline.yaml
  - ...and 2 more templates
- `ecs:UpdateCluster`
  - codebuild-sandbox.yaml
  - codebuild-ssr.yaml
- `ecs:UpdateClusterSettings`
  - codebuild-serverless.yaml
  - codebuild-vuln-scan.yaml

### `eks` (1 unique actions)

- `eks:AccessKubernetesApi`
  - test-env-iam.yaml

### `elasticache` (15 unique actions)

- `elasticache:AddTagsToResource`
  - codebuild-data.yaml
- `elasticache:CreateCacheParameterGroup`
  - codebuild-data.yaml
- `elasticache:CreateCacheSubnetGroup`
  - codebuild-data.yaml
- `elasticache:CreateReplicationGroup`
  - codebuild-data.yaml
- `elasticache:DeleteCacheParameterGroup`
  - codebuild-data.yaml
- `elasticache:DeleteCacheSubnetGroup`
  - codebuild-data.yaml
- `elasticache:DeleteReplicationGroup`
  - codebuild-data.yaml
- `elasticache:DescribeCacheClusters`
  - iam-palantir-integration.yaml
- `elasticache:DescribeCacheParameterGroups`
  - codebuild-data.yaml
- `elasticache:DescribeCacheSubnetGroups`
  - codebuild-data.yaml
- `elasticache:DescribeReplicationGroups`
  - codebuild-data.yaml
  - iam-palantir-integration.yaml
- `elasticache:ListTagsForResource`
  - codebuild-data.yaml
- `elasticache:ModifyCacheParameterGroup`
  - codebuild-data.yaml
- `elasticache:ModifyReplicationGroup`
  - codebuild-data.yaml
- `elasticache:RemoveTagsFromResource`
  - codebuild-data.yaml

### `elasticloadbalancing` (4 unique actions)

- `elasticloadbalancing:AddListenerCertificates`
  - alb-controller.yaml
- `elasticloadbalancing:RemoveListenerCertificates`
  - alb-controller.yaml
- `elasticloadbalancing:SetIpAddressType`
  - alb-controller.yaml
- `elasticloadbalancing:SetWebAcl`
  - alb-controller.yaml

### `es` (7 unique actions)

- `es:*`
  - codebuild-data.yaml
- `es:ESHttp*`
  - orchestrator-dispatcher.yaml
- `es:ESHttpDelete`
  - archive/ecs-dev-cluster.yaml
  - irsa-aura-api.yaml
- `es:ESHttpGet`
  - archive/ecs-dev-cluster.yaml
  - archive/opensearch-filesystem-index.yaml
  - chat-assistant.yaml
  - incident-investigation-workflow.yaml
  - irsa-aura-api.yaml
  - ...and 1 more templates
- `es:ESHttpHead`
  - irsa-aura-api.yaml
- `es:ESHttpPost`
  - archive/ecs-dev-cluster.yaml
  - archive/opensearch-filesystem-index.yaml
  - chat-assistant.yaml
  - incident-investigation-workflow.yaml
  - irsa-aura-api.yaml
  - ...and 1 more templates
- `es:ESHttpPut`
  - archive/ecs-dev-cluster.yaml
  - archive/opensearch-filesystem-index.yaml
  - irsa-aura-api.yaml

### `events` (2 unique actions)

- `events:ListRules`
  - codebuild-data.yaml
  - codebuild-observability.yaml
  - codebuild-security.yaml
  - codebuild-serverless.yaml
- `events:PutEvents`
  - checkpoint-websocket.yaml
  - dashboard-dynamodb.yaml
  - irsa-aura-api.yaml
  - model-assurance-pipeline.yaml
  - runtime-security-correlation.yaml
  - ...and 4 more templates

### `execute-api` (1 unique actions)

- `execute-api:ManageConnections`
  - chat-assistant.yaml
  - checkpoint-websocket.yaml
  - serverless-permission-boundary.yaml

### `guardduty` (7 unique actions)

- `guardduty:CreateDetector`
  - codebuild-security.yaml
- `guardduty:DeleteDetector`
  - codebuild-security.yaml
- `guardduty:GetDetector`
  - codebuild-security.yaml
- `guardduty:ListDetectors`
  - codebuild-security.yaml
- `guardduty:TagResource`
  - codebuild-security.yaml
- `guardduty:UntagResource`
  - codebuild-security.yaml
- `guardduty:UpdateDetector`
  - codebuild-security.yaml

### `iam` (26 unique actions)

- `iam:CreateOpenIDConnectProvider`
  - codebuild-compute.yaml
  - codebuild-foundation.yaml
- `iam:CreatePolicy`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:CreatePolicyVersion`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:DeleteOpenIDConnectProvider`
  - codebuild-compute.yaml
  - codebuild-foundation.yaml
- `iam:DeletePolicy`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:DeletePolicyVersion`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:GetOpenIDConnectProvider`
  - codebuild-compute.yaml
  - codebuild-foundation.yaml
- `iam:GetPolicy`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:GetPolicyVersion`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:GetServerCertificate`
  - alb-controller.yaml
- `iam:ListAccessKeys`
  - runtime-security-discovery.yaml
- `iam:ListAttachedRolePolicies`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-chat-assistant.yaml
  - codebuild-compute.yaml
  - codebuild-env-validator.yaml
  - ...and 9 more templates
- `iam:ListPolicyVersions`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 1 more templates
- `iam:ListRolePolicies`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-chat-assistant.yaml
  - codebuild-compute.yaml
  - codebuild-env-validator.yaml
  - ...and 9 more templates
- `iam:ListRoleTags`
  - codebuild-data.yaml
  - codebuild-vuln-scan.yaml
- `iam:ListRoles`
  - runtime-security-discovery.yaml
- `iam:ListServerCertificates`
  - alb-controller.yaml
- `iam:PutRolePermissionsBoundary`
  - codebuild-env-validator.yaml
  - codebuild-serverless-symbol-resolver.yaml
  - codebuild-serverless.yaml
- `iam:SetDefaultPolicyVersion`
  - codebuild-serverless.yaml
- `iam:TagInstanceProfile`
  - codebuild-compute.yaml
- `iam:TagOpenIDConnectProvider`
  - codebuild-compute.yaml
  - codebuild-foundation.yaml
- `iam:TagPolicy`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
- `iam:UntagInstanceProfile`
  - codebuild-compute.yaml
- `iam:UntagPolicy`
  - codebuild-application.yaml
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
- `iam:UpdateAssumeRolePolicy`
  - codebuild-bootstrap.yaml
  - codebuild-compute.yaml
  - codebuild-env-validator.yaml
  - codebuild-observability.yaml
  - codebuild-sandbox.yaml
  - ...and 3 more templates
- `iam:UpdateRoleDescription`
  - codebuild-sandbox.yaml

### `kinesis` (7 unique actions)

- `kinesis:DescribeStream`
  - audit-pipeline.yaml
  - iam-palantir-integration.yaml
- `kinesis:DescribeStreamSummary`
  - iam-palantir-integration.yaml
- `kinesis:GetRecords`
  - audit-pipeline.yaml
  - iam-palantir-integration.yaml
- `kinesis:GetShardIterator`
  - audit-pipeline.yaml
  - iam-palantir-integration.yaml
- `kinesis:ListShards`
  - audit-pipeline.yaml
- `kinesis:PutRecord`
  - iam-palantir-integration.yaml
- `kinesis:PutRecords`
  - iam-palantir-integration.yaml

### `kms` (2 unique actions)

- `kms:GenerateDataKey*`
  - account-migration-bootstrap.yaml
  - red-team.yaml
  - ssr-training.yaml
  - vuln-scan-iam.yaml
- `kms:ReEncrypt*`
  - account-migration-bootstrap.yaml

### `lambda` (8 unique actions)

- `lambda:*`
  - test-env-iam.yaml
- `lambda:CreateFunctionUrlConfig`
  - codebuild-serverless.yaml
- `lambda:DeleteFunctionUrlConfig`
  - codebuild-serverless.yaml
- `lambda:GetFunctionUrlConfig`
  - codebuild-serverless.yaml
- `lambda:InvokeFunction`
  - codebuild-chat-assistant.yaml
  - codebuild-incident-response.yaml
  - codebuild-observability.yaml
  - codebuild-serverless.yaml
  - deployment-pipeline.yaml
  - ...and 8 more templates
- `lambda:ListEventSourceMappings`
  - codebuild-data.yaml
  - codebuild-serverless.yaml
- `lambda:ListLayerVersions`
  - codebuild-sandbox.yaml
- `lambda:UpdateFunctionUrlConfig`
  - codebuild-serverless.yaml

### `logs` (3 unique actions)

- `logs:*`
  - test-env-iam.yaml
- `logs:TagLogGroup`
  - codebuild-application.yaml
  - codebuild-observability.yaml
  - codebuild-security.yaml
  - iam-palantir-integration.yaml
  - test-env-iam.yaml
- `logs:UntagLogGroup`
  - codebuild-application.yaml
  - codebuild-observability.yaml
  - codebuild-security.yaml
  - test-env-iam.yaml

### `neptune-db` (7 unique actions)

- `neptune-db:*`
  - codebuild-data.yaml
  - incident-investigation-workflow.yaml
  - orchestrator-dispatcher.yaml
- `neptune-db:CancelQuery`
  - archive/ecs-dev-cluster.yaml
- `neptune-db:DeleteDataViaQuery`
  - archive/ecs-dev-cluster.yaml
  - irsa-aura-api.yaml
- `neptune-db:GetQueryStatus`
  - archive/ecs-dev-cluster.yaml
  - runtime-security-correlation.yaml
  - runtime-security-discovery.yaml
- `neptune-db:ReadDataViaQuery`
  - archive/ecs-dev-cluster.yaml
  - irsa-aura-api.yaml
  - runtime-security-correlation.yaml
  - runtime-security-discovery.yaml
- `neptune-db:WriteDataViaQuery`
  - archive/ecs-dev-cluster.yaml
  - irsa-aura-api.yaml
  - runtime-security-discovery.yaml
- `neptune-db:connect`
  - archive/ecs-dev-cluster.yaml
  - irsa-aura-api.yaml
  - symbol-resolver-tier3.yaml

### `pricing` (3 unique actions)

- `pricing:DescribeServices`
  - account-bootstrap.yaml
- `pricing:GetAttributeValues`
  - account-bootstrap.yaml
- `pricing:GetProducts`
  - account-bootstrap.yaml

### `rds` (1 unique actions)

- `rds:CopyDBClusterSnapshot`
  - account-migration-bootstrap.yaml

### `route53` (5 unique actions)

- `route53:GetHealthCheck`
  - archive/multi-region-global.yaml
- `route53:GetHealthCheckStatus`
  - archive/multi-region-global.yaml
- `route53:ListHealthChecks`
  - archive/multi-region-global.yaml
- `route53:ListHostedZones`
  - route53-cross-account-role.yaml
- `route53:ListHostedZonesByName`
  - route53-cross-account-role.yaml

### `s3` (32 unique actions)

- `s3:*`
  - codebuild-data.yaml
  - test-env-iam.yaml
- `s3:AbortMultipartUpload`
  - audit-pipeline.yaml
- `s3:DeleteObjectVersion`
  - test-env-iam.yaml
- `s3:GetBucketAcl`
  - codebuild-bootstrap.yaml
  - codebuild-foundation.yaml
  - codebuild-runtime-security.yaml
  - codebuild-security.yaml
  - codebuild-serverless.yaml
- `s3:GetBucketCORS`
  - codebuild-marketing.yaml
- `s3:GetBucketCors`
  - codebuild-application.yaml
- `s3:GetBucketEncryption`
  - codebuild-application.yaml
  - codebuild-serverless-documentation.yaml
  - codebuild-ssr.yaml
- `s3:GetBucketOwnershipControls`
  - codebuild-marketing.yaml
- `s3:GetBucketPublicAccessBlock`
  - codebuild-application.yaml
  - codebuild-marketing.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - codebuild-security.yaml
  - ...and 2 more templates
- `s3:GetBucketTagging`
  - codebuild-application.yaml
  - codebuild-marketing.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - codebuild-security.yaml
  - ...and 4 more templates
- `s3:GetBucketVersioning`
  - archive/config-compliance.yaml
  - codebuild-application.yaml
  - codebuild-marketing.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - ...and 6 more templates
- `s3:GetBucketWebsite`
  - codebuild-marketing.yaml
- `s3:GetEncryptionConfiguration`
  - codebuild-application.yaml
  - codebuild-marketing.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - codebuild-security.yaml
  - ...and 3 more templates
- `s3:GetLifecycleConfiguration`
  - codebuild-application.yaml
  - codebuild-marketing.yaml
  - codebuild-runtime-security.yaml
  - codebuild-sandbox.yaml
  - codebuild-security.yaml
  - ...and 4 more templates
- `s3:GetObjectAttributes`
  - constitutional-ai-evaluation.yaml
- `s3:GetObjectLegalHold`
  - audit-pipeline.yaml
- `s3:GetObjectRetention`
  - audit-pipeline.yaml
- `s3:GetObjectVersion`
  - irsa-memory-service.yaml
- `s3:GetObjectVersionAcl`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:GetObjectVersionForReplication`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:GetObjectVersionTagging`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:GetReplicationConfiguration`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:HeadObject`
  - calibration-pipeline.yaml
- `s3:ListBucketMultipartUploads`
  - audit-pipeline.yaml
- `s3:ListBucketVersions`
  - test-env-iam.yaml
- `s3:PutBucketEncryption`
  - codebuild-application.yaml
  - codebuild-serverless-documentation.yaml
  - codebuild-ssr.yaml
- `s3:PutBucketOwnershipControls`
  - codebuild-bootstrap.yaml
  - codebuild-foundation.yaml
  - codebuild-marketing.yaml
- `s3:PutBucketWebsite`
  - codebuild-marketing.yaml
- `s3:PutObjectRetention`
  - dr-compliance-controls.yaml
- `s3:ReplicateDelete`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:ReplicateObject`
  - audit-pipeline.yaml
  - s3.yaml
- `s3:ReplicateTags`
  - audit-pipeline.yaml
  - s3.yaml

### `scheduler` (2 unique actions)

- `scheduler:ListScheduleGroups`
  - codebuild-observability.yaml
- `scheduler:ListSchedules`
  - codebuild-observability.yaml

### `servicecatalog` (12 unique actions)

- `servicecatalog:DescribeConstraint`
  - codebuild-sandbox.yaml
- `servicecatalog:DescribeProductAsAdmin`
  - codebuild-sandbox.yaml
- `servicecatalog:DescribeProvisionedProduct`
  - test-env-iam.yaml
- `servicecatalog:DescribeProvisioningArtifact`
  - test-env-iam.yaml
- `servicecatalog:DescribeProvisioningParameters`
  - test-env-iam.yaml
- `servicecatalog:ListAcceptedPortfolioShares`
  - codebuild-sandbox.yaml
- `servicecatalog:ListConstraintsForPortfolio`
  - codebuild-sandbox.yaml
- `servicecatalog:ListPortfolios`
  - codebuild-sandbox.yaml
- `servicecatalog:ListProvisioningArtifacts`
  - codebuild-sandbox.yaml
  - test-env-iam.yaml
- `servicecatalog:ProvisionProduct`
  - test-env-iam.yaml
- `servicecatalog:SearchProductsAsAdmin`
  - codebuild-sandbox.yaml
- `servicecatalog:TerminateProvisionedProduct`
  - test-env-iam.yaml

### `ses` (2 unique actions)

- `ses:SendEmail`
  - codebuild-serverless.yaml
  - hitl-scheduler.yaml
  - threat-intel-scheduler.yaml
- `ses:SendRawEmail`
  - codebuild-serverless.yaml
  - hitl-scheduler.yaml
  - threat-intel-scheduler.yaml

### `shield` (4 unique actions)

- `shield:CreateProtection`
  - alb-controller.yaml
- `shield:DeleteProtection`
  - alb-controller.yaml
- `shield:DescribeProtection`
  - alb-controller.yaml
- `shield:GetSubscriptionState`
  - alb-controller.yaml

### `sns` (3 unique actions)

- `sns:*`
  - test-env-iam.yaml
- `sns:ListTopics`
  - codebuild-observability.yaml
  - codebuild-security.yaml
  - codebuild-serverless.yaml
- `sns:Publish`
  - archive/config-compliance.yaml
  - archive/drift-detection.yaml
  - archive/multi-region-global.yaml
  - aura-cost-alerts.yaml
  - calibration-pipeline.yaml
  - ...and 33 more templates

### `sqs` (5 unique actions)

- `sqs:*`
  - test-env-iam.yaml
- `sqs:ChangeMessageVisibility`
  - gpu-scheduler-irsa.yaml
  - iam-palantir-integration.yaml
  - orchestrator-dispatcher.yaml
  - serverless-permission-boundary.yaml
- `sqs:DeleteMessage`
  - capability-governance.yaml
  - constitutional-audit-queue.yaml
  - gpu-scheduler-irsa.yaml
  - iam-palantir-integration.yaml
  - irsa-aura-api.yaml
  - ...and 4 more templates
- `sqs:ReceiveMessage`
  - capability-governance.yaml
  - constitutional-audit-queue.yaml
  - gpu-scheduler-irsa.yaml
  - iam-palantir-integration.yaml
  - irsa-aura-api.yaml
  - ...and 4 more templates
- `sqs:SendMessage`
  - capability-governance.yaml
  - gpu-scheduler-irsa.yaml
  - iam-palantir-integration.yaml
  - irsa-aura-api.yaml
  - realtime-monitoring.yaml
  - ...and 4 more templates

### `ssm` (2 unique actions)

- `ssm:DescribeParameters`
  - codebuild-serverless-symbol-resolver.yaml
- `ssm:GetParametersByPath`
  - codebuild-data.yaml
  - codebuild-foundation.yaml
  - iam-diagram-service.yaml
  - red-team.yaml
  - runtime-security-discovery.yaml
  - ...and 1 more templates

### `states` (10 unique actions)

- `states:*`
  - test-env-iam.yaml
- `states:DescribeExecution`
  - dr-compliance-controls.yaml
  - orchestrator-dispatcher.yaml
  - test-env-iam.yaml
- `states:DescribeStateMachineForExecution`
  - codebuild-serverless.yaml
- `states:GetExecutionHistory`
  - dr-compliance-controls.yaml
- `states:ListStateMachines`
  - codebuild-incident-response.yaml
  - codebuild-sandbox.yaml
  - codebuild-serverless.yaml
  - codebuild-ssr.yaml
- `states:SendTaskFailure`
  - dr-compliance-controls.yaml
  - hitl-callback.yaml
- `states:SendTaskHeartbeat`
  - hitl-callback.yaml
- `states:SendTaskSuccess`
  - dr-compliance-controls.yaml
  - hitl-callback.yaml
- `states:StartExecution`
  - incident-investigation-workflow.yaml
  - model-assurance-pipeline.yaml
  - orchestrator-dispatcher.yaml
  - test-env-iam.yaml
- `states:StopExecution`
  - test-env-iam.yaml

### `sts` (1 unique actions)

- `sts:GetCallerIdentity`
  - codebuild-integration-test.yaml
  - codebuild-k8s-deploy.yaml
  - codebuild-marketing.yaml
  - dr-compliance-controls.yaml
  - test-env-iam.yaml

### `waf-regional` (4 unique actions)

- `waf-regional:AssociateWebACL`
  - alb-controller.yaml
- `waf-regional:DisassociateWebACL`
  - alb-controller.yaml
- `waf-regional:GetWebACL`
  - alb-controller.yaml
- `waf-regional:GetWebACLForResource`
  - alb-controller.yaml

### `wafv2` (15 unique actions)

- `wafv2:AssociateWebACL`
  - alb-controller.yaml
  - codebuild-foundation.yaml
- `wafv2:CreateWebACL`
  - codebuild-foundation.yaml
- `wafv2:DeleteLoggingConfiguration`
  - codebuild-foundation.yaml
- `wafv2:DeleteWebACL`
  - codebuild-foundation.yaml
- `wafv2:DisassociateWebACL`
  - alb-controller.yaml
  - codebuild-foundation.yaml
- `wafv2:GetLoggingConfiguration`
  - codebuild-foundation.yaml
- `wafv2:GetWebACL`
  - alb-controller.yaml
  - codebuild-foundation.yaml
- `wafv2:GetWebACLForResource`
  - alb-controller.yaml
- `wafv2:ListLoggingConfigurations`
  - codebuild-foundation.yaml
- `wafv2:ListTagsForResource`
  - codebuild-foundation.yaml
- `wafv2:ListWebACLs`
  - codebuild-foundation.yaml
- `wafv2:PutLoggingConfiguration`
  - codebuild-foundation.yaml
- `wafv2:TagResource`
  - codebuild-foundation.yaml
- `wafv2:UntagResource`
  - codebuild-foundation.yaml
- `wafv2:UpdateWebACL`
  - codebuild-foundation.yaml

### `xray` (5 unique actions)

- `xray:GetSamplingRules`
  - otel-collector.yaml
- `xray:GetSamplingStatisticSummaries`
  - otel-collector.yaml
- `xray:GetSamplingTargets`
  - otel-collector.yaml
- `xray:PutTelemetryRecords`
  - deployment-pipeline.yaml
  - otel-collector.yaml
  - serverless-permission-boundary.yaml
- `xray:PutTraceSegments`
  - deployment-pipeline.yaml
  - otel-collector.yaml
  - serverless-permission-boundary.yaml

## Methodology

- Parser: PyYAML with a custom loader that accepts CloudFormation intrinsic tags (`!Sub`, `!Ref`, `!If`, etc.) without evaluating them
- IAM resource types scanned: `AWS::IAM::Role`, `AWS::IAM::Policy`, `AWS::IAM::ManagedPolicy`
- Effect filter: only `Effect: Allow` statements
- Wildcard matching: case-insensitive `fnmatch` (`s3:*` matches `s3:GetObject`, `s3:Get*` matches `s3:GetObject`)
- ADR-092 grant source: both `CloudFormationScopedManagedPolicy` and the inline policy on `CloudFormationServiceRole` (Statements 4-7 + existing IAM/CFN/Secrets/Bedrock/SSM blocks)
