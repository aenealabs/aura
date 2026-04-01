# ADR-050: Self-Play SWE-RL (SSR) Integration for Agent Training

**Status:** Deployed
**Date:** 2026-01-02 (Infrastructure Deployed & Validated)
**Decision Makers:** Project Aura Platform Team
**Related:** ADR-024 (Titan Neural Memory), ADR-029 (Agent Optimization), ADR-034 (Context Engineering), ADR-039 (Self-Service Test Environments), ADR-042 (Real-Time Agent Intervention)

---

## Executive Summary

This ADR proposes integrating Self-play SWE-RL (SSR), a breakthrough training paradigm from Meta FAIR/UIUC/CMU research (arXiv:2512.18552, December 2025), to enhance Aura's autonomous agent capabilities through self-play reinforcement learning.

**Key Outcomes:**
- Self-improving agent training without human-curated vulnerability data
- 10-15% projected improvement in patch generation accuracy (based on paper results)
- Dual-role architecture: bug-injection agent + bug-solving agent with shared policy
- Higher-order bug generation from failed patch attempts for curriculum learning
- Integration with existing sandbox infrastructure (ADR-039) and GraphRAG (Issue #151)
- Reduced dependency on manually labeled security vulnerability databases

**Research Results (from paper):**
- SWE-bench Verified: +10.4 points improvement (41.0% → 51.4%)
- SWE-Bench Pro: +7.8 points improvement (21.1% → 28.9%)
- Outperforms human-data baselines throughout training trajectory

---

## Context

### Current State

Project Aura's multi-agent system currently relies on:

| Component | Current Approach | Limitation |
|-----------|------------------|------------|
| **Coder Agent** | Pre-trained LLM (Bedrock Claude) | No domain-specific fine-tuning |
| **Reviewer Agent** | Static rule-based + LLM | Limited learning from feedback |
| **Validator Agent** | Test execution in sandbox | No self-improvement capability |
| **Training Data** | Human-curated CVEs, public datasets | Expensive, limited scale |
| **Patch Validation** | Pass/fail test execution | Binary signal, no curriculum |

### Problem Statement

1. **Data Scarcity:** High-quality labeled vulnerability data is expensive and limited
2. **Static Agents:** Current agents don't improve from production experience
3. **Limited Generalization:** Training on public CVEs may not cover customer-specific patterns
4. **Manual Curation Overhead:** Each new vulnerability type requires human labeling effort
5. **No Adversarial Training:** Agents aren't tested against sophisticated bug patterns

### Research Breakthrough: Self-play SWE-RL (SSR)

The SSR paper (December 2025) demonstrates that software agents can self-improve through:

1. **Minimal Data Assumptions:** Only sandboxed repositories with dependencies required
2. **Dual-Role Self-Play:** Single LLM plays bug-injector and bug-solver roles
3. **Automated Curriculum:** Higher-order bugs from failed attempts create natural progression
4. **Test-Based Verification:** Formal specification via test patches, not natural language

**Key Innovation:** The bug-injection agent learns to create increasingly challenging bugs that push the solver agent's capabilities, while the solver agent learns to fix progressively complex issues.

### Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| R1 | Implement bug artifact infrastructure compatible with Aura sandbox | P0 |
| R2 | Dual-role self-play training loop with shared policy | P0 |
| R3 | Integration with existing EKS sandbox namespaces (ADR-039) | P0 |
| R4 | Consistency validation pipeline (7-stage verification) | P0 |
| R5 | Higher-order bug generation from failed solver attempts | P1 |
| R6 | History-aware bug injection leveraging GraphRAG | P1 |
| R7 | Integration with Titan Neural Memory (ADR-024) | P1 |
| R8 | Observability metrics for training progress | P1 |
| R9 | Customer repository opt-in for training data | P2 |
| R10 | HITL approval for production deployment of trained models | P2 |

---

## Decision

**Implement SSR-based self-play training infrastructure for Aura's agents, leveraging existing sandbox environments and GraphRAG capabilities to create a continuously self-improving vulnerability detection and patch generation system.**

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        SSR TRAINING INFRASTRUCTURE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │  Bug-Injection Agent │◄───────►│  Bug-Solving Agent  │                   │
│  │  (Aura Coder reverse)│         │  (Aura Coder)       │                   │
│  └──────────┬──────────┘         └──────────┬──────────┘                   │
│             │                               │                               │
│             ▼                               ▼                               │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │   Bug Artifact       │         │   Patch Artifact    │                   │
│  │   - test_script.sh   │         │   - pred_patch.diff │                   │
│  │   - test_parser.py   │         │   - test_results    │                   │
│  │   - bug_inject.diff  │         │   - validation_log  │                   │
│  │   - test_weaken.diff │         │                     │                   │
│  │   - test_files.txt   │         │                     │                   │
│  └──────────┬──────────┘         └──────────┬──────────┘                   │
│             │                               │                               │
│             ▼                               ▼                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    CONSISTENCY VALIDATION PIPELINE                    │  │
│  │  1. Test files existence    5. Bug validity (min_failing_tests)      │  │
│  │  2. Test parser validity    6. Test weakening validity               │  │
│  │  3. Test script validity    7. Inverse mutation testing              │  │
│  │  4. Bug scope (min_files)                                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│             │                               │                               │
│             ▼                               ▼                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         REWARD COMPUTATION                            │  │
│  │                                                                       │  │
│  │  Bug-Injection Reward:              Bug-Solving Reward:              │  │
│  │  ┌─────────────────────────┐        ┌─────────────────────────┐     │  │
│  │  │ -1.0 if validation fails │        │ +1 if all tests pass    │     │  │
│  │  │ -α if s=0 or s=1        │        │ -1 otherwise            │     │  │
│  │  │ 1-(1+α)s if 0<s<1       │        └─────────────────────────┘     │  │
│  │  └─────────────────────────┘                                        │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│             │                               │                               │
│             └───────────────┬───────────────┘                               │
│                             ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    SHARED POLICY UPDATE (RL)                          │  │
│  │         Joint training on injection + solving trajectories            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        AURA PLATFORM INTEGRATION                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐             │
│  │ EKS Sandbox     │  │ GraphRAG        │  │ Titan Neural    │             │
│  │ (ADR-039)       │  │ (Issue #151)    │  │ Memory (ADR-024)│             │
│  │                 │  │                 │  │                 │             │
│  │ - Ephemeral NS  │  │ - CALL_GRAPH    │  │ - Pattern Store │             │
│  │ - Network Isoln │  │ - DEPENDENCIES  │  │ - Consolidation │             │
│  │ - Resource Quota│  │ - INHERITANCE   │  │ - Surprise Gate │             │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Bug Artifact Specification

Following the SSR paper's artifact structure:

```python
# src/services/ssr/bug_artifact.py
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
from enum import Enum

class BugInjectionStrategy(Enum):
    """Bug injection strategies from SSR paper"""
    REMOVAL_ONLY = "removal"           # Remove code hunks/files
    HISTORY_AWARE = "history"          # Revert historical changes
    REMOVAL_PLUS_HISTORY = "combined"  # Best performing (paper)
    DIRECT_INJECTION = "direct"        # Naive prompting (baseline)

@dataclass
class BugArtifact:
    """
    Standardized bug artifact format compatible with SSR training.

    Reference: Self-play SWE-RL paper, Section 2.3
    """
    # Required artifact files
    test_script: Path           # Bash script to run test suite
    test_files: List[Path]      # Oracle test files (reset before validation)
    test_parser: Path           # Python script: stdin log → stdout JSON
    bug_inject_diff: str        # Git diff introducing the bug
    test_weaken_diff: str       # Git diff hiding bug from tests

    # Metadata
    repository_id: str
    commit_sha: str
    injection_strategy: BugInjectionStrategy

    # Validation results
    min_passing_tests: int = 10
    min_changed_files: int = 2
    min_failing_tests: int = 1

    # Higher-order bug tracking
    order: int = 1              # 1 = first-order, 2 = from failed attempt
    parent_artifact_id: Optional[str] = None
    failed_patch_diff: Optional[str] = None  # For higher-order bugs

@dataclass
class ValidationResult:
    """Results from 7-stage consistency validation"""
    test_files_valid: bool
    test_parser_valid: bool
    test_script_valid: bool
    bug_scope_valid: bool
    bug_validity_valid: bool
    test_weakening_valid: bool
    inverse_mutation_valid: bool

    # Detailed metrics
    total_tests: int
    passing_before_bug: int
    failing_after_bug: int
    passing_after_weakening: int

    @property
    def is_valid(self) -> bool:
        return all([
            self.test_files_valid,
            self.test_parser_valid,
            self.test_script_valid,
            self.bug_scope_valid,
            self.bug_validity_valid,
            self.test_weakening_valid,
            self.inverse_mutation_valid
        ])
```

### Self-Play Training Loop

```python
# src/services/ssr/self_play_orchestrator.py
from typing import List, Tuple
import asyncio

class SelfPlayOrchestrator:
    """
    Orchestrates SSR self-play training loop.

    Reference: Self-play SWE-RL paper, Section 2
    """

    def __init__(
        self,
        bug_injector: BugInjectionAgent,
        solver: BugSolvingAgent,
        sandbox_service: SandboxNetworkService,
        graph_service: NeptuneGraphService,
        memory_service: TitanMemoryService,
        config: SSRConfig
    ):
        self.bug_injector = bug_injector
        self.solver = solver
        self.sandbox = sandbox_service
        self.graph = graph_service
        self.memory = memory_service
        self.config = config

        # Training state
        self.training_queue: asyncio.Queue[BugArtifact] = asyncio.Queue()
        self.higher_order_queue: asyncio.Queue[BugArtifact] = asyncio.Queue()

    async def training_iteration(
        self,
        repository: Repository
    ) -> TrainingMetrics:
        """
        Execute one SSR training iteration.

        1. Bug injection phase
        2. Consistency validation
        3. Bug solving phase (G attempts)
        4. Higher-order bug generation from failures
        5. Reward computation
        6. Joint policy update
        """
        metrics = TrainingMetrics()

        # 1. Bug injection phase
        strategy = self._select_injection_strategy()

        async with self.sandbox.create_ephemeral_namespace() as ns:
            # Clone repository into sandbox
            await ns.clone_repository(repository)

            # Generate bug artifact using selected strategy
            bug_artifact = await self.bug_injector.generate_bug(
                namespace=ns,
                repository=repository,
                strategy=strategy,
                graph_context=await self.graph.get_code_structure(repository.id)
            )

            # 2. Consistency validation (7 stages)
            validation = await self._validate_artifact(bug_artifact, ns)

            if not validation.is_valid:
                # Penalize injector for invalid bug
                injector_reward = -1.0
                metrics.invalid_bugs += 1
                await self._update_injector_policy(injector_reward)
                return metrics

            metrics.valid_bugs += 1

            # 3. Bug solving phase (multiple attempts)
            solve_attempts: List[SolveAttempt] = []

            for attempt_idx in range(self.config.group_size):  # G=8 in paper
                async with self.sandbox.create_ephemeral_namespace() as solve_ns:
                    # Construct buggy codebase
                    await self._construct_buggy_codebase(
                        solve_ns, repository, bug_artifact
                    )

                    # Attempt to solve
                    attempt = await self.solver.attempt_fix(
                        namespace=solve_ns,
                        oracle_test_patch=self._reverse_weakening_patch(
                            bug_artifact.test_weaken_diff
                        )
                    )
                    solve_attempts.append(attempt)

            # 4. Higher-order bug generation from failures
            for attempt in solve_attempts:
                if not attempt.passed and not self._is_duplicate(attempt):
                    higher_order = await self._create_higher_order_bug(
                        bug_artifact, attempt
                    )
                    if higher_order:
                        await self.higher_order_queue.put(higher_order)
                        metrics.higher_order_bugs += 1

            # 5. Reward computation
            solve_rate = sum(1 for a in solve_attempts if a.passed) / len(solve_attempts)

            # Bug-injection reward (Equation 1 from paper)
            if solve_rate == 0 or solve_rate == 1:
                injector_reward = -self.config.alpha  # α=0.8 in paper
            else:
                injector_reward = 1 - (1 + self.config.alpha) * solve_rate

            # Bug-solving rewards (binary)
            solver_rewards = [
                1.0 if attempt.passed else -1.0
                for attempt in solve_attempts
            ]

            # 6. Joint policy update
            await self._update_shared_policy(
                injector_reward=injector_reward,
                solver_rewards=solver_rewards,
                injection_trajectory=bug_artifact.trajectory,
                solve_trajectories=[a.trajectory for a in solve_attempts]
            )

            # Store successful patterns in Titan Memory
            if solve_rate > 0:
                await self.memory.store_bug_pattern(
                    bug_artifact=bug_artifact,
                    successful_fixes=[a for a in solve_attempts if a.passed]
                )

            metrics.solve_rate = solve_rate
            metrics.injector_reward = injector_reward

            return metrics

    def _select_injection_strategy(self) -> BugInjectionStrategy:
        """
        Select bug injection strategy.
        Paper finding: removal+history performs best.
        """
        import random
        if random.random() < 0.5:
            return BugInjectionStrategy.REMOVAL_ONLY
        else:
            return BugInjectionStrategy.HISTORY_AWARE
```

### History-Aware Bug Injection with GraphRAG

Leverage Aura's Hybrid GraphRAG for intelligent bug injection:

```python
# src/services/ssr/history_aware_injector.py

class HistoryAwareBugInjector:
    """
    Bug injection leveraging git history and GraphRAG.

    Reference: SSR paper Section 2.3, Figure 3 (right side)
    """

    async def identify_revertible_changes(
        self,
        repository: Repository,
        graph_context: GraphContext
    ) -> List[RevertCandidate]:
        """
        Use GraphRAG to find high-value reversion candidates.

        1. Query Neptune for high-complexity code regions
        2. Cross-reference with git history for bug fixes
        3. Rank candidates by test coverage
        """
        candidates = []

        # Find code with high cyclomatic complexity via Neptune
        complex_regions = await self.graph_service.execute_gremlin(
            f"""
            g.V().has('repository_id', '{repository.id}')
             .has('type', 'function')
             .has('complexity', gte(10))
             .order().by('complexity', desc)
             .limit(50)
             .project('file', 'function', 'complexity')
             .by('file_path')
             .by('name')
             .by('complexity')
            """
        )

        # Cross-reference with git history
        for region in complex_regions:
            git_history = await self._get_file_history(
                repository,
                region['file'],
                keywords=['fix', 'bug', 'issue', 'crash', 'error']
            )

            for commit in git_history:
                # Check test coverage via GraphRAG CALL_GRAPH
                test_coverage = await self.graph_service.query(
                    query=f"tests covering {region['function']}",
                    query_type=GraphQueryType.CALL_GRAPH
                )

                if len(test_coverage) >= self.config.min_test_coverage:
                    candidates.append(RevertCandidate(
                        file_path=region['file'],
                        function_name=region['function'],
                        commit_sha=commit.sha,
                        commit_message=commit.message,
                        test_coverage=test_coverage,
                        complexity_score=region['complexity']
                    ))

        # Rank by reversion value (complexity * test coverage)
        candidates.sort(
            key=lambda c: c.complexity_score * len(c.test_coverage),
            reverse=True
        )

        return candidates[:self.config.max_candidates]
```

### Consistency Validation Pipeline

```python
# src/services/ssr/validation_pipeline.py

class ConsistencyValidationPipeline:
    """
    7-stage consistency validation for bug artifacts.

    Reference: SSR paper Section 2.3, Figure 4
    """

    async def validate(
        self,
        artifact: BugArtifact,
        namespace: SandboxNamespace
    ) -> ValidationResult:
        """Execute all validation stages"""

        result = ValidationResult()

        # Stage 1: Test files existence and coverage
        result.test_files_valid = await self._validate_test_files(
            artifact, namespace
        )
        if not result.test_files_valid:
            return result

        # Stage 2: Test parser validity
        result.test_parser_valid = await self._validate_test_parser(
            artifact, namespace
        )
        if not result.test_parser_valid:
            return result

        # Stage 3: Test script validity (all tests pass on original)
        original_results = await self._run_tests(namespace, artifact)
        result.test_script_valid = (
            all(r == "passed" for r in original_results.values()) and
            len(original_results) >= artifact.min_passing_tests
        )
        result.total_tests = len(original_results)
        result.passing_before_bug = sum(
            1 for r in original_results.values() if r == "passed"
        )
        if not result.test_script_valid:
            return result

        # Stage 4: Bug scope validation
        changed_files = self._count_changed_files(artifact.bug_inject_diff)
        result.bug_scope_valid = changed_files >= artifact.min_changed_files
        if not result.bug_scope_valid:
            return result

        # Stage 5: Bug validity (tests fail after injection)
        await namespace.apply_patch(artifact.bug_inject_diff)
        buggy_results = await self._run_tests(namespace, artifact)
        failing_tests = sum(
            1 for r in buggy_results.values() if r == "failed"
        )
        result.bug_validity_valid = failing_tests >= artifact.min_failing_tests
        result.failing_after_bug = failing_tests
        if not result.bug_validity_valid:
            return result

        # Stage 6: Test weakening validity
        await namespace.apply_patch(artifact.test_weaken_diff)
        weakened_results = await self._run_tests(namespace, artifact)
        passing_after_weaken = sum(
            1 for r in weakened_results.values() if r == "passed"
        )
        # Some previously failing tests should now pass
        result.test_weakening_valid = passing_after_weaken > (
            result.passing_before_bug - result.failing_after_bug
        )
        result.passing_after_weakening = passing_after_weaken
        if not result.test_weakening_valid:
            return result

        # Stage 7: Inverse mutation testing
        result.inverse_mutation_valid = await self._validate_inverse_mutation(
            artifact, namespace
        )

        return result

    async def _validate_inverse_mutation(
        self,
        artifact: BugArtifact,
        namespace: SandboxNamespace
    ) -> bool:
        """
        Verify each modified file contributes to the bug.

        For each file in bug patch:
        1. Reset to full buggy state
        2. Revert only that file to fixed version
        3. Run non-weakened tests
        4. If any failing test passes → file contributes
        """
        changed_files = self._get_changed_files(artifact.bug_inject_diff)

        for file_path in changed_files:
            # Reset to buggy state
            await namespace.reset_to_original()
            await namespace.apply_patch(artifact.bug_inject_diff)

            # Revert only this file
            await namespace.restore_file(file_path)

            # Run tests without weakening
            results = await self._run_tests(namespace, artifact)

            # Check if any test that was failing now passes
            buggy_results = await self._get_cached_buggy_results()
            file_contributes = any(
                results.get(test) == "passed" and buggy_results.get(test) == "failed"
                for test in results
            )

            if not file_contributes:
                return False  # This file doesn't contribute to bug

        return True  # All files contribute
```

### AWS Infrastructure Components

```yaml
# deploy/cloudformation/ssr-training.yaml
AWSTemplateFormatVersion: '2010-09-09'
Description: 'Project Aura - Layer 7.3 - SSR Training (Self-Play RL Infrastructure)'

Parameters:
  ProjectName:
    Type: String
    Default: aura
  Environment:
    Type: String
    AllowedValues: [dev, qa, prod]
  AlertEmail:
    Type: String
    Description: Email address for budget and operational alerts
  VpcId:
    Type: AWS::EC2::VPC::Id
    Description: VPC ID for SSR training resources
  PrivateSubnetIds:
    Type: List<AWS::EC2::Subnet::Id>
    Description: Private subnet IDs for ECS tasks

Conditions:
  IsProd: !Equals [!Ref Environment, prod]
  IsDev: !Equals [!Ref Environment, dev]

Resources:
  #############################################
  # ECS Cluster for SSR Training
  #############################################
  SSRTrainingCluster:
    Type: AWS::ECS::Cluster
    Properties:
      ClusterName: !Sub '${ProjectName}-ssr-training-${Environment}'
      ClusterSettings:
        - Name: containerInsights
          Value: enabled
      CapacityProviders:
        - FARGATE
        - FARGATE_SPOT
      DefaultCapacityProviderStrategy:
        - CapacityProvider: FARGATE_SPOT
          Weight: 4
        - CapacityProvider: FARGATE
          Weight: 1
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment
        - Key: Layer
          Value: sandbox
        - Key: Purpose
          Value: ssr-training

  #############################################
  # IAM Role for Step Functions
  #############################################
  SSRTrainingRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-ssr-training-role-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: states.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: SSRTrainingPermissions
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: DynamoDBAccess
                Effect: Allow
                Action: [dynamodb:GetItem, dynamodb:PutItem, dynamodb:UpdateItem, dynamodb:Query]
                Resource:
                  - !GetAtt SSRTrainingStateTable.Arn
                  - !Sub '${SSRTrainingStateTable.Arn}/index/*'
              - Sid: S3Access
                Effect: Allow
                Action: [s3:GetObject, s3:PutObject, s3:ListBucket]
                Resource:
                  - !GetAtt SSRTrainingBucket.Arn
                  - !Sub '${SSRTrainingBucket.Arn}/*'
              - Sid: SQSAccess
                Effect: Allow
                Action: [sqs:SendMessage, sqs:ReceiveMessage, sqs:DeleteMessage]
                Resource: !GetAtt SSRTrainingQueue.Arn
              - Sid: ECSTaskExecution
                Effect: Allow
                Action: [ecs:RunTask, ecs:StopTask, ecs:DescribeTasks]
                Resource: '*'
                Condition:
                  ArnEquals:
                    'ecs:cluster': !GetAtt SSRTrainingCluster.Arn
              - Sid: PassRole
                Effect: Allow
                Action: iam:PassRole
                Resource:
                  - !GetAtt SSRTaskExecutionRole.Arn
                  - !GetAtt SSRTaskRole.Arn
              - Sid: LambdaInvoke
                Effect: Allow
                Action: lambda:InvokeFunction
                Resource: !Sub 'arn:${AWS::Partition}:lambda:${AWS::Region}:${AWS::AccountId}:function:${ProjectName}-ssr-*-${Environment}'
              - Sid: CloudWatchMetrics
                Effect: Allow
                Action: cloudwatch:PutMetricData
                Resource: '*'
                Condition:
                  StringEquals:
                    'cloudwatch:namespace': !Sub '${ProjectName}/SSR'
              - Sid: KMSDecrypt
                Effect: Allow
                Action: [kms:Decrypt, kms:GenerateDataKey]
                Resource: !GetAtt SSRTrainingKMSKey.Arn

  #############################################
  # ECS Task Execution Role
  #############################################
  SSRTaskExecutionRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-ssr-task-execution-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      ManagedPolicyArns:
        - !Sub 'arn:${AWS::Partition}:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy'
      Policies:
        - PolicyName: SecretsAccess
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Effect: Allow
                Action: [secretsmanager:GetSecretValue]
                Resource: !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/${Environment}/*'
              - Effect: Allow
                Action: [kms:Decrypt]
                Resource: !GetAtt SSRTrainingKMSKey.Arn

  #############################################
  # ECS Task Role (for running containers)
  #############################################
  SSRTaskRole:
    Type: AWS::IAM::Role
    Properties:
      RoleName: !Sub '${ProjectName}-ssr-task-role-${Environment}'
      AssumeRolePolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Principal:
              Service: ecs-tasks.amazonaws.com
            Action: sts:AssumeRole
      Policies:
        - PolicyName: SSRTaskPermissions
          PolicyDocument:
            Version: '2012-10-17'
            Statement:
              - Sid: S3ArtifactAccess
                Effect: Allow
                Action: [s3:GetObject, s3:PutObject]
                Resource: !Sub '${SSRTrainingBucket.Arn}/*'
              - Sid: BedrockInference
                Effect: Allow
                Action: [bedrock:InvokeModel, bedrock:InvokeModelWithResponseStream]
                Resource: !Sub 'arn:${AWS::Partition}:bedrock:${AWS::Region}::foundation-model/*'
              - Sid: CloudWatchLogs
                Effect: Allow
                Action: [logs:CreateLogStream, logs:PutLogEvents]
                Resource: !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/ecs/${ProjectName}-ssr-*'

  #############################################
  # Bug Injection Task Definition
  #############################################
  BugInjectionTaskDef:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${ProjectName}-ssr-bug-injection-${Environment}'
      Cpu: '4096'
      Memory: '16384'
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      ExecutionRoleArn: !GetAtt SSRTaskExecutionRole.Arn
      TaskRoleArn: !GetAtt SSRTaskRole.Arn
      ContainerDefinitions:
        - Name: bug-injector
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ProjectName}-ssr-injector:latest'
          Essential: true
          Environment:
            - Name: ENVIRONMENT
              Value: !Ref Environment
            - Name: PROJECT_NAME
              Value: !Ref ProjectName
          Secrets:
            - Name: BEDROCK_API_KEY
              ValueFrom: !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/${Environment}/bedrock-api-key'
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref SSRInjectorLogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: injector

  #############################################
  # Bug Solving Task Definition
  #############################################
  BugSolvingTaskDef:
    Type: AWS::ECS::TaskDefinition
    Properties:
      Family: !Sub '${ProjectName}-ssr-bug-solving-${Environment}'
      Cpu: '4096'
      Memory: '16384'
      NetworkMode: awsvpc
      RequiresCompatibilities: [FARGATE]
      ExecutionRoleArn: !GetAtt SSRTaskExecutionRole.Arn
      TaskRoleArn: !GetAtt SSRTaskRole.Arn
      ContainerDefinitions:
        - Name: bug-solver
          Image: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/${ProjectName}-ssr-solver:latest'
          Essential: true
          Environment:
            - Name: ENVIRONMENT
              Value: !Ref Environment
            - Name: PROJECT_NAME
              Value: !Ref ProjectName
          Secrets:
            - Name: BEDROCK_API_KEY
              ValueFrom: !Sub 'arn:${AWS::Partition}:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:${ProjectName}/${Environment}/bedrock-api-key'
          LogConfiguration:
            LogDriver: awslogs
            Options:
              awslogs-group: !Ref SSRSolverLogGroup
              awslogs-region: !Ref AWS::Region
              awslogs-stream-prefix: solver

  #############################################
  # CloudWatch Log Groups
  #############################################
  SSRInjectorLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/ecs/${ProjectName}-ssr-injector-${Environment}'
      RetentionInDays: !If [IsProd, 365, 90]
      KmsKeyId: !GetAtt SSRTrainingKMSKey.Arn

  SSRSolverLogGroup:
    Type: AWS::Logs::LogGroup
    Properties:
      LogGroupName: !Sub '/ecs/${ProjectName}-ssr-solver-${Environment}'
      RetentionInDays: !If [IsProd, 365, 90]
      KmsKeyId: !GetAtt SSRTrainingKMSKey.Arn

  #############################################
  # Security Group for SSR Tasks
  #############################################
  SSRSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupName: !Sub '${ProjectName}-ssr-training-sg-${Environment}'
      GroupDescription: Security group for SSR training tasks
      VpcId: !Ref VpcId
      SecurityGroupEgress:
        - IpProtocol: tcp
          FromPort: 443
          ToPort: 443
          CidrIp: 0.0.0.0/0
          Description: HTTPS for AWS APIs and Bedrock
      Tags:
        - Key: Name
          Value: !Sub '${ProjectName}-ssr-training-sg-${Environment}'
  #############################################
  # S3 Bucket for Training Artifacts
  #############################################
  SSRTrainingBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: !Sub '${ProjectName}-ssr-training-${Environment}'
      BucketEncryption:
        ServerSideEncryptionConfiguration:
          - ServerSideEncryptionByDefault:
              SSEAlgorithm: aws:kms
              KMSMasterKeyID: !Ref SSRTrainingKMSKey
      VersioningConfiguration:
        Status: Enabled
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: true
        IgnorePublicAcls: true
        RestrictPublicBuckets: true
      LifecycleConfiguration:
        Rules:
          - Id: ExpireOldArtifacts
            Status: Enabled
            ExpirationInDays: 90
            Prefix: artifacts/
      IntelligentTieringConfigurations:
        - Id: TrainingArtifacts
          Status: Enabled
          Tierings:
            - AccessTier: ARCHIVE_ACCESS
              Days: 90
            - AccessTier: DEEP_ARCHIVE_ACCESS
              Days: 180
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  SSRTrainingBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref SSRTrainingBucket
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Sid: EnforceTLS
            Effect: Deny
            Principal: '*'
            Action: 's3:*'
            Resource:
              - !GetAtt SSRTrainingBucket.Arn
              - !Sub '${SSRTrainingBucket.Arn}/*'
            Condition:
              Bool:
                'aws:SecureTransport': 'false'
          - Sid: DenyInsecureTransport
            Effect: Deny
            Principal: '*'
            Action: 's3:*'
            Resource:
              - !GetAtt SSRTrainingBucket.Arn
              - !Sub '${SSRTrainingBucket.Arn}/*'
            Condition:
              NumericLessThan:
                's3:TlsVersion': '1.2'

  #############################################
  # DynamoDB Table for Training State
  #############################################
  SSRTrainingStateTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: !Sub '${ProjectName}-ssr-training-state-${Environment}'
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: repository_id
          AttributeType: S
        - AttributeName: artifact_id
          AttributeType: S
        - AttributeName: created_at
          AttributeType: S
      KeySchema:
        - AttributeName: repository_id
          KeyType: HASH
        - AttributeName: artifact_id
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: CreatedAtIndex
          KeySchema:
            - AttributeName: repository_id
              KeyType: HASH
            - AttributeName: created_at
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      PointInTimeRecoverySpecification:
        PointInTimeRecoveryEnabled: true

  # SQS queue for training job orchestration
  SSRTrainingQueue:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-ssr-training-queue-${Environment}'
      VisibilityTimeoutSeconds: 900  # 15 minutes per training iteration
      MessageRetentionPeriod: 1209600  # 14 days
      KmsMasterKeyId: !Ref SSRTrainingKMSKey
      RedrivePolicy:
        deadLetterTargetArn: !GetAtt SSRTrainingDLQ.Arn
        maxReceiveCount: 3

  SSRTrainingDLQ:
    Type: AWS::SQS::Queue
    Properties:
      QueueName: !Sub '${ProjectName}-ssr-training-dlq-${Environment}'
      MessageRetentionPeriod: 1209600
      KmsMasterKeyId: !Ref SSRTrainingKMSKey

  # Step Functions for training orchestration
  SSRTrainingStateMachine:
    Type: AWS::StepFunctions::StateMachine
    Properties:
      StateMachineName: !Sub '${ProjectName}-ssr-training-${Environment}'
      RoleArn: !GetAtt SSRTrainingRole.Arn
      Definition:
        Comment: SSR Self-Play Training Orchestration
        StartAt: SelectRepository
        States:
          SelectRepository:
            Type: Task
            Resource: !GetAtt SelectRepositoryLambda.Arn
            Next: BugInjection
          BugInjection:
            Type: Task
            Resource: !Sub 'arn:${AWS::Partition}:states:::ecs:runTask.sync'
            Parameters:
              LaunchType: FARGATE
              Cluster: !Ref SSRTrainingCluster
              TaskDefinition: !Ref BugInjectionTaskDef
            Next: ValidateArtifact
          ValidateArtifact:
            Type: Task
            Resource: !GetAtt ValidateArtifactLambda.Arn
            Next: ValidationChoice
          ValidationChoice:
            Type: Choice
            Choices:
              - Variable: $.validation.is_valid
                BooleanEquals: true
                Next: BugSolving
            Default: RecordInvalidBug
          BugSolving:
            Type: Map
            ItemsPath: $.solve_attempts
            MaxConcurrency: 4
            Iterator:
              StartAt: AttemptFix
              States:
                AttemptFix:
                  Type: Task
                  Resource: !Sub 'arn:${AWS::Partition}:states:::ecs:runTask.sync'
                  Parameters:
                    LaunchType: FARGATE
                    Cluster: !Ref SSRTrainingCluster
                    TaskDefinition: !Ref BugSolvingTaskDef
                  End: true
            Next: ComputeRewards
          ComputeRewards:
            Type: Task
            Resource: !GetAtt ComputeRewardsLambda.Arn
            Next: UpdatePolicy
          UpdatePolicy:
            Type: Task
            Resource: !GetAtt UpdatePolicyLambda.Arn
            Next: GenerateHigherOrderBugs
          GenerateHigherOrderBugs:
            Type: Task
            Resource: !GetAtt GenerateHigherOrderLambda.Arn
            End: true
          RecordInvalidBug:
            Type: Task
            Resource: !GetAtt RecordInvalidBugLambda.Arn
            End: true

  #############################################
  # KMS Key for Training Data Encryption
  #############################################
  SSRTrainingKMSKey:
    Type: AWS::KMS::Key
    Properties:
      Description: KMS key for SSR training data encryption
      EnableKeyRotation: true
      KeyPolicy:
        Version: '2012-10-17'
        Statement:
          - Sid: Enable IAM Policies
            Effect: Allow
            Principal:
              AWS: !Sub 'arn:${AWS::Partition}:iam::${AWS::AccountId}:root'
            Action: 'kms:*'
            Resource: '*'
      Tags:
        - Key: Project
          Value: !Ref ProjectName
        - Key: Environment
          Value: !Ref Environment

  SSRTrainingKMSKeyAlias:
    Type: AWS::KMS::Alias
    Properties:
      AliasName: !Sub 'alias/${ProjectName}-ssr-training-${Environment}'
      TargetKeyId: !Ref SSRTrainingKMSKey

  #############################################
  # Budget and Cost Controls
  #############################################
  SSRTrainingBudget:
    Type: AWS::Budgets::Budget
    Properties:
      Budget:
        BudgetName: !Sub '${ProjectName}-ssr-training-${Environment}'
        BudgetLimit:
          Amount: !If [IsProd, 10000, 1000]
          Unit: USD
        TimeUnit: MONTHLY
        BudgetType: COST
        CostFilters:
          TagKeyValue:
            - !Sub 'user:Project$${ProjectName}'
            - !Sub 'user:Purpose$ssr-training'
      NotificationsWithSubscribers:
        - Notification:
            NotificationType: ACTUAL
            ComparisonOperator: GREATER_THAN
            Threshold: 50
          Subscribers:
            - SubscriptionType: EMAIL
              Address: !Ref AlertEmail
        - Notification:
            NotificationType: ACTUAL
            ComparisonOperator: GREATER_THAN
            Threshold: 80
          Subscribers:
            - SubscriptionType: EMAIL
              Address: !Ref AlertEmail
        - Notification:
            NotificationType: FORECASTED
            ComparisonOperator: GREATER_THAN
            Threshold: 100
          Subscribers:
            - SubscriptionType: EMAIL
              Address: !Ref AlertEmail

  SSRCostAlarm:
    Type: AWS::CloudWatch::Alarm
    Properties:
      AlarmName: !Sub '${ProjectName}-ssr-training-cost-${Environment}'
      AlarmDescription: SSR training costs exceeding threshold - auto-pause may be triggered
      MetricName: EstimatedCharges
      Namespace: AWS/Billing
      Dimensions:
        - Name: ServiceName
          Value: AmazonECS
      Statistic: Maximum
      Period: 21600  # 6 hours
      EvaluationPeriods: 1
      Threshold: !If [IsProd, 5000, 500]
      ComparisonOperator: GreaterThanThreshold
      AlarmActions:
        - !Ref SSRCostAlertTopic

  SSRCostAlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: !Sub '${ProjectName}-ssr-cost-alerts-${Environment}'
      KmsMasterKeyId: !Ref SSRTrainingKMSKey

  SSRCostAlertSubscription:
    Type: AWS::SNS::Subscription
    Properties:
      TopicArn: !Ref SSRCostAlertTopic
      Protocol: email
      Endpoint: !Ref AlertEmail

  #############################################
  # CloudWatch Metrics and Dashboard
  #############################################
  SSRTrainingDashboard:
    Type: AWS::CloudWatch::Dashboard
    Properties:
      DashboardName: !Sub '${ProjectName}-ssr-training-${Environment}'
      DashboardBody: !Sub |
        {
          "widgets": [
            {
              "type": "metric",
              "properties": {
                "title": "Training Progress",
                "metrics": [
                  ["${ProjectName}/SSR", "ValidBugs", "Environment", "${Environment}"],
                  ["${ProjectName}/SSR", "InvalidBugs", "Environment", "${Environment}"],
                  ["${ProjectName}/SSR", "HigherOrderBugs", "Environment", "${Environment}"]
                ],
                "period": 300,
                "stat": "Sum"
              }
            },
            {
              "type": "metric",
              "properties": {
                "title": "Solve Rate",
                "metrics": [
                  ["${ProjectName}/SSR", "SolveRate", "Environment", "${Environment}"]
                ],
                "period": 300,
                "stat": "Average"
              }
            },
            {
              "type": "metric",
              "properties": {
                "title": "Reward Distribution",
                "metrics": [
                  ["${ProjectName}/SSR", "InjectorReward", "Environment", "${Environment}"],
                  ["${ProjectName}/SSR", "SolverReward", "Environment", "${Environment}"]
                ],
                "period": 300,
                "stat": "Average"
              }
            }
          ]
        }

Outputs:
  TrainingBucketName:
    Value: !Ref SSRTrainingBucket
  TrainingStateTableName:
    Value: !Ref SSRTrainingStateTable
  TrainingStateMachineArn:
    Value: !Ref SSRTrainingStateMachine
```

---

## GovCloud Compatibility

All AWS services used in this ADR are available in AWS GovCloud (US) regions:

| Service | GovCloud Availability | Region |
|---------|----------------------|--------|
| ECS Fargate | ✅ Available | us-gov-west-1, us-gov-east-1 |
| Step Functions | ✅ Available | us-gov-west-1, us-gov-east-1 |
| DynamoDB | ✅ Available | us-gov-west-1, us-gov-east-1 |
| S3 | ✅ Available | us-gov-west-1, us-gov-east-1 |
| SQS | ✅ Available | us-gov-west-1, us-gov-east-1 |
| CloudWatch | ✅ Available | us-gov-west-1, us-gov-east-1 |
| KMS | ✅ Available | us-gov-west-1, us-gov-east-1 |
| Bedrock | ✅ Available | us-gov-west-1 only |
| Lambda | ✅ Available | us-gov-west-1, us-gov-east-1 |

**Notes:**
- All ARN patterns use `${AWS::Partition}` for GovCloud compatibility
- Bedrock Claude 3.5 Sonnet is available in GovCloud (us-gov-west-1)
- Bedrock custom model training is available in GovCloud with potential pricing differences
- VPC Endpoints should be configured for all services in production GovCloud deployments

---

## Customer Consent and Data Governance

### GDPR/CCPA Compliance Requirements

Customer consent is **mandatory** before any repository can be used for SSR training. This section documents the consent requirements aligned with GDPR Article 7 and CCPA 1798.100.

```python
# src/services/ssr/consent_policy.py
from dataclasses import dataclass
from enum import Enum
from typing import List, Set

class ConsentType(Enum):
    """Required consent types for SSR training participation."""
    SSR_TRAINING_PARTICIPATION = "ssr_training"      # Use repo for training
    SYNTHETIC_BUG_GENERATION = "synthetic_bugs"      # Create bugs from code
    MODEL_WEIGHT_UPDATES = "model_updates"           # Update shared policy
    DATA_RETENTION_90_DAYS = "retention_90d"         # Artifact retention period

@dataclass
class CustomerConsentPolicy:
    """
    Customer consent requirements for SSR training.

    Compliance: GDPR Article 7, CCPA 1798.100
    """

    # Minimum consent requirements - ALL must be granted
    REQUIRED_CONSENTS: Set[ConsentType] = frozenset({
        ConsentType.SSR_TRAINING_PARTICIPATION,
        ConsentType.SYNTHETIC_BUG_GENERATION,
        ConsentType.MODEL_WEIGHT_UPDATES,
        ConsentType.DATA_RETENTION_90_DAYS,
    })

    # Customer-specific isolation requirements
    ISOLATION_REQUIREMENTS: List[str] = [
        "No cross-customer training data mixing",
        "Customer-specific model checkpoints available on request",
        "Full audit trail of training data provenance",
        "Right to withdrawal triggers data purge within 30 days",
    ]

    # Data retention policies
    ARTIFACT_RETENTION_DAYS: int = 90
    TRAINING_LOG_RETENTION_DAYS: int = 365

    def validate_consent(
        self,
        customer_id: str,
        granted_consents: Set[ConsentType]
    ) -> bool:
        """Verify all required consents are granted."""
        return self.REQUIRED_CONSENTS.issubset(granted_consents)

@dataclass
class ConsentRecord:
    """Immutable record of customer consent."""
    customer_id: str
    consent_type: ConsentType
    granted_at: str  # ISO 8601 timestamp
    granted_by: str  # User ID who granted consent
    ip_address: str  # For audit trail
    consent_version: str  # Version of consent terms accepted

    # Withdrawal tracking
    withdrawn_at: str | None = None
    withdrawal_reason: str | None = None
```

### Data Governance Controls

| Control | Implementation | Audit Frequency |
|---------|----------------|-----------------|
| **Consent Verification** | Pre-flight check before any training job | Every training job |
| **Data Provenance** | Full lineage tracking from repo → artifact → model | Continuous |
| **Cross-Customer Isolation** | Separate S3 prefixes, DynamoDB partition keys | Quarterly audit |
| **Retention Enforcement** | S3 lifecycle policies, automated purge jobs | Weekly verification |
| **Withdrawal Processing** | 30-day SLA for complete data removal | On-demand |
| **Audit Logging** | CloudTrail + application logs to immutable storage | 365-day retention |

### CMMC Level 3 Control Mapping

| CMMC Practice | SSR Implementation | Verification Method |
|---------------|-------------------|---------------------|
| AC.L2-3.1.1 (Authorized Access) | IAM least privilege, consent-gated access | IAM policy review |
| AU.L2-3.3.1 (Event Logging) | CloudWatch + CloudTrail for all training ops | Log analysis |
| SC.L2-3.13.1 (Boundary Protection) | VPC isolation, security groups, no public IPs | Network scan |
| SC.L2-3.13.11 (CUI Encryption) | KMS encryption at rest, TLS 1.2+ in transit | Encryption audit |
| SI.L2-3.14.6 (Monitor Communications) | VPC Flow Logs, network traffic analysis | Weekly review |

---

## Implementation Phases

### Phase 1: Bug Artifact Infrastructure (Weeks 1-4)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 1.1 | Implement BugArtifact dataclass | `src/services/ssr/bug_artifact.py` |
| 1.2 | Create consistency validation pipeline | `src/services/ssr/validation_pipeline.py` |
| 1.3 | Build test parser framework | `src/services/ssr/test_parser.py` |
| 1.4 | Integrate with sandbox service | Updated `sandbox_network_service.py` |
| 1.5 | Add DynamoDB table for artifacts | `ssr-training.yaml` |
| 1.6 | Unit tests for artifact handling | `tests/test_ssr_artifact.py` |
| 1.7 | Security hardening and IAM review | Security team sign-off |

**Success Criteria:**
- 100% of artifact validation stages implemented (7/7 stages)
- Integration with existing EKS sandbox namespaces verified
- 95%+ test coverage on validation logic (measured by pytest-cov)
- Security review completed with no HIGH findings

### Phase 2: Self-Play Training Loop (Weeks 5-9)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 2.1 | Implement bug injection agent | `src/services/ssr/bug_injector.py` |
| 2.2 | Implement bug solving agent | `src/services/ssr/bug_solver.py` |
| 2.3 | Create self-play orchestrator | `src/services/ssr/orchestrator.py` |
| 2.4 | Build reward computation module | `src/services/ssr/rewards.py` |
| 2.5 | Implement Step Functions workflow | `deploy/cloudformation/ssr-training.yaml` |
| 2.6 | Add training queue and DLQ | SQS resources |
| 2.7 | Implement Lambda functions | 6 Lambda functions for workflow |
| 2.8 | Observability and X-Ray tracing | Distributed tracing enabled |

**Success Criteria:**
- End-to-end training loop executes successfully (≥10 iterations)
- Reward computation matches paper formula within 0.01 tolerance
- Sandbox isolation verified (no network leakage in security scan)
- All 6 Lambda functions deployed with <500ms p99 latency

### Phase 3: History-Aware Injection + GraphRAG (Weeks 10-12)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 3.1 | Implement history-aware injection | `src/services/ssr/history_injector.py` |
| 3.2 | Integrate with Neptune GraphRAG | GraphRAG queries for candidates |
| 3.3 | Add git history analysis | `src/services/ssr/git_analyzer.py` |
| 3.4 | Build reversion candidate ranking | Complexity × coverage scoring |
| 3.5 | Integration tests with real repos | `tests/integration/test_ssr_injection.py` |

**Success Criteria:**
- GraphRAG-enhanced candidate selection operational (≥50 queries/min)
- History-aware injection produces ≥3 unique bug types per repository
- Reversion quality score ≥0.7 on test repositories
- Neptune read replica configured for SSR queries

### Phase 4: Higher-Order Bugs + Memory (Weeks 13-16)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 4.1 | Implement higher-order bug generation | Failed attempts → new artifacts |
| 4.2 | Integrate with Titan Neural Memory | Pattern storage and retrieval |
| 4.3 | Build deduplication logic | Prevent overlapping bugs |
| 4.4 | Add curriculum learning metrics | Difficulty progression tracking |
| 4.5 | Memory consolidation for patterns | Cross-iteration learning |

**Success Criteria:**
- Higher-order bugs comprise ≥20% of training set after 100 iterations
- Memory retrieval latency <100ms p95
- Curriculum difficulty score increases monotonically over training
- Deduplication reduces artifact overlap by ≥80%

### Phase 5: Production Integration (Weeks 17-20)

| Task | Description | Deliverable |
|------|-------------|-------------|
| 5.1 | Customer repository opt-in system | UI + API for consent |
| 5.2 | HITL approval for model deployment | Approval workflow integration |
| 5.3 | A/B testing framework | Compare SSR-trained vs baseline |
| 5.4 | Production monitoring dashboard | CloudWatch metrics and alarms |
| 5.5 | Operational runbook | `docs/operations/SSR_RUNBOOK.md` |
| 5.6 | Customer consent UX design | UI mockups and flow |

**Success Criteria:**
- Customer consent mechanism operational with ≥30% opt-in rate
- HITL approval latency <24 hours for model deployments
- A/B test shows ≥10% improvement in patch accuracy (statistically significant p<0.05)
- Operational runbook covers: pause/resume, failure investigation, rollback, cost anomaly
- Zero security incidents during pilot phase

### Implementation Timeline Summary

| Phase | Duration | Weeks | Key Milestone |
|-------|----------|-------|---------------|
| Phase 1 | 4 weeks | 1-4 | Bug artifact infrastructure complete |
| Phase 2 | 5 weeks | 5-9 | Self-play training loop operational |
| Phase 3 | 3 weeks | 10-12 | GraphRAG integration complete |
| Phase 4 | 4 weeks | 13-16 | Higher-order bugs + memory live |
| Phase 5 | 4 weeks | 17-20 | Production deployment ready |
| **Total** | **20 weeks** | | **Full SSR capability** |

**Buffer Rationale:** 25% buffer added to original 16-week estimate based on architectural review recommendations for security hardening, IAM complexity, and customer consent UX design.

---

## Security Considerations

### Sandbox Isolation Requirements

| Control | Implementation | Verification |
|---------|----------------|--------------|
| Network Isolation | Dedicated VPC subnets for SSR | NetworkPolicy enforcement |
| Compute Isolation | Fargate tasks with no shared resources | Task-level isolation |
| Storage Isolation | Separate S3 buckets with bucket policies | IAM boundary enforcement |
| Secrets Isolation | No customer secrets in training artifacts | Pre-scan filter integration |
| Code Isolation | Read-only access to repositories | Git clone without push access |

### Data Protection

```python
# src/services/ssr/security.py

class SSRSecurityGuard:
    """Security controls for SSR training"""

    async def pre_training_scan(
        self,
        repository: Repository
    ) -> SecurityScanResult:
        """
        Scan repository before using for training.

        1. Check for secrets using SecretsPrescanFilter (ADR-048)
        2. Verify no PII in test data
        3. Confirm customer consent
        """
        # Use existing secrets filter
        secrets_result = await self.secrets_filter.scan_repository(repository)
        if secrets_result.has_secrets:
            raise SecurityViolation(
                f"Repository contains secrets: {secrets_result.findings}"
            )

        # Check consent
        consent = await self.consent_service.check_consent(
            customer_id=repository.customer_id,
            consent_type=ConsentType.SSR_TRAINING
        )
        if not consent.granted:
            raise ConsentNotGranted(
                f"Customer has not consented to SSR training"
            )

        return SecurityScanResult(approved=True)
```

### Compliance Alignment

| Compliance Framework | SSR Impact | Mitigation |
|---------------------|------------|------------|
| **CMMC Level 3** | Training data handling | Encryption at rest/transit, audit logs |
| **SOC 2** | Data isolation | Customer consent, access controls |
| **GDPR** | Data processing | Opt-in only, no PII in artifacts |
| **HIPAA** | PHI protection | Healthcare repos excluded by default |

---

## Cost Estimation

### Compute Costs (per month, dev environment)

| Resource | Specification | Estimated Cost |
|----------|---------------|----------------|
| ECS Fargate (Bug Injection) | 4 vCPU, 8GB, 2hr/day | $150 |
| ECS Fargate (Bug Solving) | 4 vCPU, 8GB, 8hr/day | $600 |
| Step Functions | ~10K state transitions | $25 |
| S3 Storage | 100GB artifacts | $25 |
| DynamoDB | On-demand, ~1M requests | $50 |
| CloudWatch | Metrics + logs | $50 |
| **Total (Dev)** | | **~$900/month** |

### Production Scale Estimate

| Scale | Training Jobs/Day | Estimated Cost |
|-------|-------------------|----------------|
| Pilot | 10 | $2,500/month |
| Standard | 100 | $8,000/month |
| Enterprise | 1,000 | $25,000/month |

### Bedrock/SageMaker Costs (Model Training)

| Option | Approach | Estimated Cost |
|--------|----------|----------------|
| Bedrock Custom Models | Fine-tune Claude | $15-30K one-time |
| SageMaker Training | Distributed RL | $5-10K per training run |
| Inference | Production serving | $500-2,000/month |

---

## Alternatives Considered

### Alternative 1: Static Bug Dataset (SWE-smith approach)

**Description:** Use SWE-smith or similar to generate static bug dataset, then train with standard supervised learning.

**Pros:**
- Simpler implementation
- Lower compute requirements
- No self-play complexity

**Cons:**
- No curriculum learning (static difficulty)
- No adaptation to model improvements
- Limited diversity compared to self-play

**Decision:** Rejected - SSR's self-play provides superior learning signal per paper results.

### Alternative 2: Human-Curated Training Data Only

**Description:** Continue using only human-labeled vulnerability data (CVEs, security advisories).

**Pros:**
- Known quality
- Existing pipeline
- No new infrastructure

**Cons:**
- Expensive to scale
- Limited coverage
- Slow to update

**Decision:** Rejected - SSR augments (not replaces) human data with unlimited synthetic training.

### Alternative 3: External Training Service

**Description:** Use third-party ML training service (e.g., Anyscale, Weights & Biases).

**Pros:**
- Managed infrastructure
- Faster time-to-value
- Expert support

**Cons:**
- Data leaves Aura environment
- Vendor dependency
- Higher long-term cost
- Compliance concerns

**Decision:** Rejected - Customer data must remain within Aura's security boundary.

---

## Success Metrics

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| Patch Generation Accuracy | Establish in Week 1 | ≥+10% (statistically significant) | A/B test on held-out bugs, 1000+ samples |
| False Positive Rate | Establish in Week 1 | ≤-5% reduction | Production alert analysis, weekly |
| Training Data Volume | Human-curated only | ≥10x synthetic bugs | Artifact count in DynamoDB |
| Agent Improvement Rate | Static (0%) | ≥2% monthly improvement | Monthly evaluation on SWE-bench subset |
| Customer Opt-in Rate | 0% | ≥30% | Consent tracking dashboard |
| Bug Diversity Score | N/A | ≥0.8 Shannon entropy | Artifact type distribution analysis |
| Solve Rate Stability | N/A | 0.3-0.7 range | Rolling 7-day average |
| Training Cost Efficiency | N/A | ≤$25/valid bug | CloudWatch cost metrics |

### Evaluation Methodology

1. **Baseline Establishment (Week 1):**
   - Run current agents on 100 held-out vulnerabilities
   - Record patch accuracy, false positive rate, latency
   - This becomes the baseline for all A/B comparisons

2. **Continuous Evaluation:**
   - Weekly A/B tests on 50 new vulnerabilities
   - Statistical significance testing (p<0.05) before declaring improvement
   - Shadow deployment of SSR-trained model alongside production

3. **Rollback Criteria:**
   - If patch accuracy drops >5% for 2 consecutive weeks
   - If false positive rate increases >10%
   - If any security incident occurs during training

---

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Reward hacking | Medium | High | Public/private test splits, human review |
| Training instability | Medium | Medium | Proven hyperparameters, gradual scaling |
| Customer data exposure | Low | Critical | Strict sandbox isolation, consent system |
| Compute cost overrun | Medium | Medium | Budget alerts, auto-scaling limits |
| Model quality regression | Low | High | HITL approval before deployment |

---

## References

1. Wei et al. "Toward Training Superintelligent Software Agents through Self-Play SWE-RL" (arXiv:2512.18552, December 2025)
2. ADR-024: Titan Neural Memory Architecture
3. ADR-029: Agent Optimization Strategies
4. ADR-034: Context Engineering Framework
5. ADR-039: Self-Service Test Environments
6. ADR-042: Real-Time Agent Intervention
7. ADR-048: Developer Tools and Data Platform Integrations

---

## Appendix A: SSR Paper Key Equations

### Bug-Injection Reward (Equation 1)

```
r_inject = {
    -1.0                  if consistency validation fails
    -α                    if s = 0 or s = 1
    1 - (1 + α)s          if 0 < s < 1 (ideal difficulty)
}

where:
- s = solve rate (fraction of successful solver attempts)
- α = 0.8 (penalty magnitude for degenerate solve rates)
```

### Bug-Solving Reward (Equation 2)

```
r_solve = {
    +1    if all tests pass
    -1    otherwise
}
```

### Expected Reward Analysis

For valid bugs with ideal difficulty (0 < s < 1):
- Solver expected reward: E[r_solve] = 2s - 1
- Injector expected reward: r_inject = 1 - (1 + α)s

This creates opposing incentives that push bugs toward the frontier of solver capability.

---

## Appendix B: Prompt Templates

### Bug-Injection Prompt (Removal-Oriented)

See full prompt in SSR paper Appendix A.1. Key elements:
- Explore codebase and test suite
- Identify test files with ≥ min_passing_tests coverage
- Remove code hunks/files (≥ min_changed_files)
- Create test parser and weakening patch
- Submit 5-file artifact

### Bug-Solving Prompt

```
Solve the following issue by implementing the necessary code changes:

<issue_description>
I am improving the test suite of the project with the following changes,
but the current code does not pass the tests. Please fix the code.

```diff
{oracle_test_patch}
```
</issue_description>

Submit a patch file that resolves the issue.
```

---

## Architectural Review

### Review Summary (2026-01-01)

**Reviewer:** Architecture Review
**Verdict:** APPROVE WITH CONDITIONS

The architectural review identified the following areas that have been addressed in this ADR revision:

| Finding | Severity | Status | Resolution |
|---------|----------|--------|------------|
| Missing ECS Cluster definition | Critical | ✅ Fixed | Added `SSRTrainingCluster` with Fargate Spot |
| Missing IAM Role definitions | Critical | ✅ Fixed | Added `SSRTrainingRole`, `SSRTaskExecutionRole`, `SSRTaskRole` |
| Missing Task Definitions | High | ✅ Fixed | Added `BugInjectionTaskDef`, `BugSolvingTaskDef` |
| No GovCloud compatibility statement | Medium | ✅ Fixed | Added GovCloud Compatibility section |
| Customer consent GDPR/CCPA gaps | High | ✅ Fixed | Added Customer Consent and Data Governance section |
| Missing S3 bucket policy | Medium | ✅ Fixed | Added TLS enforcement bucket policy |
| Missing budget controls | Medium | ✅ Fixed | Added `SSRTrainingBudget`, cost alarms, SNS alerts |
| Timeline too aggressive | Medium | ✅ Fixed | Extended from 16 to 20 weeks (+25% buffer) |
| Vague success criteria | Medium | ✅ Fixed | Added quantitative metrics with measurement methods |
| Missing operational runbook | Medium | ✅ Fixed | Added to Phase 5 deliverables |

### Remaining Recommendations (Future Phases)

The following recommendations are noted for future enhancement:

1. **Federated Learning (Future):** Consider federated learning approaches for IP-sensitive customers
2. **Enhanced Container Isolation (Future):** Evaluate gVisor/Firecracker for additional sandbox hardening
3. **Training Data Anomaly Detection (Future):** Add ML-based detection for potentially malicious training patterns

---

## Decision Outcome

**DEPLOYED** - Infrastructure deployed and validated January 2, 2026.

**Approval Conditions Met:**
- ✅ Complete CloudFormation template with all resources defined
- ✅ GovCloud compatibility confirmed for all services
- ✅ Customer consent requirements documented (GDPR/CCPA)
- ✅ IAM roles defined with least-privilege policies
- ✅ Cost controls implemented (budgets, alerts, auto-pause triggers)
- ✅ Timeline adjusted to 20 weeks with 25% buffer

**Deployment Status (Jan 2, 2026):**
- ✅ `codebuild-ssr.yaml` deployed - SSR CodeBuild project operational
- ✅ `ssr-training.yaml` (Layer 7.2) deployed - S3 bucket, DynamoDB table, KMS key
- ✅ `ssr-training-pipeline.yaml` (Layer 7.3) deployed - ECS Fargate Spot, ECR repos, Step Functions, SNS
- ✅ Integration tests passing (16/16): Artifact storage (8) + Validation pipeline (8)
- ✅ Code fixes applied: KMS encryption for S3, DynamoDB Float-to-Decimal conversion

**Milestones Completed:**
1. ~~Architecture Review to review infrastructure proposal~~ ✅ Complete
2. ~~AWS Infrastructure deployment~~ ✅ Complete (Jan 2, 2026)
3. ~~Integration test validation~~ ✅ Complete (16/16 tests passing)

**Next Steps:**
1. Security team to review sandbox isolation controls (Phase 1, Week 4)
2. Product team to design customer opt-in UX (Phase 5, Week 17)
3. Engineering to continue Phase 2-5 implementation
