# Semantic Guardrails Latency Benchmark (ADR-065)

Measured latency of the deterministic layers of the semantic guardrails engine
(`src/services/semantic_guardrails/`) against the per-layer targets in
`docs/architecture-decisions/ADR-065-semantic-guardrails-engine.md`.

## Scope

| Layer | Measured here? | Notes |
|---|---|---|
| L1 Normalization | Yes | `TextNormalizer.normalize` |
| L2 Pattern matching | Yes | `PatternMatcher.match` (on normalized text) |
| L3 Embedding k-NN (OpenSearch) | **No** | Needs a live OpenSearch domain and embedding model |
| L4 LLM judge (Bedrock Haiku) | **No** | Needs live Bedrock |
| L5 Multi-turn tracking | Yes | `MultiTurnTracker.record_turn`, in-memory mode (no DynamoDB) |
| L6 Decision engine | Yes | `DecisionEngine.assess` with precomputed upstream results |
| End-to-end, L3/L4 skipped | Yes | `SemanticGuardrailsEngine.assess_threat(skip_embedding=True, skip_intent=True)` |

**Real L3 and L4 latency is unmeasured.** It can only be obtained in a live AWS
environment. The ADR targets for L3 (50 ms), L4 (150 ms) and the ~240 ms total
therefore remain unverified. Nothing in this document estimates or simulates
network or model time.

## Method

- Script: `scripts/benchmark_semantic_guardrails.py`. Timer: `time.perf_counter_ns`.
- 200 warmup calls, then 2000 timed iterations per layer per input class.
  Percentiles use nearest-rank on the sorted samples. With n=2000, p99 is the
  20th-largest sample and `max` is a single observation (sensitive to
  scheduler/GC noise).
- Every component runs in its built-in in-memory/mock mode. No network calls.
- L5 uses a fresh session id per call (first-turn path), plus one row with a
  single long-lived session. L6 times only `DecisionEngine.assess` using
  L1/L2/L5 results computed once beforehand.
- The end-to-end path includes L1, L2, L5, L6, plus the engine's metrics
  recording (mock CloudWatch mode, no flush) and logging. Log output was
  redirected to a file/pipe, not a terminal.
- Corpus (static, in the script):

| Class | Chars | L2 verdict | Fast-exit |
|---|---|---|---|
| benign_short | 50 | SAFE | no |
| benign_2KB | 2048 | SAFE | no |
| benign_20KB_code | 20480 | SAFE | no |
| adv_injection_phrase ("Ignore all previous instructions...") | 63 | CRITICAL | yes |
| adv_homoglyph (Cyrillic o/e substitutions) | 63 | CRITICAL | yes |
| adv_zero_width (U+200B inside words) | 67 | CRITICAL | yes |
| adv_base64 (injection phrase base64-wrapped) | 103 | CRITICAL | yes |
| adv_injection_in_2KB (phrase embedded in benign text) | 2063 | CRITICAL | yes |

All adversarial inputs were caught by L1+L2 and took the fast-exit path, so
their end-to-end numbers do not include L5 or the full L6 path for non-fast-exit
cases (the engine still records the session turn and runs the decision step).

## Environment

| Item | Value |
|---|---|
| CPU | Apple M5, 10 cores (`sysctl machdep.cpu.brand_string`, `hw.ncpu`) |
| OS | macOS-27.0.1-arm64 |
| Python | 3.12.3 |
| Git commit | 712bebf (measured before the surrounding branch changes were committed) |
| Date (UTC) | 2026-10-15 02:07 |
| Load | Developer laptop, not isolated; other processes were running |

## Results (milliseconds)

### L1 Normalization (target 5 ms)

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 0.0041 | 0.0043 | 0.0052 | 0.0226 |
| benign_2KB | 0.0881 | 0.0941 | 0.1047 | 0.1413 |
| benign_20KB_code | 0.7871 | 0.8427 | 0.9757 | 2.1042 |
| adv_injection_phrase | 0.0046 | 0.0048 | 0.0058 | 0.0246 |
| adv_homoglyph | 0.0077 | 0.0081 | 0.0100 | 0.1020 |
| adv_zero_width | 0.0071 | 0.0073 | 0.0102 | 0.0202 |
| adv_base64 | 0.0084 | 0.0086 | 0.0105 | 0.0305 |
| adv_injection_in_2KB | 0.0909 | 0.2220 | 0.3233 | 12.3555 |

