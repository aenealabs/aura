# Sandbox Security Model

**Version:** 1.1
**Last Updated:** 2026-08-28

---

## Overview

The Sandbox Security Model is the validation layer that ensures every AI-generated patch is tested before reaching human reviewers or production systems. Project Aura provisions ephemeral Fargate environments, constrained by a restrictive security group and a least-privilege task role, where patches undergo syntax validation, functional verification, security scanning, and performance benchmarking.

This document explains how sandbox environments work, which isolation controls are actually enforced, the validation categories that every patch must pass, and the resource controls that prevent runaway processes.

---

## Why Sandbox Testing Matters

AI-generated code, like human-written code, can contain bugs. The sandbox layer provides a safety net that catches problems before they reach production.

### Without Sandbox Validation

```
1. Coder Agent generates patch
2. Human reviewer approves (based on code review alone)
3. Patch deployed to production
4. Runtime error discovered in production
5. Rollback required, incident created
```

### With Sandbox Validation

```
1. Coder Agent generates patch
2. Sandbox automatically provisions isolated environment
3. All validation categories executed (syntax, tests, security, performance)
4. Validation FAILS: "Unit test test_auth_flow.py failed"
5. Patch rejected automatically, never reaches human reviewer
6. Coder Agent notified, generates improved patch
```

The sandbox layer filters out problematic patches before they consume human attention or risk production stability.

### What Validation Covers

Sandbox validation runs these checks before a patch reaches human review:

| Issue Type | How it is detected |
|------------|--------------------|
| Syntax errors | Parse failure |
| Unit test failures | Repository test suite exit status |
| Security regressions | Scanner re-run against the patched tree |
| Performance regressions | Benchmark comparison against the pre-patch baseline |
| Integration failures | Integration suite exit status |

No catch-rate or production-success figures are published here. Aura has no
customer deployments, so any such rate would be unmeasured.

---

## Sandbox Architecture

Each sandbox is an ephemeral Fargate task that runs patched code under a
dedicated task role and a dedicated security group, separated from production
data by IAM allow-list and by the environment's AWS account boundary.

> **Scope note (2026-08-28).** Sandbox tasks run in the platform VPC's private
> subnets, not in a dedicated sandbox VPC. There is no separate sandbox VPC and
> no `10.200.0.0/16` CIDR: `deploy/cloudformation/sandbox.yaml` takes `VpcId`
> and `PrivateSubnetIds` as parameters imported from the networking stack, and
> `deploy/cloudformation/networking.yaml` creates exactly three public and three
> private subnets in one VPC. Earlier revisions of this page described a
> separate sandbox VPC; that was never deployed. The boundary Aura actually
> enforces is described below and in `ENFORCED_ISOLATION_LEVELS`
> (`src/services/sandbox_network_service.py:79`).

### Environment Topology

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PLATFORM VPC (per environment/account)               │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐          │
│  │  Application    │  │  Neptune        │  │  OpenSearch     │          │
│  │  Services       │  │  (Graph DB)     │  │  (Vector DB)    │          │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘          │
│         (private subnets, own security groups + IAM roles)              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │             Sandbox Fargate Task (same private subnets)           │  │
│  │             sandbox-2026-01-19-abc123                             │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                │  │
│  │  │  Patched    │  │  Mock       │  │  Test       │                │  │
│  │  │  Code       │  │  Services   │  │  Data       │                │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                │  │
│  │                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────┐  │  │
│  │  │  Fargate Task (ephemeral, auto-destroyed)                   │  │  │
│  │  │  - CPU: 0.5 vCPU                                            │  │  │
│  │  │  - Memory: 1 GB                                             │  │  │
│  │  │  - Timeout: 30 minutes max                                  │  │  │
│  │  │  - assignPublicIp: DISABLED                                 │  │  │
│  │  └─────────────────────────────────────────────────────────────┘  │  │
│  │                                                                   │  │
│  │  Security group: no inbound rules at all                          │  │
│  │  Egress: UDP 53 (DNS) + TCP 443 only                              │  │
│  │  Task role: allow-list only (2 DynamoDB tables, 1 log group,      │  │
│  │             1 S3 artifact prefix). No Neptune, no OpenSearch.      │  │
│  └───────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

  Separation from production is by AWS ACCOUNT (dev and qa occupy distinct
  accounts per deploy/config/account-mapping.env; PROD_ACCOUNT_ID is still
  PENDING) plus IAM allow-list and security group, NOT by a VPC boundary.
