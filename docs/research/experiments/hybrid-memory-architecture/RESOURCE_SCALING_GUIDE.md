# Resource Scaling Guide: Development to Production

**Document ID:** HMA-002
**Date:** December 6, 2025
**Philosophy:** Build for the ceiling, deploy on the floor

---

## Overview

Project Aura implements a **configuration-driven scaling architecture** where the same services and code paths are used from development through enterprise production. The only differences are resource allocations controlled via environment configuration.

```
┌─────────────────────────────────────────────────────────────────┐
│                    SCALING PHILOSOPHY                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Development          Growth              Enterprise             │
│  ───────────          ──────              ──────────             │
│  Same architecture    Same architecture   Same architecture      │
│  Minimal resources    Moderate resources  Full resources         │
│  Single instance      Multi-instance      Multi-region           │
│  ~$200/month          ~$2,000/month       ~$15,000/month         │
│                                                                  │
│  ┌─────────┐          ┌─────────┐         ┌─────────┐           │
│  │ ░░░░░░░ │    →     │ ▓▓▓░░░░ │    →    │ ████████ │           │
│  │ ░░░░░░░ │          │ ▓▓▓░░░░ │         │ ████████ │           │
│  │ ░░░░░░░ │          │ ▓▓▓░░░░ │         │ ████████ │           │
│  └─────────┘          └─────────┘         └─────────┘           │
│   10% capacity         40% capacity        100% capacity         │
│                                                                  │
│  Code changes: ZERO                                              │
│  Config changes: Environment variables + instance sizing         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1. Resource Mapping by Environment

### 1.1 Memory Service (Neural Memory)

| Component | Development | Staging | Production (S) | Production (M) | Production (L) |
|-----------|-------------|---------|----------------|----------------|----------------|
| **Retrieval Instances** | | | | | |
| Instance Type | t3.medium (CPU) | inf2.xlarge | inf2.xlarge | inf2.8xlarge | inf2.8xlarge |
| Count | 1 | 1 | 2 | 2 | 4 |
| Throughput | 2K req/s | 25K req/s | 50K req/s | 100K req/s | 200K req/s |
| **TTT Instances** | | | | | |
| Instance Type | t3.large (CPU) | g5.xlarge | g5.xlarge | g5.xlarge | g5.2xlarge |
| Count | 1 | 0-1 | 0-1 | 0-2 | 0-3 |
| Throughput | 50 upd/s | 500 upd/s | 500 upd/s | 1K upd/s | 1.5K upd/s |
| **Monthly Cost** | ~$70 | ~$600 | ~$1,400 | ~$3,000 | ~$5,500 |

**Development Note:** CPU instances (t3.medium/large) for development allow:
- No Neuron SDK compilation required
- Standard PyTorch debugging
- Same code path (abstracted via interface)
- Low cost for iteration

### 1.2 Agent Orchestration (EKS)

| Component | Development | Staging | Production (S) | Production (M) | Production (L) |
|-----------|-------------|---------|----------------|----------------|----------------|
| **Node Group** | | | | | |
| Instance Type | t3.medium | t3.large | m6i.large | m6i.xlarge | m6i.2xlarge |
| Count | 2 | 2 | 3 | 5 | 10 |
| vCPUs Total | 4 | 4 | 6 | 20 | 80 |
| Memory Total | 8 GB | 16 GB | 24 GB | 80 GB | 320 GB |
| **Concurrent Orchestrations** | 5 | 20 | 50 | 150 | 500 |
| **Monthly Cost** | ~$60 | ~$120 | ~$220 | ~$550 | ~$1,800 |

### 1.3 Data Layer

| Component | Development | Staging | Production (S) | Production (M) | Production (L) |
|-----------|-------------|---------|----------------|----------------|----------------|
| **Neptune** | | | | | |
| Instance Type | db.t3.medium | db.t3.medium | db.r5.large | db.r5.xlarge | db.r5.2xlarge |
| Read Replicas | 0 | 0 | 1 | 2 | 3 |
| **OpenSearch** | | | | | |
| Instance Type | t3.small.search | t3.medium.search | m6g.large.search | m6g.xlarge.search | m6g.2xlarge.search |
| Data Nodes | 1 | 2 | 2 | 3 | 5 |
| **DynamoDB** | | | | | |
| Capacity Mode | On-Demand | On-Demand | Provisioned | Provisioned | Provisioned |
| RCU | - | - | 100 | 500 | 2000 |
| WCU | - | - | 50 | 250 | 1000 |
| **Monthly Cost** | ~$150 | ~$300 | ~$800 | ~$2,000 | ~$5,000 |

### 1.4 LLM Integration (Bedrock)

| Component | Development | Staging | Production (S) | Production (M) | Production (L) |
|-----------|-------------|---------|----------------|----------------|----------------|
| **Model Tier Distribution** | | | | | |
| Fast (Haiku) | 60% | 50% | 40% | 40% | 40% |
| Accurate (Sonnet) | 35% | 45% | 55% | 55% | 55% |
| Maximum (Opus) | 5% | 5% | 5% | 5% | 5% |
| **Rate Limits** | | | | | |
| Requests/min | 100 | 500 | 2,000 | 5,000 | 10,000 |
| Tokens/day | 100K | 1M | 10M | 50M | 200M |
| **Monthly Cost** | ~$50 | ~$500 | ~$2,000 | ~$8,000 | ~$25,000 |

---

## 2. Total Cost Summary by Environment

| Environment | Memory | Compute | Data | LLM | Other | Total/Month |
|-------------|--------|---------|------|-----|-------|-------------|
| **Development** | $70 | $60 | $150 | $50 | $50 | **~$380** |
| **Staging** | $600 | $120 | $300 | $500 | $100 | **~$1,620** |
| **Production (S)** | $1,400 | $220 | $800 | $2,000 | $200 | **~$4,620** |
| **Production (M)** | $3,000 | $550 | $2,000 | $8,000 | $400 | **~$13,950** |
| **Production (L)** | $5,500 | $1,800 | $5,000 | $25,000 | $800 | **~$38,100** |

---

## 3. Configuration Schema

### 3.1 Environment Configuration

```yaml
# deploy/config/environments/development.yaml
environment: development
tier: dev

