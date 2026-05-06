# Impact Assessment: Replacing RLM "100x" and JEPA "2.85x" with Measured Benchmarks

**Date:** 2026-05-06
**Driver:** 2026-05-06 codebase audit findings F1 (JEPA literal) and F2 (RLM unbenchmarked)
**Scope:** What changes — in code, docs, marketing, and risk posture — when the headline performance constants are replaced with numbers a benchmark harness produces.

---

## Current state

### JEPA (`src/services/jepa/embedding_predictor.py`)

`operations_saved = "2.85x"` is a **hardcoded string literal** at line 514 and re-emitted at lines 905, 929, and 1025. The value is set unconditionally whenever `task_type.is_non_generative` is True. Critically:

- The predictor (`_run_predictor`) does run a real transformer forward pass.
- The decoder (`_run_decoder`) is a stub: `_embeddings_to_text` returns `f"[decoded:{md5_hash[:8]}]"` (line 625). Real decoding would use vocabulary projection + beam search; today there's no vocabulary, no projection head, no decoded output.
- Predictor weights are randomly initialized; there is no training loop.
- The "savings" the literal claims is the *paper's* theoretical ratio of (predictor-only) to (predictor + decoder) FLOPs. With the current stub decoder the runtime ratio is meaningless.
- `tests/test_jepa_embedding_predictor.py:48` tests assert `result.operations_saved == "2.85x"` — tautological.

**Net:** the claim communicates a research result, not a measured property of this implementation.

### RLM (`src/services/rlm/recursive_context_engine.py`)

The "100x context scaling" claim lives in module docstrings (`__init__.py`, `recursive_context_engine.py:4,8`). It is **not** a runtime constant — there is no equivalent of JEPA's hardcoded `2.85x`. The runtime behaviour:

- `process` → `_process_recursive` decomposes prompts up to 10 levels deep.
- The LLM is asked to generate Python that calls `context_search`, `context_chunk`, `recursive_call`, `aggregate_results` helpers.
- The depth × per-level summarization ratio yields the effective context multiplier.
- Whether 100× actually obtains depends on (a) how aggressively each level summarises, (b) recursion depth permitted, and (c) whether the LLM-generated decomposition code is well-formed.

**Net:** the claim is research-grounded and architecturally plausible, but no published benchmark in the repo demonstrates it. Per the audit's `tests/benchmarks/test_jepa_efficiency.py` reference, there's no benchmarks directory.

---

## What real benchmarking requires

### JEPA benchmark harness

To produce honest numbers we'd need:

1. **A real decoder.** Either:
   - Wire a tied embedding/output projection (≈ 1 day of work) to make `_run_decoder` produce text against a small vocabulary, OR
   - Define "operations saved" as predictor-only FLOPs vs. predictor+decoder FLOPs, count them via tracing rather than running the decoder. The latter is cheaper and more defensible because the FLOP count of an untrained decoder equals that of a trained one.

2. **Latency micro-benchmark.** Measure end-to-end latency of `predict()` for non-generative vs. generative task types over N samples (≥ 1000) and emit median/p95/p99 numbers. This is what customers actually care about.

3. **Integration baseline.** Measure round-trip latency on the GraphRAG retrieval path with and without the JEPA fast path engaged. This tells us the *system-level* lift, which is usually 30–60% of the unit-level lift after queueing and network costs.

### RLM benchmark harness

Different shape because the relevant metric isn't FLOPs:

1. **Long-context QA datasets.** Standard public sets used in the literature: NIAH (Needle In A Haystack), RULER, LongBench, Loong. Pick two; report recall@1 across context lengths {16K, 64K, 256K, 1M, 4M tokens}.

2. **Effective context length.** Define as the largest context size at which recall@1 stays ≥ 0.9. The "100× scaling" claim becomes verifiable: if RLM achieves effective length 4M with a 32K-context base model, that's 125×; if it achieves 1M, that's ~30×.

3. **Decomposition quality gate.** Track what fraction of LLM-generated decomposition code parses, type-checks, and executes without error. Below ~95% the recursive path's effective gain collapses.

---

## Expected number ranges (calibrated)

### JEPA

| Metric | Pessimistic | Realistic | Optimistic |
|---|---|---|---|
| Operation count saved (FLOPs ratio, predictor-only vs. full) | 1.5× | 2.0–2.8× | 3.5× |
| End-to-end latency win on a real workload | 1.05× | 1.3–1.6× | 2.0× |
| Cache-hit rate increase from predictor routing | 0% | 5–15% | 25% |