```

### Component Description

| Component | Purpose | Technology |
|-----------|---------|------------|
| **Sandbox Orchestrator** | Provisions and manages sandbox lifecycle | Python, AWS Step Functions |
| **ECS Fargate Task** | Runs patched code in isolation | AWS ECS, Fargate Spot |
| **Mock Services** | Simulates external dependencies | LocalStack, custom mocks |
| **Test Data Store** | Provides synthetic test data | In-memory, no production data |
| **CloudWatch Logs** | Captures test output and metrics | Sandbox-specific log groups |

---

## Network Isolation

The sandbox network model constrains what a sandbox task can reach. It is a
security-group and IAM boundary, not a network-partition boundary.

### Isolation Levels: What Is Enforced

`NetworkIsolationLevel` declares four levels. `ENFORCED_ISOLATION_LEVELS`
(`src/services/sandbox_network_service.py:79`) is the single source of truth for
which of them the provisioning path actually implements.

| Level | Enforced | Behaviour |
|-------|----------|-----------|
| `none` | Yes | No isolation (host network) |
| `container` | Yes | Task in private subnets, sandbox security group, `assignPublicIp: DISABLED`. **Default and strongest enforced level.** |
| `vpc` | **No** | Declared but not implemented. Requesting it raises `UnsupportedIsolationLevelError`. |
| `full` | **No** | Declared but not implemented. Requesting it raises `UnsupportedIsolationLevelError`. |

`vpc` and `full` were previously accepted and silently served container-level
networking with a success response, because the task `networkConfiguration`
block was byte-for-byte identical across all three levels. They are now refused
before any AWS call rather than misrepresenting the boundary. Implementing them
requires per-level subnets and security groups in CloudFormation, selected by
`_get_sandbox_subnets`; that infrastructure work has not been done.

### Enforced Controls

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SANDBOX NETWORK MODEL (as deployed)                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  LAYER 1: Security Group Rules                                          │
│  ─────────────────────────────────────────────────────────────────────  │
│  - No inbound rules at all (nothing may initiate a connection in)       │
│  - Egress restricted to UDP 53 (DNS) and TCP 443                        │
│  - No public IP: assignPublicIp DISABLED on every task                  │
│  - Source: deploy/cloudformation/sandbox.yaml SandboxSecurityGroup      │
│                                                                         │
│  LAYER 2: IAM Task Role (allow-list, not explicit deny)                 │
│  ─────────────────────────────────────────────────────────────────────  │
│  - SandboxTaskRole grants ONLY: GetItem/PutItem/UpdateItem on the two   │
│    sandbox DynamoDB tables, CreateLogStream/PutLogEvents on the         │
│    sandbox log group, and GetObject on the sandbox artifacts prefix     │
│  - Neptune, OpenSearch and all other data stores are absent from the    │
│    policy, so access is denied by omission                              │
│  - No cross-account role assumption is granted                          │
│                                                                         │
│  LAYER 3: Account Boundary                                              │
│  ─────────────────────────────────────────────────────────────────────  │
│  - dev and qa are separate AWS accounts                                 │
│  - This, not a VPC boundary, is what separates environments             │
│                                                                         │
│  NOT ENFORCED: dedicated sandbox VPC, VPC peering restrictions as a     │
│  sandbox-specific control, sandbox-specific private hosted zone.        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Security Group Configuration

As deployed in `deploy/cloudformation/sandbox.yaml`:

```yaml
SandboxSecurityGroup:
  Type: AWS::EC2::SecurityGroup
  Condition: HasVpc
  Properties:
    GroupName: !Sub '${ProjectName}-sandbox-isolated-${Environment}'
    GroupDescription: Highly restrictive security group for sandbox patch testing
    # VPC is imported from the networking stack -- the platform VPC,
    # not a dedicated sandbox VPC.
    VpcId: !Ref VpcId
    # Inbound: no rules declared, so nothing may initiate a connection in.
    SecurityGroupEgress:
      - IpProtocol: udp
        FromPort: 53
        ToPort: 53
        CidrIp: 0.0.0.0/0
        Description: DNS resolution
      - IpProtocol: tcp
        FromPort: 443
        ToPort: 443
        CidrIp: 0.0.0.0/0
        Description: HTTPS for AWS APIs and package downloads
