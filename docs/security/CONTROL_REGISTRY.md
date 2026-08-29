# Control Registry - Aura Internal Security Controls

**Status:** Active
**Version:** 1.3.0
**Last Updated:** 2026-08-29

---

## Overview

This registry assigns a stable internal identifier to each security control Aura implements in
infrastructure. Controls are referenced by their `AURA-CTL-###` ID from CloudFormation template
metadata, code comments, and audit evidence, so that a control has one durable name regardless of
which external framework happens to be asking about it.

**Why an internal ID rather than an external one.** A given control usually satisfies several
frameworks at once, and each framework names it differently. Hardcoding one framework's identifier
into a template makes the template look like it exists to serve that framework, ties our source to
someone else's numbering, and ages badly when that numbering changes. An internal ID is the stable
handle; the framework mappings hang off it here.

---

## Namespace Rules

`AURA-CTL-###` is the namespace for **implemented security controls**. It is deliberately distinct
from the identifier schemes already in use, none of which mean "control":

| Namespace | Meaning | Defined in |
|-----------|---------|------------|
| `AURA-CTL-###` | **Implemented security control** (this registry) | `docs/security/CONTROL_REGISTRY.md` |
| `AURA-<DOMAIN>-###` | Runtime **error codes** (`AUTH`, `API`, `AGT`, `INF`, `SV`) | `docs/support/troubleshooting/` |
| `SEC-###` | Org standards validator **rule IDs** | `src/services/security/org_standards_validator.py` |
| `GR-<DOMAIN>-###` | Guardrail rule IDs | `src/services/cognitive_memory_service.py` |
| `CC*` / `A*` / `C*` | SOC 2 Trust Services Criteria (external) | `src/services/compliance_evidence_service.py` |
| `ADR-###` | Architecture decisions | `docs/architecture-decisions/` |

**Rules:**

- IDs are assigned sequentially and are **never reused**, even if a control is retired.
- A control keeps its ID across refactors. If the implementation moves, update the reference column,
  not the ID.
- Retired controls stay in this table with status `Retired` and the reason.

**Status vocabulary.** "Implemented" describes the code or template in this repository, **not** the
running estate. A control is not satisfied and must not be attested until its Evidence section has
been executed against a deployed environment.

| Status | Meaning |
|---|---|
| `Implemented` | Merged and in effect on the code path it governs |
| `Implemented, not deployed` | Merged and locally verified; the infrastructure it configures has never been deployed, so the control is **not** active anywhere |
| `Retired` | No longer in force; row kept with the reason |

### Customer and framework mappings

**Do not record customer-specific control identifiers in this repository.** The `Frameworks` column
below is limited to public standards (NIST 800-53, SOC 2, CMMC). Where a customer, prospect, or
partner maintains their own internal control numbering, that mapping is maintained outside this
repository in the relevant engagement material.

This repository is public. The internal ID exists precisely so that source, templates, and commit
history can reference a control without disclosing who asked for it or how they number it.

---

## Registry