memory_service:
  retrieval:
    instance_type: t3.medium        # CPU for dev (no Neuron SDK needed)
    instance_count: 1
    use_inferentia: false           # Toggle for Inferentia2
  ttt:
    instance_type: t3.large         # CPU for dev (no CUDA needed)
    instance_count: 1
    min_instances: 1                # Always running in dev
    max_instances: 1
    use_gpu: false                  # Toggle for GPU

  model:
    dimensions: 512
    depth: 3
    hidden_multiplier: 4
    checkpoint_interval_hours: 24

  miras:
    attentional_bias: huber
    retention_gate: adaptive
    retention_strength: 0.01

  surprise:
    memorization_threshold: 0.7
    momentum: 0.9

compute:
  eks:
    node_instance_type: t3.medium
    min_nodes: 2
    max_nodes: 2

data:
  neptune:
    instance_type: db.t3.medium
    read_replicas: 0
  opensearch:
    instance_type: t3.small.search
    data_nodes: 1
  dynamodb:
    capacity_mode: on-demand

llm:
  rate_limits:
    requests_per_minute: 100
    tokens_per_day: 100000
  model_distribution:
    fast: 0.60
    accurate: 0.35
    maximum: 0.05
  budget:
    daily_limit_usd: 5
    monthly_limit_usd: 100
```

```yaml
# deploy/config/environments/production-large.yaml
environment: production
tier: large

memory_service:
  retrieval:
    instance_type: inf2.8xlarge     # Inferentia2 for production
    instance_count: 4
    use_inferentia: true
  ttt:
    instance_type: g5.2xlarge       # GPU for TTT
    instance_count: 0               # Scale to zero base
    min_instances: 0
    max_instances: 3
    use_gpu: true
    scaling:
      target_queue_depth: 100
      scale_up_cooldown: 60
      scale_down_cooldown: 300

  model:
    dimensions: 512
    depth: 3
    hidden_multiplier: 4
    checkpoint_interval_hours: 1

  miras:
    attentional_bias: huber
    retention_gate: adaptive
    retention_strength: 0.01

  surprise:
    memorization_threshold: 0.7
    momentum: 0.9