```

Note that TCP 443 egress is open to `0.0.0.0/0`. It is scoped by port, not by
destination, so the sandbox is not egress-free.

### IAM Task Role

Production data stores are unreachable because the task role never grants them,
not because an explicit `Deny` statement blocks them. `SandboxTaskRole` in
`deploy/cloudformation/sandbox.yaml` is an allow-list:

```yaml
Statement:
  - Effect: Allow
    Action: [dynamodb:GetItem, dynamodb:PutItem, dynamodb:UpdateItem]
    Resource:
      - !GetAtt SandboxStateTable.Arn
      - !GetAtt SandboxResultsTable.Arn
  - Effect: Allow
    Action: [logs:CreateLogStream, logs:PutLogEvents]
    Resource:
      - !Sub 'arn:${AWS::Partition}:logs:${AWS::Region}:${AWS::AccountId}:log-group:/ecs/sandboxes-${Environment}:*'
  - Effect: Allow
    Action: [s3:GetObject]
    Resource:
      - !Sub 'arn:${AWS::Partition}:s3:::${ProjectName}-sandbox-artifacts-${AWS::AccountId}-${Environment}/*'
```

There is no `neptune-db`, `es`, or broad `s3` grant, and no `sts:AssumeRole`
grant for another account.

---

## Validation Categories

Every patch must pass five validation categories before it can proceed to human review. Failure in any category results in automatic rejection.

### Category Overview

| Category | What It Validates | Failure Criteria | Timeout |
|----------|-------------------|------------------|---------|
| **Syntax** | Code compiles and parses correctly | Any parse/compile error | 1 min |
| **Unit Tests** | Existing test suite passes | Any test failure | 10 min |
| **Security Scans** | No new vulnerabilities introduced | New HIGH/CRITICAL CVEs | 5 min |
| **Performance** | No latency regression | >10% latency increase | 5 min |
| **Integration** | API compatibility maintained | Contract violations | 10 min |

### 1. Syntax Validation

The first and fastest check ensures the patched code is syntactically valid.

**What It Checks:**
- Python: `python -m py_compile`
- JavaScript: `eslint --parser-options=ecmaVersion:2022`
- TypeScript: `tsc --noEmit`
- Go: `go build`

**Pass Criteria:**
```
Syntax Validation: PASSED
- Files validated: 3
- Parse errors: 0
- Warnings: 2 (non-blocking)
```

**Failure Example:**
```
Syntax Validation: FAILED
- File: src/services/auth_service.py
- Line: 47
- Error: IndentationError: unexpected indent
- Status: REJECTED (syntax error prevents further validation)
```

### 2. Unit Test Execution

The sandbox runs the existing test suite to ensure the patch does not break functionality.

**What It Checks:**
- Existing unit tests in `tests/` directory
- Test fixtures and mocks
- Code coverage (must not decrease)

**Configuration:**
```python
# Sandbox test configuration
SANDBOX_TEST_CONFIG = {
    "framework": "pytest",
    "parallel": True,
    "max_workers": 4,
    "timeout_per_test": 30,  # seconds
    "fail_fast": False,  # Run all tests even if some fail
    "coverage_threshold": 70,  # Minimum coverage percentage
    "markers_exclude": ["slow", "integration"]  # Skip slow tests
}
```

**Pass Criteria:**
```
Unit Tests: PASSED
- Tests executed: 147
- Tests passed: 147
- Tests failed: 0
- Coverage: 78.3% (threshold: 70%)
- Duration: 2m 34s
```

**Failure Example:**
```
Unit Tests: FAILED
- Tests executed: 147
- Tests passed: 145
- Tests failed: 2
- Failures:
  - test_user_authentication: AssertionError - Expected 200, got 401
  - test_password_validation: TypeError - unsupported operand type
- Status: REJECTED (2 test failures)
```

### 3. Security Scanning

Automated security scans verify the patch does not introduce new vulnerabilities.

**Scan Types:**

| Scan | Tool | Focus |
|------|------|-------|
| SAST | Semgrep, Bandit | Code-level vulnerabilities |
| SCA | Snyk, Safety | Dependency vulnerabilities |
| Secrets | TruffleHog, GitLeaks | Hardcoded credentials |
| Container | Trivy | Base image CVEs |

**What It Checks:**
- New vulnerability findings compared to baseline
- Severity classification (CRITICAL, HIGH, MEDIUM, LOW)
- Known CVE correlation

**Pass Criteria:**
```
Security Scans: PASSED
- SAST findings: 0 new (3 existing, accepted)
- SCA findings: 0 new
- Secrets detected: 0
- Delta: No new vulnerabilities introduced
```

**Failure Example:**
```
Security Scans: FAILED
- New vulnerability detected:
  - Type: SQL Injection (CWE-89)
  - Severity: HIGH
  - File: src/db/query_builder.py:23
  - Description: User input concatenated into SQL query
