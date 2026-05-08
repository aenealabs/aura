# Regenerating Tier 3 Calibration Recordings

This directory holds the recorded Bedrock responses replayed by `tests/integration/graph/test_confidence_calibration.py` (issue #118). Replay-based testing means the test runs in CI without real Bedrock calls, but the recordings drift over time as prompts change, model snapshots roll out, or fixture intent shifts. This doc is the canonical procedure for refreshing `recordings.json`.

## When to re-record

Re-record when any of the following changes:

1. The Tier 3 prompt template (`Tier3LLMResolver._build_prompt`) is intentionally edited.
2. The set of calibration fixtures (`_build_unambiguous_fixtures` / `_build_ambiguous_fixtures` in the test file) is changed.
3. A new Bedrock model snapshot is rolled out and the team wants the calibration baseline to track the new model.
4. The `recordings.json` schema version (`_metadata.schema_version`) is incremented.

Do **not** re-record on incidental code changes. If the test is failing on `main` without one of the above triggers, treat it as a real signal — either a model has drifted or the prompt has been changed without matching recording updates.

## The current recordings are synthetic

The recordings shipped with #118 are **synthetic placeholders** chosen to validate the test infrastructure: 18/2 verified-vs-null on unambiguous fixtures and 6/14 verified-vs-null on ambiguous fixtures, producing a clear Mann-Whitney U separation. These synthetics do **not** reflect real Bedrock behavior and exist only so the test exercises the calibration logic end-to-end in CI.

The first real-Bedrock recording campaign should:

- Replace every entry in `recordings.json` with the actual response observed when running each fixture's prompt against Bedrock.
- Update `_metadata.distribution_intent` to describe the observed distribution (rather than the synthetic intent).
- Tighten or relax the `mannwhitneyu` and `median-separation` thresholds in the test if the real distribution is meaningfully different from the synthetic baseline.

## Re-recording procedure

Run from the project root with valid AWS credentials targeting an account that has Bedrock model access for the configured model (Claude Sonnet 4.6 / Haiku 4.5 per CLAUDE.md):

```bash
# 1. Confirm Bedrock access first; bail early if the credential
#    cannot invoke the model.
aws bedrock list-foundation-models --region us-east-1 \
    --query 'modelSummaries[?contains(modelId, `claude`)].modelId' \
    --output text

# 2. Run the recording script (to be authored alongside this doc
#    in the next pass). The script:
#      - imports the same fixture builders the test uses
#      - constructs the same prompts
#      - invokes Bedrock for each fixture
#      - writes the returned text into recordings.json keyed by
#        fixture_id
python -m scripts.calibration.record_tier3_responses \
    --output tests/fixtures/bedrock_recordings/calibration/recordings.json
```

The recording script does not yet exist; it is filed as a small follow-up task because authoring it requires Bedrock access during development. Until the script exists, recordings can be refreshed manually by:

1. Checking out the test file and running it under a debugger.
2. For each fixture, capturing the prompt as printed by the resolver.
3. Sending each prompt to Bedrock via the `bedrock-runtime` API.
4. Pasting the returned `body.content[0].text` into `recordings.json` against the matching `fixture_id`.

## Cost ceiling

Real-Bedrock recording costs roughly the same as a single Tier 3 ingestion of 40 prompts. Expect well under USD 1.00 per full recording run. If a re-recording campaign runs unexpectedly hot, check that no fixture has a prompt larger than the configured `max_tokens=256`.

## Validation

After updating recordings:

```bash
python -m pytest tests/integration/graph/test_confidence_calibration.py -v --no-cov
```

The test will:

- Verify every fixture has a recording (no missing keys).
- Verify there are no stale recordings (no extra keys).
- Run the resolver across all 40 fixtures.
- Assert MWU p-value < 0.01.
- Assert median score separation > 0.3.

If the assertions fail after re-recording, the model's behavior on this prompt set has actually changed; that is the signal the test exists to surface. Investigate (model snapshot? prompt edit? fixture rot?) and either tighten the prompt or update the thresholds.