The 2.85× FLOP claim is roughly correct for the architecture in the source paper; it's the **end-to-end** number that tends to disappoint and is what we should publish.

### RLM

| Metric | Pessimistic | Realistic | Optimistic |
|---|---|---|---|
| Effective context length (32K base) | 100K (3×) | 500K (15×) | 4M (125×) |
| NIAH recall@1 at 1M tokens | 0.4 | 0.7–0.85 | 0.95 |
| Decomposition success rate | 75% | 88–94% | 99% |

The 100× claim is **achievable** on cooperative datasets (NIAH-style) but fragile on adversarial ones. Honest reporting requires per-dataset numbers, not a single multiplier.

---

## Engineering effort

| Work | Size | Justification |
|---|---|---|
| JEPA FLOP counter + latency micro-benchmark | **S** (3–5 days) | Tracing FLOPs is straightforward; latency microbench is a `pytest-benchmark` harness. |
| JEPA decoder fix (real projection head) | **M** (1–2 weeks) | Optional, but strengthens the runtime savings claim. |
| RLM eval harness (NIAH + RULER subset) | **M** (1–2 weeks) | Both datasets have public loaders; need an eval orchestrator + result aggregation. Bedrock cost ~$200–500 per full sweep. |
| RLM decomposition success monitor | **S** (2–3 days) | Counter + log line + dashboard widget. |
| Replace hardcoded literals with measured values | **S** (1 day) | Mechanical once the harness produces numbers. |
| Update docs / marketing pages | **S** (1 day) | `docs/agentic-capabilities.html`, `docs/architecture-decision-records.html`, ADR-051, README, project status. |

**Total realistic budget: 4–6 weeks of focused engineering for credible, customer-defensible numbers.** A "make the audit go away" pass that just removes the literals and replaces them with FLOP counts is **1 week**.

---

## Risks

1. **Real numbers underperform headline.** Most likely outcome on JEPA — the 2.85× FLOP figure stands but the system-level latency win is closer to 1.3–1.6×. Marketing has to acknowledge the difference between FLOP savings and wall-clock savings or accept questions during pilot.

2. **Real numbers depend on the base model.** RLM context scaling depends on the underlying LLM. Bigger frontier models reduce the relative win because their native context already covers more. Honest framing: "X× extension on top of any base model" is more durable than absolute multipliers.

3. **Adversarial datasets expose weaknesses.** NIAH is designed to be solvable by long-context models; it's a low bar. If we publish 100× on NIAH and a customer's evaluation uses adversarial multi-hop QA, the numbers will look 3–5× worse. **Recommendation: publish on at least two datasets with different difficulty profiles.**

4. **Customer audit risk.** A regulated customer who walks the test suite (per the audit's flag of `tests/benchmarks/test_jepa_efficiency.py` not existing) and finds the literal `"2.85x"` in a tautological assertion has a credibility-impacting finding. This is the strongest argument for fixing it before pilot.

---

## Documentation impact

When numbers replace literals, these surfaces change:

- `src/services/jepa/embedding_predictor.py:514, 905, 929, 1025` — replace literal with computed.
- `src/services/jepa/__init__.py:5,15` — module docstring.
- `src/services/rlm/__init__.py:5,8` and `recursive_context_engine.py:4,8` — module docstrings cite multipliers without source benchmarks.
- `docs/agentic-capabilities.html:1027,1030,1273` — public-facing cards.
- `docs/architecture-decision-records.html:811,814,1770,1771` — ADR-051 summary cards.
- `docs/PROJECT_STATUS.md:69` — "100x context window expansion".
- `CLAUDE.md` — references in the ADR-051 line.
- `docs/architecture-decisions/ADR-051-recursive-context-and-embedding-prediction.md` — the ADR itself.

The cleanest replacement format is: **"`X×` (measured on dataset D, base model M, date)"** rather than a bare number. This puts the result in context and inoculates against future model changes.

---

## Recommended sequencing

1. **Week 1**: drop the literal, switch to FLOP-counted "operations saved" for JEPA (no marketing change yet).
2. **Week 2**: stand up a `tests/benchmarks/` directory with NIAH-1M and a synthetic JEPA latency suite. Run them as a nightly job.
3. **Week 3**: publish first nightly numbers internally; calibrate language for external claims.
4. **Week 4**: update docs, ADR-051, and the public marketing pages with the new "measured" framing.

If only one week is available, do step 1 alone — it removes the literal, which is the strongest customer-audit risk, and replaces it with a defensible FLOP ratio. Marketing claims can stay until step 4, but should be moved out of code comments.