- Status: REJECTED (new HIGH severity vulnerability)
```

### 4. Performance Benchmarking

Performance tests ensure the patch does not introduce latency regressions.

**What It Measures:**
- API endpoint response times
- Memory consumption
- CPU utilization
- Database query latency

**Benchmark Configuration:**
```python
PERFORMANCE_CONFIG = {
    "baseline_comparison": True,
    "regression_threshold_percent": 10,  # Max allowed degradation
    "warmup_requests": 100,
    "measurement_requests": 1000,
    "concurrent_users": 10,
    "percentiles": [50, 95, 99]
}
```

**Pass Criteria:**
```
Performance Tests: PASSED
- Endpoint: /api/v1/users
- Baseline P95: 45ms
- Patched P95: 47ms (+4.4%)
- Threshold: 10%
- Status: PASSED (within threshold)
```

**Failure Example:**
```
Performance Tests: FAILED
- Endpoint: /api/v1/process
- Baseline P95: 120ms
- Patched P95: 185ms (+54.2%)
- Threshold: 10%
- Status: REJECTED (54.2% regression exceeds 10% threshold)
```

### 5. Integration Testing

Integration tests verify API contracts and cross-service compatibility.

**What It Checks:**
- API schema compliance (OpenAPI validation)
- Request/response contract testing
- Backward compatibility for existing clients
- Service communication patterns

**Pass Criteria:**
```
Integration Tests: PASSED
- API contracts validated: 12
- Breaking changes: 0
- Deprecation warnings: 1 (acceptable)
- Client compatibility: 100%
```

**Failure Example:**
```
Integration Tests: FAILED
- Breaking change detected:
  - Endpoint: POST /api/v1/users
  - Field removed: "legacy_id" (required by v1 clients)
  - Affected clients: mobile-app-v2, partner-api
- Status: REJECTED (breaking API change)
```

---

## Validation Pipeline

The validation pipeline executes all categories in a defined sequence with early termination on failure.

### Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SANDBOX VALIDATION PIPELINE                          │
└─────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  1. PROVISION SANDBOX               │
│  ─────────────────────────          │
│  - Create Fargate task              │
│  - Deploy patched code              │
│  - Initialize mock services         │
│  Timeout: 5 minutes                 │
└─────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  2. SYNTAX VALIDATION               │
│  ─────────────────────────          │
│  - Parse all modified files         │
│  - Check compilation                │
│  Timeout: 1 minute                  │
│                                     │
│  [FAIL] ───────────────────────────────────────────────┐
└─────────────────────────────────────┘                  │
         │                                               │
         │ [PASS]                                        │
         ▼                                               │
┌─────────────────────────────────────┐                  │
│  3. UNIT TESTS                      │                  │
│  ─────────────────────────          │                  │
│  - Execute test suite               │                  │
│  - Calculate coverage               │                  │
│  Timeout: 10 minutes                │                  │
│                                     │                  │
│  [FAIL] ───────────────────────────────────────────────┤
└─────────────────────────────────────┘                  │
         │                                               │
         │ [PASS]                                        │
         ▼                                               │
┌─────────────────────────────────────┐                  │
│  4. SECURITY SCANS                  │                  │
│  ─────────────────────────          │                  │
│  - SAST analysis                    │                  │
│  - SCA dependency check             │                  │
│  - Secrets detection                │                  │
│  Timeout: 5 minutes                 │                  │
│                                     │                  │
│  [FAIL] ───────────────────────────────────────────────┤
└─────────────────────────────────────┘                  │
         │                                               │
         │ [PASS]                                        │
         ▼                                               │
┌─────────────────────────────────────┐                  │
│  5. PERFORMANCE TESTS               │                  │
│  ─────────────────────────          │                  │
│  - Benchmark endpoints              │                  │
│  - Compare to baseline              │                  │
│  Timeout: 5 minutes                 │                  │
│                                     │                  │
│  [FAIL] ───────────────────────────────────────────────┤
└─────────────────────────────────────┘                  │
         │                                               │
         │ [PASS]                                        │
         ▼                                               │
┌─────────────────────────────────────┐                  │
│  6. INTEGRATION TESTS               │                  │
│  ─────────────────────────          │                  │
│  - API contract validation          │                  │
│  - Compatibility checks             │                  │
│  Timeout: 10 minutes                │                  │
│                                     │                  │
│  [FAIL] ───────────────────────────────────────────────┤
└─────────────────────────────────────┘                  │
         │                                               │
         │ [PASS]                                        │
         ▼                                               ▼
┌─────────────────────────────────────┐  ┌─────────────────────────────┐
│  VALIDATION PASSED                  │  │  VALIDATION FAILED          │
│  ─────────────────────────          │  │  ─────────────────────────  │
│  - Generate success report          │  │  - Generate failure report  │
│  - Proceed to HITL review           │  │  - Notify Coder Agent       │
│  - Preserve sandbox for review      │  │  - Log failure details      │
└─────────────────────────────────────┘  │  - Teardown sandbox         │
                                         └─────────────────────────────┘
```