| ID | Control | Status | Implementation | Frameworks |
|----|---------|--------|----------------|------------|
| `AURA-CTL-001` | **Model I/O Audit Logging** -- Bedrock model invocation input and output are captured as audit records. Every record is delivered in full to an encrypted S3 corpus; CloudWatch Logs, encrypted with a customer-managed key, carries the same records for operational query, with bodies over 100 KB referenced from S3 rather than dropped. | **Implemented, not deployed** | `deploy/cloudformation/bedrock-invocation-logging.yaml` (Layer 4.15) | NIST 800-53 AU-2, AU-3, AU-9, AU-11, SC-28 |
| `AURA-CTL-002` | **Sandbox Network Boundary Truthfulness** -- the sandbox provisioning path refuses any network isolation level it does not actually enforce, instead of accepting the request and provisioning a weaker boundary under the stronger name. `ENFORCED_ISOLATION_LEVELS` is the single source of truth for what is implemented. | Implemented | `src/services/sandbox_network_service.py:79` (`ENFORCED_ISOLATION_LEVELS`, `UnsupportedIsolationLevelError`); `deploy/cloudformation/sandbox.yaml` (Layer 7.1) | NIST 800-53 SC-7, SC-7(21), AC-4, SA-4(9), CM-4 |
| `AURA-CTL-003` | **Error Response Detail Suppression** -- unhandled API exceptions return a generic body. The exception message is never included in any environment, and a debug request is honored only where the resolved environment is debug-safe. Full detail is logged server-side against the `request_id` the caller receives. | Implemented | `src/api/security_middleware.py:34` (`DEBUG_SAFE_ENVIRONMENTS`), `:283-301` (interlock), `:334-341` (response body); `src/api/main.py:395`, `:481` (wiring) | NIST 800-53 SI-11, AU-3, AU-9, CM-7(1) |

---

## AURA-CTL-001: Model I/O Audit Logging

> **Status: Implemented, not deployed (as of 2026-08-29).** The template is merged; the stack has
> never been deployed to any environment. **Model invocation logging is not capturing anything
> today, in dev, qa or prod.** Do not cite this control as active, and do not use it as evidence for
> AU-2 / AU-3 / AU-9 / AU-11 / SC-28 until the Evidence section below has actually been executed
> against a deployed stack -- including the 100 KB boundary test in both directions. Verification to
> date is local only: `cfn-lint` wrapper passed, three injected fault classes correctly caught,
> `validate_iam_actions.py` 16 valid / 0 invalid, inline Lambda AST-compiles. GovCloud availability
> of `PutModelInvocationLoggingConfiguration` is **unverified**. Deployment is cost-gated on the DEV
> environment being restored; see `docs/DEFERRED_WORK_REGISTRY.md`.

### Requirement

Prompts and completions sent to and returned from foundation models are audit-relevant records. They
must be captured in full, retained for the environment's retention period, and encrypted at rest
under a key the organization controls.

### Implementation

Defined by `deploy/cloudformation/bedrock-invocation-logging.yaml`. Everything below describes what
the template does **when deployed**; it has not been:

- **Capture.** A Lambda-backed custom resource applies the Bedrock model invocation logging
  configuration. There is no native CloudFormation resource type for this configuration, so it is
  managed through `bedrock:PutModelInvocationLoggingConfiguration`. The function reads back its own
  write and fails the stack if the configuration did not take effect.
- **Encryption at rest.** A customer-managed KMS key with rotation enabled encrypts both the
  CloudWatch log group and the S3 overflow bucket. One key covers the whole evidence path.
- **Completeness.** Bedrock writes bodies inline to CloudWatch Logs only up to 100 KB. Above that,
  bodies go to S3 — or are dropped silently if no S3 destination is configured.

  **This is Aura's normal operating range, not an edge case.** `ContextStackConfig.total_budget` is
  100,000 tokens and `_estimate_tokens()` is `len(text) // 4`, so a full context is roughly 400 KB —
  four times the inline threshold. The `RETRIEVED_DOCUMENTS` layer alone is budgeted at 50,000 tokens
  (~200 KB), double the threshold by itself. See `src/services/context_stack_manager.py:85` and
  `:548`.

  The control therefore uses **dual delivery**:

  | Destination | Prefix / target | Contents |
  |---|---|---|
  | S3 (`s3Config`) | `invocation-logs/` | **Authoritative corpus** — every record, any size, unsplit |
  | CloudWatch Logs (`cloudWatchConfig`) | log group | Operational query surface; bodies inline up to 100 KB |
  | S3 (`largeDataDeliveryS3Config`) | `large-data/` | Bodies over 100 KB, referenced from the CloudWatch events |

  Full S3 delivery is what keeps an audit record whole. With CloudWatch alone, a record over 100 KB
  lives half in the log group and half in S3, and a Logs Insights query for prompt content returns
  nothing for exactly the largest invocations — which is indistinguishable from "no such prompt".
  S3 is the store to query when completeness matters; CloudWatch is for operational triage.