compute:
  eks:
    node_instance_type: m6i.2xlarge
    min_nodes: 5
    max_nodes: 20

data:
  neptune:
    instance_type: db.r5.2xlarge
    read_replicas: 3
  opensearch:
    instance_type: m6g.2xlarge.search
    data_nodes: 5
  dynamodb:
    capacity_mode: provisioned
    rcu: 2000
    wcu: 1000

llm:
  rate_limits:
    requests_per_minute: 10000
    tokens_per_day: 200000000
  model_distribution:
    fast: 0.40
    accurate: 0.55
    maximum: 0.05
  budget:
    daily_limit_usd: 1000
    monthly_limit_usd: 30000
```

### 3.2 Abstraction Layer

```python
# src/config/memory_service_config.py
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import os

class AcceleratorType(Enum):
    CPU = "cpu"
    GPU = "gpu"
    INFERENTIA = "inferentia"

@dataclass
class MemoryServiceConfig:
    """Configuration for neural memory service, environment-aware."""

    # Retrieval configuration
    retrieval_instance_type: str
    retrieval_instance_count: int
    retrieval_accelerator: AcceleratorType

    # TTT configuration
    ttt_instance_type: str
    ttt_min_instances: int
    ttt_max_instances: int
    ttt_accelerator: AcceleratorType

    # Model configuration
    model_dimensions: int = 512
    model_depth: int = 3
    hidden_multiplier: int = 4

    # MIRAS configuration
    attentional_bias: str = "huber"
    retention_gate: str = "adaptive"
    retention_strength: float = 0.01

    # Surprise configuration
    memorization_threshold: float = 0.7
    momentum: float = 0.9

    @classmethod
    def from_environment(cls) -> "MemoryServiceConfig":
        """Load configuration from environment variables."""
        env = os.getenv("AURA_ENVIRONMENT", "development")

        if env == "development":
            return cls(
                retrieval_instance_type="t3.medium",
                retrieval_instance_count=1,
                retrieval_accelerator=AcceleratorType.CPU,
                ttt_instance_type="t3.large",
                ttt_min_instances=1,
                ttt_max_instances=1,
                ttt_accelerator=AcceleratorType.CPU,
            )
        elif env == "production-large":
            return cls(
                retrieval_instance_type="inf2.8xlarge",
                retrieval_instance_count=4,
                retrieval_accelerator=AcceleratorType.INFERENTIA,
                ttt_instance_type="g5.2xlarge",
                ttt_min_instances=0,
                ttt_max_instances=3,
                ttt_accelerator=AcceleratorType.GPU,
            )
        # ... other environments

    def get_retrieval_backend(self):
        """Get appropriate backend based on accelerator type."""
        if self.retrieval_accelerator == AcceleratorType.CPU:
            from .backends.cpu_memory import CPUMemoryBackend
            return CPUMemoryBackend(self)
        elif self.retrieval_accelerator == AcceleratorType.INFERENTIA:
            from .backends.inferentia_memory import InferentiaMemoryBackend
            return InferentiaMemoryBackend(self)
        elif self.retrieval_accelerator == AcceleratorType.GPU:
            from .backends.gpu_memory import GPUMemoryBackend
            return GPUMemoryBackend(self)
```

---

## 4. Hardware Abstraction

### 4.1 Memory Backend Interface

```python
# src/services/memory_backends/base.py
from abc import ABC, abstractmethod
from typing import Any
import torch

class MemoryBackend(ABC):
    """Abstract base class for neural memory backends."""

    @abstractmethod
    async def load_model(self, checkpoint_path: str) -> None:
        """Load model weights from checkpoint."""
        pass

    @abstractmethod
    async def retrieve(self, query: torch.Tensor) -> torch.Tensor:
        """Forward pass for memory retrieval."""
        pass

    @abstractmethod
    async def compute_surprise(self, input: torch.Tensor) -> float:
        """Compute gradient-based surprise score."""
        pass

    @abstractmethod
    async def update(self, key: torch.Tensor, value: torch.Tensor) -> None:
        """Test-time training update."""
        pass

    @abstractmethod
    async def save_checkpoint(self, path: str) -> None:
        """Save model weights to checkpoint."""
        pass