### Early Termination

The pipeline terminates immediately upon any failure to conserve resources:

```python
class SandboxValidator:
    def validate_patch(self, patch_code: str, metadata: dict) -> ValidationResult:
        """
        Execute validation pipeline with early termination.
        Fails fast to minimize sandbox runtime and costs.
        """
        stages = [
            ("syntax", self.validate_syntax),
            ("unit_tests", self.run_unit_tests),
            ("security", self.run_security_scans),
            ("performance", self.run_performance_tests),
            ("integration", self.run_integration_tests),
        ]

        results = {}
        for stage_name, stage_func in stages:
            result = stage_func(patch_code)
            results[stage_name] = result

            if not result.passed:
                # Early termination - do not run remaining stages
                return ValidationResult(
                    passed=False,
                    failed_stage=stage_name,
                    failure_reason=result.failure_reason,
                    results=results
                )

        return ValidationResult(passed=True, results=results)
```

---

## Resource Limits and Timeouts

Sandboxes operate under strict resource constraints to prevent runaway processes and control costs.

### Resource Allocation

| Resource | Limit | Justification |
|----------|-------|---------------|
| **CPU** | 0.5 vCPU | Sufficient for test execution |
| **Memory** | 1 GB | Covers typical test suites |
| **Storage** | 20 GB ephemeral | Temporary build artifacts |
| **Network** | Outbound only | Package downloads only |
| **Task Duration** | 30 minutes max | Hard limit, auto-terminated |

### Timeout Configuration

```python
SANDBOX_TIMEOUTS = {
    "provisioning": 300,       # 5 minutes
    "syntax_validation": 60,   # 1 minute
    "unit_tests": 600,         # 10 minutes
    "security_scans": 300,     # 5 minutes
    "performance_tests": 300,  # 5 minutes
    "integration_tests": 600,  # 10 minutes
    "total_execution": 1800,   # 30 minutes (hard limit)
}
```

### Automatic Cleanup

Sandboxes are automatically destroyed after execution to prevent resource accumulation:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SANDBOX LIFECYCLE                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  CREATION                                                               │
│  ────────                                                               │
│  - Trigger: Patch generated by Coder Agent                              │
│  - Duration: ~2 minutes for provisioning                                │
│  - Resources: Fargate task, CloudWatch log group                        │
│                                                                         │
│  EXECUTION                                                              │
│  ─────────                                                              │
│  - Duration: Variable (typically 5-15 minutes)                          │
│  - Maximum: 30 minutes (hard timeout)                                   │
│  - Monitoring: CloudWatch metrics, real-time logs                       │
│                                                                         │
│  DESTRUCTION                                                            │
│  ───────────                                                            │
│  - Trigger: Validation complete OR timeout reached                      │
│  - Automatic: No manual intervention required                           │
│  - Retention: Logs retained for 90 days (dev) / 365 days (prod)         │
│                                                                         │
│  COST OPTIMIZATION                                                      │
│  ─────────────────                                                      │
│  - Fargate Spot: 70% cost reduction for ephemeral tasks                 │
│  - Auto-teardown: Prevents orphaned resources                           │
│  - Shared VPC: Amortized networking costs                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Sandbox Results and Reporting

Every sandbox execution produces a comprehensive report for human reviewers.