- **Retention.** 90 days (dev), 180 days (qa), 365 days (prod), applied to the log group and to *both*
  S3 prefixes from the same environment mapping, so a CloudWatch pointer can never outlive the body
  it points at.

### Scope and limitations

- The logging configuration is an **account + region singleton**. It is not scoped to the stack.
  Deleting the stack disables model invocation logging for the entire account in that region.
- Only invocations through the `bedrock-runtime` endpoint are captured. Verified: `BedrockLLMService`
  uses `bedrock-runtime` (`src/services/bedrock_llm_service.py`).

### Evidence

- Log group and its ARN are published to SSM at
  `/{project}/{environment}/bedrock/invocation-log-group-{name,arn}`.
- Stack outputs expose the log group, KMS key ARN, overflow bucket, and delivery role for
  cross-stack reference and audit collection.
- Verification: `aws bedrock get-model-invocation-logging-configuration --region <region>` returns
  the applied configuration. The custom resource additionally reads its own write back at deploy time
  and fails the stack if `cloudWatchConfig.logGroupName`, `largeDataDeliveryS3Config`, `s3Config`, or
  `textDataDeliveryEnabled` is missing or wrong — so a configuration that applied partially cannot
  report success.
- **Boundary test (required before attesting this control).** Verifying with a small prompt only
  proves the inline path. Exercise both sides: one invocation under 100 KB (body inline in the log
  event) and one over (log event carries an S3 reference, and the object exists under `large-data/`
  encrypted with the CMK). In both cases a complete record must also be present under
  `invocation-logs/`. Without both halves, a working overflow path is indistinguishable from a
  silently dropped body.

---

## AURA-CTL-002: Sandbox Network Boundary Truthfulness

### Requirement

A sandbox is a security boundary whose value depends entirely on the caller
believing the boundary is what it was told it is. A provisioning path that
accepts a request for a strong isolation level and delivers a weaker one is
worse than one that has no isolation at all, because the caller then reasons
about a boundary that does not exist. The platform threat model names "network
isolation bypass" explicitly, so this is in scope rather than a style
preference.

The control: the requested isolation level is either enforced as named, or the
request is refused. There is no silent downgrade path.

### Implementation

`NetworkIsolationLevel` declares four levels (`none`, `container`, `vpc`,
`full`). `ENFORCED_ISOLATION_LEVELS`
(`src/services/sandbox_network_service.py:79`) is a frozenset naming the two the
live path implements: `NONE` and `CONTAINER`.

- **Refusal.** `FargateSandboxOrchestrator._require_enforced_isolation` runs at
  the top of `create_sandbox`, before any AWS call, so the refusal does not
  depend on reaching ECS. An unenforced-but-declared level raises
  `UnsupportedIsolationLevelError` (a `ValueError` subclass) naming what would
  otherwise have happened; a value that is not an isolation level at all raises
  plain `ValueError` listing the valid names.
- **What `container` actually enforces.** The task runs in the private subnets
  with the sandbox security group and `assignPublicIp: DISABLED`.
  `SandboxSecurityGroup` in `deploy/cloudformation/sandbox.yaml` declares no
  inbound rules and limits egress to UDP 53 and TCP 443. `SandboxTaskRole` is an
  allow-list covering two DynamoDB tables, one log group and one S3 artifact
  prefix.
- **Simulation is labelled as such.** `SandboxNetworkOrchestrator` is a
  simulation harness with no callers outside its own tests; all four of its
  levels fabricate identifiers and make no AWS call. Records it produces carry
  `simulated=True` in the dataclass and in `to_dict()`, so a consumer can tell a
  placeholder from a real network without reading the provisioning code.