### L2 Pattern matching (target 10 ms)

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 0.0375 | 0.0411 | 0.0470 | 0.1507 |
| benign_2KB | 1.6385 | 1.7568 | 1.8151 | 4.0598 |
| benign_20KB_code | 14.6596 | 15.7684 | 18.4608 | 40.5046 |
| adv_injection_phrase | 0.0357 | 0.0400 | 0.0437 | 0.0650 |
| adv_homoglyph | 0.0356 | 0.0430 | 0.0763 | 0.1760 |
| adv_zero_width | 0.0355 | 0.0401 | 0.0453 | 0.0730 |
| adv_base64 | 0.0462 | 0.0501 | 0.0545 | 0.0695 |
| adv_injection_in_2KB | 1.1137 | 1.3712 | 2.0030 | 4.6405 |

### L5 Multi-turn tracking, in-memory (target 20 ms)

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 0.0031 | 0.0035 | 0.0068 | 0.0133 |
| benign_2KB | 0.0032 | 0.0036 | 0.0071 | 0.0295 |
| benign_20KB_code | 0.0033 | 0.0037 | 0.0049 | 0.1979 |
| adv_injection_phrase | 0.0032 | 0.0038 | 0.0045 | 0.1624 |
| adv_homoglyph | 0.0034 | 0.0040 | 0.0052 | 0.0783 |
| adv_zero_width | 0.0037 | 0.0041 | 0.0051 | 0.0196 |
| adv_base64 | 0.0044 | 0.0047 | 0.0052 | 0.0063 |
| adv_injection_in_2KB | 0.0048 | 0.0053 | 0.0060 | 0.0090 |
| same session, repeated turns | 0.0112 | 0.0129 | 0.0141 | 0.0479 |

L5 time is independent of input text (it takes a score, not text).

### L6 Decision engine (target 5 ms)

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 0.0030 | 0.0031 | 0.0037 | 0.0220 |
| benign_2KB | 0.0036 | 0.0039 | 0.0045 | 0.0363 |
| benign_20KB_code | 0.0096 | 0.0098 | 0.0119 | 0.0642 |
| adv_injection_phrase | 0.0080 | 0.0088 | 0.0127 | 0.0488 |
| adv_homoglyph | 0.0080 | 0.0093 | 0.0128 | 0.0350 |
| adv_zero_width | 0.0079 | 0.0085 | 0.0100 | 0.0266 |
| adv_base64 | 0.0081 | 0.0086 | 0.0089 | 0.0365 |
| adv_injection_in_2KB | 0.0088 | 0.0092 | 0.0102 | 0.0461 |

### End-to-end deterministic path (L3/L4 skipped; L1+L2+L5+L6+metrics)

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 0.0568 | 0.0630 | 0.0722 | 0.2122 |
| benign_2KB | 1.7359 | 1.8586 | 1.9043 | 3.8941 |
| benign_20KB_code | 15.3549 | 16.4328 | 16.7928 | 24.7117 |
| adv_injection_phrase | 0.0717 | 0.0817 | 0.1003 | 0.2406 |
| adv_homoglyph | 0.0747 | 0.0847 | 0.0994 | 0.1865 |
| adv_zero_width | 0.0745 | 0.0820 | 0.0914 | 0.1842 |
| adv_base64 | 0.0892 | 0.0981 | 0.1105 | 0.2108 |
| adv_injection_in_2KB | 1.2650 | 1.7003 | 2.9628 | 11.3897 |

### Orchestration overhead with built-in mock L3/L4 (NOT real L3/L4 latency)

Full `assess_threat` with the engine's default mock embedding detector and mock
intent classifier (in-process hash embedding + cosine over a small mock corpus,
and a keyword-based mock classifier), dispatched through the engine's
`ThreadPoolExecutor`. This is overhead **excluding network and model time**; it
says nothing about OpenSearch or Bedrock latency. Adversarial inputs fast-exit
before L3/L4, so they match the deterministic numbers.

| input | p50 | p95 | p99 | max |
|---|---|---|---|---|
| benign_short | 1.3947 | 1.4750 | 1.5981 | 3.2536 |
| benign_2KB | 3.1309 | 3.3585 | 3.8993 | 5.7181 |
| benign_20KB_code | 17.0733 | 19.2587 | 23.3160 | 38.6368 |
| adv_injection_phrase | 0.0720 | 0.0784 | 0.0843 | 0.1358 |
| adv_homoglyph | 0.0761 | 0.0843 | 0.0985 | 0.2849 |
| adv_zero_width | 0.0798 | 0.0873 | 0.0938 | 0.1439 |
| adv_base64 | 0.0905 | 0.1020 | 0.1099 | 0.1878 |
| adv_injection_in_2KB | 1.2425 | 1.3335 | 1.4424 | 3.2037 |

