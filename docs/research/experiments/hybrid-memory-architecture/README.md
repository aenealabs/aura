# Hybrid Memory Architecture Experiment

**Experiment ID:** HMA
**Status:** Analysis Complete, Implementation Pending
**Related ADR:** ADR-024 (Deployed - 237 tests, 5 phases complete)

---

## Overview

This experiment analyzes and documents the hybrid memory architecture for Project Aura's neural memory system, combining Inferentia2 for inference and GPU for test-time training.

## Documents

| Document | Purpose |
|----------|---------|
| `PERFORMANCE_ANALYSIS.md` | Theoretical performance comparison: Hybrid vs GPU-Only |
| `RESOURCE_SCALING_GUIDE.md` | Development to production resource mapping |
| `ENTERPRISE_TIER_CONFIG.md` | Configuration guide for Small/Medium/Large enterprises |

## Key Findings

1. **Hybrid wins at scale:** +67% throughput, -62% p99 latency, -36% cost at 500M req/mo
2. **Configuration-driven scaling:** Same codebase from dev ($70/mo) to enterprise ($40K/mo)
3. **Hardware abstraction:** CPU/GPU/Inferentia backends behind common interface
4. **Enterprise tiers:** Small ($5K), Medium ($15K), Large ($40K) with self-service scaling

## Architecture Decision

```
Development:     CPU (t3) ────────────────────────────► Same Code
                     │
Staging:         Inferentia2 (inf2) + GPU (g5) ───────► Same Code
                     │
Production:      Inferentia2 cluster + GPU fleet ─────► Same Code
```

## Next Steps

1. [ ] Implement `DeepMLPMemory` module with CPU backend
2. [ ] Add hardware abstraction layer (`MemoryBackend` interface)
3. [ ] Create Neuron SDK compilation pipeline for Inferentia2
4. [ ] Benchmark CPU vs GPU vs Inferentia2 performance
5. [ ] Integrate with existing `CognitiveMemoryService`

## References

- ADR-024: `../../proposals/ADR-024-TITAN-NEURAL-MEMORY.md`
- Titans Paper: arXiv:2501.00663
- MIRAS Paper: arXiv:2504.13173
- AWS Inferentia2 Documentation

---

*Last Updated: December 6, 2025*