- **Defaults.** `sandbox_isolation_level` defaulted to `"vpc"` in both the
  persistence layer and the settings API, which was persisted and shown to
  operators but never read by provisioning. The default is now `"container"`,
  and the API field description states which levels are enforced.

### Scope and limitations

- **`vpc` and `full` are not provided.** This control makes their absence
  explicit; it does not implement them. Doing so requires per-level subnets and
  security groups provisioned in CloudFormation and selected by
  `_get_sandbox_subnets`.
- Sandbox tasks share the platform VPC's private subnets. There is no dedicated
  sandbox VPC (`deploy/cloudformation/sandbox.yaml` takes `VpcId` and
  `PrivateSubnetIds` as parameters imported from the networking stack).
- TCP 443 egress is open to `0.0.0.0/0`. It is scoped by port, not by
  destination, so a sandbox is not egress-free.
- Resource discovery previously could not succeed at all: `_get_sandbox_subnets`
  filtered on `tag:Type=private`, which `networking.yaml` did not create, and
  `_get_sandbox_security_groups` expected a Name tag of
  `sg-{env}-sandbox-isolated` while `sandbox.yaml` creates
  `${ProjectName}-sandbox-isolated-${Environment}`. Both documented SSM
  fallbacks are published by no template, so each lookup always raised.
  **Fixed in #413** -- the subnets now carry `Type: private`, and the
  security-group lookup follows the repo's naming convention.
- The SSM fallbacks (`/aura/{env}/sandbox/subnet-ids`,
  `/aura/{env}/sandbox/security-group-id`) remain unpublished. The tag-based
  primary path works, so these are now genuinely fallbacks rather than the only
  remaining hope, but the code's error messages still offer them as an option.

### Evidence

- `ENFORCED_ISOLATION_LEVELS` is the assertable artifact: it is a module
  constant, not a config value, so the enforced set cannot drift from the code
  at runtime.
- `tests/test_sandbox_isolation_enforcement.py` covers refusal of each
  unenforced level, acceptance of each enforced level, rejection of unknown
  values, and that validation precedes any AWS call.
- Verification that the refusal is live: call
  `FargateSandboxOrchestrator.create_sandbox(..., isolation_level="full")` and
  confirm `UnsupportedIsolationLevelError` with no ECS `RunTask` attempted.

---

## AURA-CTL-003: Error Response Detail Suppression

> **Status: Implemented (as of 2026-08-29).** This control is in force on the code path from the
> moment the application starts; it configures no infrastructure and has no deployment dependency,
> which is why it is `Implemented` rather than `Implemented, not deployed`. **This is a statement
> about the code path, not about a running estate** -- dev and qa are spun down, so the control has
> not been observed operating against live traffic. Verification to date is the unit suite in
> `tests/test_security_middleware.py`, plus the fault injection recorded in `fc9ab72` (restoring
> `"message": str(e)` fails `test_debug_never_returns_exception_message`; reverting it passes, while
> the interlock tests stay green under the injection, confirming the two mechanisms are tested
> independently rather than one masking the other).

### Requirement

An unhandled exception must not become a disclosure channel. Exception text produced deep in a
service routinely embeds the operational detail that produced it -- connection strings, ARNs, account
identifiers, fragments of the request body -- and an error response is reachable by whoever sent the
request. Detail needed for diagnosis belongs in the server log, correlated to the request, not in the
response.

### Implementation

Defined by `SecureExceptionMiddleware` in `src/api/security_middleware.py`. Two mechanisms, either of
which is sufficient on its own; both are present deliberately.

- **The message is never returned.** The response body names the exception and points at the log:
  `{"exception": "<type name>", "detail": "<pointer to the server log>"}` (`:334-341`). `str(e)` is
  absent from the response in every environment, debug or not. Nothing is lost -- `logger.exception`
  at `:312` has already recorded the message and the full traceback against the same `request_id`
  that the caller receives in the body and on the `X-Request-ID` header.