```

### 4.2 CPU Backend (Development)

```python
# src/services/memory_backends/cpu_memory.py
import torch
from .base import MemoryBackend

class CPUMemoryBackend(MemoryBackend):
    """CPU-based memory backend for development."""

    def __init__(self, config):
        self.config = config
        self.device = torch.device("cpu")
        self.model = self._build_model()

    def _build_model(self):
        """Build DeepMLPMemory on CPU."""
        from ..models.deep_mlp_memory import DeepMLPMemory
        model = DeepMLPMemory(
            dim=self.config.model_dimensions,
            depth=self.config.model_depth,
            hidden_mult=self.config.hidden_multiplier
        )
        return model.to(self.device)

    async def retrieve(self, query: torch.Tensor) -> torch.Tensor:
        query = query.to(self.device)
        with torch.no_grad():
            return self.model(query)

    async def compute_surprise(self, input: torch.Tensor) -> float:
        input = input.to(self.device).requires_grad_(True)
        output = self.model(input)
        loss = output.sum()  # Simplified loss
        loss.backward()

        grad_norm = sum(
            p.grad.norm().item()
            for p in self.model.parameters()
            if p.grad is not None
        )
        return grad_norm

    async def update(self, key: torch.Tensor, value: torch.Tensor) -> None:
        # TTT update logic
        key, value = key.to(self.device), value.to(self.device)
        # ... training step
```

### 4.3 Inferentia Backend (Production Retrieval)

```python
# src/services/memory_backends/inferentia_memory.py
import torch
from .base import MemoryBackend

class InferentiaMemoryBackend(MemoryBackend):
    """Inferentia2-based memory backend for production retrieval."""

    def __init__(self, config):
        self.config = config
        self._load_neuron_model()

    def _load_neuron_model(self):
        """Load Neuron-compiled model."""
        import torch_neuronx

        # Load pre-compiled model
        self.model = torch.jit.load(
            f"models/memory_neuron_{self.config.model_dimensions}.pt"
        )

    async def retrieve(self, query: torch.Tensor) -> torch.Tensor:
        """Optimized forward pass on NeuronCore."""
        # Neuron handles device placement
        return self.model(query)

    async def compute_surprise(self, input: torch.Tensor) -> float:
        """Surprise computation on Inferentia (limited gradient support)."""
        # Neuron SDK supports inference gradients
        # For full TTT, offload to GPU backend
        raise NotImplementedError(
            "Full surprise computation requires GPU. "
            "Use GPUMemoryBackend for TTT operations."
        )

    async def update(self, key: torch.Tensor, value: torch.Tensor) -> None:
        """TTT not supported on Inferentia - delegate to GPU."""
        raise NotImplementedError(
            "TTT updates require GPU. Route to GPUMemoryBackend."
        )
```

### 4.4 GPU Backend (Production TTT)

```python
# src/services/memory_backends/gpu_memory.py
import torch
from .base import MemoryBackend

class GPUMemoryBackend(MemoryBackend):
    """GPU-based memory backend for TTT operations."""

    def __init__(self, config):
        self.config = config
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._build_model()
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=0.001
        )

    def _build_model(self):
        from ..models.deep_mlp_memory import DeepMLPMemory
        model = DeepMLPMemory(
            dim=self.config.model_dimensions,
            depth=self.config.model_depth,
            hidden_mult=self.config.hidden_multiplier
        )
        return model.to(self.device)

    async def compute_surprise(self, input: torch.Tensor) -> float:
        """Full gradient-based surprise on GPU."""
        input = input.to(self.device).requires_grad_(True)

        prediction = self.model(input)
        loss = self._compute_loss(prediction, input)
        loss.backward()

        grad_norm = sum(
            p.grad.norm().item()
            for p in self.model.parameters()
            if p.grad is not None
        )

        # Clear gradients
        self.optimizer.zero_grad()

        return grad_norm

    async def update(self, key: torch.Tensor, value: torch.Tensor) -> None:
        """Test-time training update on GPU."""
        key, value = key.to(self.device), value.to(self.device)

        # Forward pass
        prediction = self.model(key)

        # Compute loss (Huber for outlier robustness)
        loss = torch.nn.functional.huber_loss(prediction, value, delta=1.0)

        # Backward pass
        loss.backward()

        # Optimizer step
        self.optimizer.step()
        self.optimizer.zero_grad()
