# Control Registry - Aura Internal Security Controls

**Status:** Active
**Version:** 1.0.0
**Last Updated:** 2026-08-28

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
| `AURA-CTL-001` | **Model I/O Audit Logging** — Bedrock model invocation input and output are captured as audit records. Every record is delivered in full to an encrypted S3 corpus; CloudWatch Logs, encrypted with a customer-managed key, carries the same records for operational query, with bodies over 100 KB referenced from S3 rather than dropped. | Implemented | `deploy/cloudformation/bedrock-invocation-logging.yaml` (Layer 4.15) | NIST 800-53 AU-2, AU-3, AU-9, AU-11, SC-28 |

---

## AURA-CTL-001: Model I/O Audit Logging

### Requirement

Prompts and completions sent to and returned from foundation models are audit-relevant records. They
must be captured in full, retained for the environment's retention period, and encrypted at rest
under a key the organization controls.

### Implementation

Deployed by `deploy/cloudformation/bedrock-invocation-logging.yaml`:

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

## Adding a Control

1. Claim the next sequential `AURA-CTL-###`.
2. Add a row to the registry table and a detail section below it.
3. Reference the ID from the implementing template's `Metadata.Control` field, and from code comments
   at the points that enforce it.
4. Map to public frameworks only. Customer-specific numbering stays out of this repository.