- **A debug request is checked against the environment, not trusted.** `DEBUG_SAFE_ENVIRONMENTS`
  (`:34`) is a module-level frozenset naming the four environments where a debug body is permitted:
  `dev`, `development`, `local`, `test`. The constructor (`:283-301`) resolves the environment,
  normalizes it with `.strip().lower()`, and drops `debug` with a logged `ERROR` if the environment
  is not in that set. The check is in `__init__`, so the refusal is decided once at startup rather
  than per request.

The interlock exists because the two variables were independent. `main.py` reads `DEBUG` as its own
variable (`main.py:443`) with no relationship to `ENVIRONMENT`, so a single stray `DEBUG=true` on a
production deployment previously turned every unhandled exception into `str(e)` on the wire. `main.py`
now passes the canonical resolution of `ENVIRONMENT` through (`main.py:481`), so the two cannot
disagree, and the middleware re-checks rather than relying on the call site having done so.

### Scope and limitations

- **The `prod` fail-closed default applies to the assembled application.** `main.py` passes the raw
  resolution of `ENVIRONMENT` -- `None` when unset or blank -- so the middleware's own `prod`
  fallback (`:284`) is reached rather than bypassed. With `ENVIRONMENT` unset, `DEBUG=true` is
  refused. This was not true when the control was first recorded: `main.py` passed its own `dev`
  fallback, so an unconfigured deployment honored `DEBUG=true` and the fail-closed default protected
  only a direct consumer of the middleware. Residual exposure in that state was the exception *type
  name* only, since the first mechanism withholds the message unconditionally. Corrected in the same
  change that added `test_main_wires_debug_interlock`, which pins the wiring rather than the
  middleware in isolation.
- **`ENVIRONMENT` is normalized once** (`main.py:395`, `.strip().lower()`, blank treated as unset)
  and every environment-dependent decision derives from that value, so case and whitespace cannot
  make two decisions disagree. Two derived defaults remain, deliberately: `dev` for HSTS and the
  docs gate, the raw value for the debug interlock. Both are tabulated in
  `docs/runbooks/API_DEBUG_ERROR_RESPONSES.md`. Normalizing also closed a separate fail-open: a
  padded `ENVIRONMENT="  prod  "` previously failed to match `("prod", "production")` and skipped
  the CORS empty-origin refusal in production.
- **Scope is unhandled exceptions reaching this middleware.** Detail deliberately returned by an
  endpoint's own error handling, by FastAPI request validation, or by a handler that catches and
  formats its own failure, is outside this control.

### Evidence

- `DEBUG_SAFE_ENVIRONMENTS` is the assertable artifact: a module constant, not a config value, so the
  permitted set cannot drift at runtime.
- `tests/test_security_middleware.py::TestSecureExceptionHandler` covers refusal across `prod`,
  `production`, `qa` and `staging`; the unset-`ENVIRONMENT` path; case and whitespace normalization;
  that the debug body names the type; and that the raised message never appears in the response text.
- Verification that the suppression is live: issue a request that raises, and confirm the response
  contains no exception message while the service log carries the message and traceback under the
  same `request_id`. Procedure in `docs/runbooks/API_DEBUG_ERROR_RESPONSES.md`.
- Verification that the interlock is live: start the application with `DEBUG=true` and
  `ENVIRONMENT=prod` and confirm the startup log carries `Debug error responses requested but
  refused: environment=prod ...` at `ERROR`, and that a 500 response carries no `debug` key.

---

## Adding a Control

1. Claim the next sequential `AURA-CTL-###`.
2. Add a row to the registry table and a detail section below it.
3. Reference the ID from the implementing template's `Metadata.Control` field, and from code comments
   at the points that enforce it.
4. Map to public frameworks only. Customer-specific numbering stays out of this repository.