### Report Structure

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SANDBOX VALIDATION REPORT                            │
│                    sandbox-2026-01-19-abc123                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  SUMMARY                                                                │
│  ───────                                                                │
│  Status:           PASSED                                               │
│  Duration:         8 minutes 23 seconds                                 │
│  Patch ID:         patch-2026-01-19-xyz789                              │
│  Vulnerability:    SQL Injection (CVE-2026-12345)                       │
│                                                                         │
│  VALIDATION RESULTS                                                     │
│  ──────────────────                                                     │
│  ┌────────────────────┬──────────┬───────────┬─────────────────────┐    │
│  │ Category           │ Status   │ Duration  │ Details             │    │
│  ├────────────────────┼──────────┼───────────┼─────────────────────┤    │
│  │ Syntax Validation  │ PASSED   │ 12s       │ 3 files validated   │    │
│  │ Unit Tests         │ PASSED   │ 4m 15s    │ 147/147 passed      │    │ 
│  │ Security Scans     │ PASSED   │ 2m 08s    │ 0 new findings      │    │ 
│  │ Performance Tests  │ PASSED   │ 1m 32s    │ +4.4% latency       │    │
│  │ Integration Tests  │ PASSED   │ 16s       │ 12 contracts valid  │    │
│  └────────────────────┴──────────┴───────────┴─────────────────────┘    │
│                                                                         │
│  METRICS                                                                │
│  ───────                                                                │
│  Test Coverage:    78.3% (baseline: 76.1%, delta: +2.2%)                │
│  CPU Utilization:  34% average                                          │
│  Memory Peak:      512 MB                                               │
│  Network I/O:      23 MB (package downloads)                            │
│                                                                         │
│  ARTIFACTS                                                              │
│  ─────────                                                              │
│  - Full test report: s3://aura-sandbox/reports/abc123/test-report.html  │
│  - Coverage report:  s3://aura-sandbox/reports/abc123/coverage.html     │
│  - Security report:  s3://aura-sandbox/reports/abc123/security.json     │
│  - CloudWatch logs:  /aws/ecs/aura-sandbox/abc123                       │
│                                                                         │
│  RECOMMENDATION: Proceed to HITL approval                               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Failure Report Example

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    SANDBOX VALIDATION REPORT                            │
│                    sandbox-2026-01-19-def456                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  SUMMARY                                                                │
│  ───────                                                                │
│  Status:           FAILED                                               │
│  Failed Stage:     Unit Tests                                           │
│  Duration:         5 minutes 41 seconds                                 │
│                                                                         │
│  FAILURE DETAILS                                                        │
│  ───────────────                                                        │
│  Test:     test_user_authentication                                     │
│  File:     tests/test_auth.py:47                                        │
│  Error:    AssertionError                                               │
│                                                                         │
│  Expected: status_code == 200                                           │
│  Actual:   status_code == 401                                           │
│                                                                         │
│  Stack Trace:                                                           │
│  ─────────────                                                          │
│  tests/test_auth.py:47: AssertionError                                  │
│    > assert response.status_code == 200                                 │
│    E AssertionError: assert 401 == 200                                  │
│    E  + where 401 = <Response [401]>.status_code                        │
│                                                                         │
│  ROOT CAUSE ANALYSIS                                                    │
│  ───────────────────                                                    │
│  The patch modified the authentication flow in auth_service.py.         │
│  The existing test expects a 200 response, but the patched code         │
│  now requires an additional header that the test does not provide.      │
│                                                                         │
│  RECOMMENDED ACTION                                                     │
│  ──────────────────                                                     │
│  Coder Agent should update the patch to maintain backward               │
│  compatibility with existing authentication patterns.                   │
│                                                                         │
│  STATUS: Patch rejected, Coder Agent notified                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Isolation

Sandboxes never access production data. All test data is synthetic or anonymized.

### Data Sources

| Data Type | Source | Production Access |
|-----------|--------|-------------------|
| **Test fixtures** | Committed to repository | No |
| **Mock API responses** | Generated by mock services | No |
| **Database seeds** | Synthetic data generators | No |
| **User data** | Faker library (fake names, emails) | No |
| **Secrets** | Dummy values for testing | No |

### Mock Service Configuration