```

---

## 5. Deployment Patterns

### 5.1 Development Deployment

```yaml
# deploy/kubernetes/memory-service/overlays/development/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 1
    target:
      kind: Deployment
      name: memory-retrieval
  - patch: |-
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/memory
        value: "2Gi"
      - op: replace
        path: /spec/template/spec/containers/0/resources/limits/cpu
        value: "1"
    target:
      kind: Deployment
      name: memory-retrieval

configMapGenerator:
  - name: memory-config
    behavior: merge
    literals:
      - AURA_ENVIRONMENT=development
      - USE_INFERENTIA=false
      - USE_GPU=false
```

### 5.2 Production Large Deployment

```yaml
# deploy/kubernetes/memory-service/overlays/production-large/kustomization.yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - ../../base

patches:
  - patch: |-
      - op: replace
        path: /spec/replicas
        value: 4
    target:
      kind: Deployment
      name: memory-retrieval
  - patch: |-
      - op: add
        path: /spec/template/spec/nodeSelector
        value:
          node.kubernetes.io/instance-type: inf2.8xlarge
      - op: add
        path: /spec/template/spec/containers/0/resources/limits/aws.amazon.com~1neuron
        value: 1
    target:
      kind: Deployment
      name: memory-retrieval

configMapGenerator:
  - name: memory-config
    behavior: merge
    literals:
      - AURA_ENVIRONMENT=production-large
      - USE_INFERENTIA=true
      - USE_GPU=true
```

---

## 6. Scaling Triggers

### 6.1 When to Scale Up

| Metric | Threshold | Action |
|--------|-----------|--------|
| Retrieval p99 latency | > 10ms sustained 5min | Add Inferentia instance |
| TTT queue depth | > 500 for 2min | Add GPU instance |
| NeuronCore utilization | > 90% for 10min | Add Inferentia instance |
| GPU utilization | > 85% for 5min | Add GPU instance |
| Memory service errors | > 1% for 5min | Scale + investigate |

### 6.2 When to Scale Down

| Metric | Threshold | Action |
|--------|-----------|--------|
| NeuronCore utilization | < 40% for 30min | Remove Inferentia instance |
| GPU utilization | < 20% for 15min | Scale GPU to zero |
| TTT queue | Empty for 10min | Scale GPU to zero |

---

## 7. Migration Path

### 7.1 Development → Staging

```bash
# 1. Compile model for Inferentia (one-time)
python scripts/compile_neuron_model.py --dim 512 --depth 3

# 2. Deploy to staging with Inferentia
kubectl apply -k deploy/kubernetes/memory-service/overlays/staging

# 3. Validate latency meets SLA
pytest tests/integration/test_memory_latency.py --env=staging
```

### 7.2 Staging → Production

```bash
# 1. Run load test to validate capacity
locust -f tests/load/memory_service.py --host=staging.aura.internal

# 2. Deploy to production (canary)
kubectl argo rollouts promote memory-service -n aura

# 3. Monitor metrics during rollout
kubectl argo rollouts status memory-service -n aura --watch
```

---

## Summary

| Aspect | Development | Production (L) | Scaling Factor |
|--------|-------------|----------------|----------------|
| Retrieval throughput | 2K req/s | 200K req/s | 100x |
| TTT throughput | 50 upd/s | 1.5K upd/s | 30x |
| p99 latency | ~20ms | ~3ms | 7x better |
| Monthly cost | $380 | $38,100 | 100x |
| Code changes | 0 | 0 | Same codebase |

**Key Principle:** Configuration-driven scaling with hardware abstraction allows seamless transition from development to enterprise production without code changes.

---

*Document Version: 1.0*
*Last Updated: December 6, 2025*
