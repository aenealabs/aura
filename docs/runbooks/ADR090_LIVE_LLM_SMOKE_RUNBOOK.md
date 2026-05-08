# ADR-090 Live-LLM Smoke Runbook

**Last Updated:** May 8, 2026
**Workflow:** `.github/workflows/nightly-live-llm.yml`
**Test:** `tests/live/test_tier3_live_llm.py`
**Tracking Issue:** [#120](https://github.com/aenealabs/aura/issues/120)
**Owner:** Platform Engineering

---

## Overview

The nightly live-LLM smoke runs the Tier 3 symbol resolver against real Bedrock on five representative fixtures. The mocked Tier 3 tests prove the resolver code is correct given a known-shaped LLM response; this smoke catches what mocks cannot:

- A new model snapshot rolls out and changes the response shape.
- Prompt-injection defense kicks in and Bedrock returns a refusal.
- Bedrock throttling story shifts and the resolver no longer handles it gracefully.

The suite is **deferrable / P2**: it costs real money per run and adds little signal beyond what mocked tests already prove. The hard cost cap (USD 0.50 per run, enforced in-test) bounds the blast radius.

## Failure Interpretation

When the nightly workflow fails, the diagnosis depends on which assertion fired and what the rest of the platform looks like. The decision tree:

### 1. Cost cap exceeded

```
AssertionError: Estimated run cost $X.XXXX exceeded cap $0.50
```

This means a fixture or prompt change inflated token usage. Investigate:

- Has `_PER_FIXTURE_MAX_TOKENS` been raised in the test?
- Has the fixture set grown beyond five entries?
- Has the prompt template (`Tier3LLMResolver._build_prompt`) gotten significantly longer?

**Action:** the cost cap is intentional. Either revert the inflating change or open a PR raising the cap with explicit cost-impact justification.

### 2. Resolution rate below 60%

```
AssertionError: Resolution rate XX% is below 60% threshold
```

Three plausible root causes -- diagnose by cross-referencing other signals:

| Symptom | Likely cause | Action |
| --- | --- | --- |
| All five fixtures returned `unverified`; the prompt template was edited recently | **Prompt drift**: the new prompt no longer elicits valid JSON from the model. | Compare the new prompt against `git log -p src/services/graph/symbol_resolver_tier3.py`. Roll back or fix the prompt. Re-record the calibration test recordings (#118 REGENERATING.md) once the prompt is stable. |
| Fixtures partially resolved, but the same fixtures had been resolving cleanly historically; nothing in the resolver code has changed | **Model drift / new snapshot**: AWS rolled out a new Claude version that interprets the prompt differently. | Check Bedrock model availability (`aws bedrock list-foundation-models`) for the model ID currently configured. Pin to the prior snapshot if possible, or update the prompt to match the new model's behaviour. |
| The fixtures look stale or unrealistic compared to actual production call sites | **Fixture rot**: the synthetic fixtures no longer reflect what the resolver sees in real ingestion runs. | Replace one or two fixtures with patterns drawn from a recent customer ingestion. Update the runbook with the rationale. |
| Bedrock invocation errors visible in workflow logs (5xx, throttling, timeouts) | **Bedrock outage / throttle**: external to the resolver. | Check the AWS Health Dashboard for us-east-1 Bedrock status. Re-run the workflow once the platform is healthy; do not patch the test based on a transient outage. |

### 3. Module-level skip fired ("AWS_BEDROCK_AVAILABLE not set")

The test was collected but did not run. This is expected behaviour anywhere `AWS_BEDROCK_AVAILABLE` is unset (PR pipeline, stripped CI images). The nightly workflow sets it in the env block; if the nightly skip fires, the workflow's env config has drifted -- inspect `.github/workflows/nightly-live-llm.yml`.

## Operational Notes

### Re-running the smoke manually

```bash
gh workflow run nightly-live-llm.yml --repo aenealabs/aura
```

Or set up local credentials and run directly:

```bash
AWS_BEDROCK_AVAILABLE=1 \
AWS_PROFILE=<bedrock-enabled-profile> \
pytest tests/live/ -m live_llm --no-cov -v
```

### Disabling the workflow

If the workflow is generating false alarms during a known Bedrock incident:

```bash
gh workflow disable nightly-live-llm.yml --repo aenealabs/aura
```

Re-enable with `gh workflow enable`. Always pair a disable with an issue comment explaining why and an expected re-enable date.

### Cost accounting

Each nightly run is bounded at USD 0.50 (in-test assertion). Annual cost ceiling: 365 × USD 0.50 = USD 182.50 worst case. Realistic usage at the current fixture sizing is closer to USD 5-10 per year. If the cost ever materially exceeds projections, investigate -- the resolver may be retrying or the fixture set may have grown.

### When to re-record the mocked tests

The mocked Tier 3 tests (`tests/integration/graph/test_confidence_calibration.py` per #118) replay synthetic Bedrock responses. The live-LLM smoke is the *only* test that exercises real model behaviour. When the live smoke surfaces a prompt drift or model drift:

1. Confirm the change is intentional (or is forced on us by a model snapshot we cannot pin).
2. Update the prompt or fixtures.
3. Re-record the mocked calibration recordings so the PR-pipeline test reflects the new model behaviour.

This keeps the two test layers aligned: the live smoke catches unknown drift; the mocked test catches known regressions per PR.

## References

- Test: `tests/live/test_tier3_live_llm.py`
- Workflow: `.github/workflows/nightly-live-llm.yml`
- Resolver: `src/services/graph/symbol_resolver_tier3.py`
- Issue: [#120](https://github.com/aenealabs/aura/issues/120)
- Calibration test (mocked): `tests/integration/graph/test_confidence_calibration.py` (#118)