```python
# Sandbox mock configuration
MOCK_SERVICES = {
    "neptune": {
        "endpoint": "mock-neptune.sandbox.aura.internal",
        "type": "localstack",
        "data": "synthetic_graph_fixtures.json"
    },
    "opensearch": {
        "endpoint": "mock-opensearch.sandbox.aura.internal",
        "type": "localstack",
        "data": "synthetic_vectors.json"
    },
    "external_apis": {
        "github": "mock-github.sandbox.aura.internal",
        "slack": "mock-slack.sandbox.aura.internal",
        "response_mode": "recorded_fixtures"
    }
}
```

### Why No Production Data?

1. **Security**: Production data may contain PII, credentials, or sensitive business information
2. **Compliance**: HIPAA, SOX, and GDPR prohibit copying production data to test environments
3. **Performance**: Synthetic data can be optimized for fast test execution
4. **Determinism**: Controlled test data produces reproducible results

---

## Cost Analysis

Sandbox validation is cost-effective due to ephemeral provisioning and Spot pricing.

### Per-Patch Cost Breakdown

| Resource | Usage | Cost (USD) |
|----------|-------|------------|
| Fargate (Spot) | 0.5 vCPU x 1 GB x 15 min | $0.01 |
| CloudWatch Logs | 50 MB | $0.03 |
| S3 (reports) | 10 MB stored | $0.00 |
| Data transfer | 25 MB | $0.00 |
| **Total per patch** | | **$0.04** |

### Monthly Projections

| Patches/Month | Sandbox Cost | Notes |
|---------------|--------------|-------|
| 100 | $4 | Small team |
| 500 | $20 | Medium team |
| 2,000 | $80 | Large enterprise |
| 10,000 | $400 | High-volume CI/CD |

**Cost Optimization Strategies:**
- Fargate Spot for 70% discount
- Aggressive timeouts prevent runaway costs
- Automatic teardown eliminates orphaned resources
- Shared VPC amortizes networking

---

## Compliance Mapping

Sandbox validation satisfies multiple compliance framework requirements.

| Framework | Requirement | Sandbox Control |
|-----------|-------------|-----------------|
| **CMMC Level 3** | CM.L2-3.4.5 Test changes | Automated test execution |
| **SOX** | Change management testing | Documented validation results |
| **NIST 800-53** | CM-3 Configuration Change Control | Isolated test environment |
| **FedRAMP** | CM-4 Security Impact Analysis | Security scans before deployment |
| **HIPAA** | Audit controls | Full execution logging |
| **PCI-DSS 4.0** | 6.5.3 Pre-deployment testing | Automated regression detection |

### Audit Evidence

All sandbox executions produce audit evidence:

- **Execution timestamp**: When validation started/completed
- **Resource identifiers**: Sandbox ID, task ARN, log group
- **Test results**: Pass/fail status with details
- **Artifacts**: Reports stored in S3 with WORM policy
- **Retention**: 7 years for compliance requirements

---

## Key Takeaways

> **Every patch is validated before human review.** The sandbox layer ensures that human reviewers only see patches that have passed automated validation, saving time and reducing risk.

> **Sandbox reachability is constrained by security group and IAM allow-list.** A sandbox task has no inbound rules, no public IP, egress only on UDP 53 and TCP 443, and a task role that grants nothing beyond two sandbox DynamoDB tables, one log group and one S3 artifact prefix. It is not a dedicated-VPC boundary, and `vpc` / `full` isolation levels are refused rather than provided -- see the Isolation Levels table above.

> **Five validation categories provide comprehensive coverage.** Syntax, unit tests, security scans, performance, and integration tests catch different categories of issues.

> **Resource limits prevent runaway processes.** Strict CPU, memory, and timeout limits ensure sandboxes cannot consume excessive resources.

> **Sandbox validation is cost-effective.** Ephemeral provisioning and Spot pricing keep per-patch costs under $0.05.

---

## Related Concepts

- [HITL Workflows](./hitl-workflows.md) - Human approval that follows sandbox validation
- [Multi-Agent System](./multi-agent-system.md) - Validator Agent that orchestrates sandbox testing
- [Autonomous Security Intelligence](./autonomous-security-intelligence.md) - AI that generates patches for validation
- [Hybrid GraphRAG](./hybrid-graphrag.md) - Context used to configure sandbox tests

---

## Technical References

- ADR-005: HITL Sandbox Architecture
- ADR-007: Ephemeral Test Environment Provisioning
- ADR-039: Self-Service Test Environments
- `docs/design/HITL_SANDBOX_ARCHITECTURE.md` - Detailed technical specification