## Comparison to ADR-065 targets

Worst-case p95 across all input classes, per layer:

| Layer | ADR target | Worst p95 (input) | Worst-case p50 | Verdict |
|---|---|---|---|---|
| L1 Normalization | 5 ms | 0.8427 ms (benign_20KB_code) | 0.7871 ms | Met |
| L2 Pattern matching | 10 ms | **15.7684 ms** (benign_20KB_code) | 14.6596 ms | **Not met for 20KB inputs**; met for short and 2KB inputs (p95 1.7568 ms at 2KB) |
| L3 Embedding | 50 ms | not measured | not measured | Unverified |
| L4 LLM judge | 150 ms | not measured | not measured | Unverified |
| L5 Multi-turn | 20 ms | 0.0129 ms (in-memory) | 0.0112 ms | Met for in-memory only; the DynamoDB-backed path is unmeasured |
| L6 Decision | 5 ms | 0.0098 ms (benign_20KB_code) | 0.0096 ms | Met |
| Deterministic E2E | n/a (no ADR target for this subset; L1+L2+L5+L6 budget = 40 ms) | 16.4328 ms (benign_20KB_code) | 15.3549 ms | Within the 40 ms sum of those four targets, but exceeds the 15 ms fast-path figure in `assess_fast_path` ("<15ms") for 20KB inputs |

Total-engine P95 < 300 ms and the ~240 ms total are **not assessable**: they
depend on L3 and L4, which were not measured. The deterministic path consumes
at most 16.4328 ms p95 (20KB benign), leaving 283.5672 ms of the 300 ms P95
budget for L3+L4 plus network, which is a bound on what the unmeasured layers
may cost, not a measurement of them.

Observations:

- L2 dominates the deterministic path for large benign inputs (about 14.7 of
  15.4 ms p50 at 20KB): cost scales with input length because every regex runs
  over the full text. Short prompts (50 chars) complete the whole deterministic
  path in 0.0630 ms p95.
- Adversarial inputs are cheap because they are short and exit early; the
  injection-in-2KB case is bounded by normalization/pattern scan over 2KB
  (p95 1.7003 ms end-to-end).
- L1 decodes base64 and homoglyph/zero-width inputs in under 0.01 ms p95 at
  these sizes. Larger obfuscated payloads were not tested.

## Limitations

- L3 and L4 real latency is unmeasured (needs live AWS: OpenSearch k-NN,
  Bedrock). The mock-L3/L4 table is orchestration overhead only.
- L5 was measured against the in-memory store. Production uses DynamoDB, adding
  a network round trip (read plus write) that is not included.
- Single machine (Apple Silicon laptop), single process, no concurrent load, no
  contention on the shared thread pool. Production CPUs (EKS EC2) and request
  concurrency will differ. Results do not transfer directly.
- Max and p99 values are noisy at n=2000 on a non-isolated machine (for example
  the 12.3555 ms L1 max on adv_injection_in_2KB is a one-off outlier, not
  typical behavior).
- Small corpus (8 inputs, 3 benign sizes). Not a statistical sample of real
  traffic; pattern-match cost depends on input content as well as length.
- Metrics publishing ran in mock mode (buffered, never flushed), so CloudWatch
  flush cost is excluded.
- The 20KB benign input is Python-like code repeated; other content types may
  behave differently.

## Reproduction

```bash
python scripts/benchmark_semantic_guardrails.py --iterations 2000 --warmup 200 \
  --mock-l3-l4 --json /tmp/guardrails_bench.json > /tmp/guardrails_bench.log 2>&1
```

The engine logs one line per assessment, so the console output is large;
redirect it and render tables from the JSON, for example:

```bash
python - <<'PY'
import json, sys
sys.path.insert(0, "scripts")
import benchmark_semantic_guardrails as b
print(b.render(json.load(open("/tmp/guardrails_bench.json"))))
PY
```

Smoke test: `pytest tests/scripts/test_benchmark_semantic_guardrails.py`.
Runtime at 2000 iterations is a few minutes, dominated by the 20KB inputs.
