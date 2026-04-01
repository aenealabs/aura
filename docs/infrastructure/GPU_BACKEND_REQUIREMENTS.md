# GPU Backend Requirements for ML Services

This document outlines the GPU requirements and hardware recommendations for Project Aura's machine learning services, including neural memory, embedding generation, and LLM inference.

## Overview

Project Aura uses GPU acceleration for:
- **Titan Embedding Service**: Vector embedding generation with Amazon Titan
- **Neural Memory Service**: Titan cognitive architecture with memory consolidation
- **Local LLM Inference**: Optional GPU-accelerated inference for on-premise deployments

## AWS Managed GPU Services (Recommended)

For production deployments, AWS Bedrock handles GPU infrastructure transparently:

| Service | AWS Backend | GPU Requirements |
|---------|-------------|------------------|
| Titan Embeddings | Amazon Bedrock | Managed (no user config) |
| Claude/Sonnet | Amazon Bedrock | Managed (no user config) |
| Neural Memory | CPU + Bedrock | No GPU required |

**Production Recommendation**: Use AWS Bedrock for all LLM operations. Bedrock handles GPU provisioning, scaling, and cost optimization automatically.

## Self-Hosted GPU Requirements

For organizations requiring on-premise or self-hosted deployments:

### Minimum Requirements (Development/Testing)

| Component | Specification |
|-----------|---------------|
| GPU | NVIDIA RTX 3090 (24GB VRAM) |
| CPU | 16 cores |
| RAM | 64GB |
| Storage | 500GB NVMe SSD |
| CUDA | 12.0+ |
| Driver | 525+ |

### Recommended (Small Production)

| Component | Specification |
|-----------|---------------|
| GPU | NVIDIA A10G (24GB VRAM) x2 |
| CPU | 32 cores (AMD EPYC or Intel Xeon) |
| RAM | 128GB ECC |
| Storage | 1TB NVMe SSD (RAID 1) |
| CUDA | 12.2+ |
| Network | 25 Gbps |

### High-Scale Production

| Component | Specification |
|-----------|---------------|
| GPU | NVIDIA A100 (80GB VRAM) x4 |
| CPU | 64 cores (AMD EPYC 7763) |
| RAM | 512GB ECC |
| Storage | 4TB NVMe SSD (RAID 10) |
| CUDA | 12.2+ |
| Network | 100 Gbps InfiniBand |

## AWS Instance Types

| Use Case | Instance Type | vCPUs | RAM | GPU | Cost ($/hr) |
|----------|---------------|-------|-----|-----|-------------|
| Development | g4dn.xlarge | 4 | 16GB | T4 16GB | ~$0.53 |
| Embeddings | g4dn.2xlarge | 8 | 32GB | T4 16GB | ~$0.75 |
| Inference | g5.2xlarge | 8 | 32GB | A10G 24GB | ~$1.21 |
| Training | p4d.24xlarge | 96 | 1152GB | A100 80GB x8 | ~$32.77 |

## Memory Requirements by Operation

### Embedding Generation

```
Batch Size 1:    ~2GB VRAM
Batch Size 10:   ~4GB VRAM
Batch Size 100:  ~8GB VRAM
Batch Size 500:  ~16GB VRAM (max recommended)
```

### Neural Memory Consolidation

Neural memory operations are CPU-bound with optional GPU acceleration:

```
Memory Bank Size 1K entries:   ~512MB RAM
Memory Bank Size 10K entries:  ~2GB RAM
Memory Bank Size 100K entries: ~8GB RAM
Consolidation (GPU):           ~4GB VRAM
```

### LLM Context Processing

For self-hosted LLM inference:

```
7B parameter model:   ~14GB VRAM (FP16)
13B parameter model:  ~26GB VRAM (FP16)
70B parameter model:  ~140GB VRAM (FP16, requires multi-GPU)
```

## Configuration Examples

### Titan Embedding Service

```python
# titan_embedding_service.py configuration
class TitanEmbeddingService:
    # Batch processing configuration
    DEFAULT_BATCH_SIZE = 10  # Concurrent embeddings
    MAX_BATCH_SIZE = 100     # Hardware-dependent limit

    # For GPU-accelerated deployments
    GPU_BATCH_SIZE = 50      # Optimized for A10G
    CPU_BATCH_SIZE = 10      # Fallback for CPU-only
```

### EKS Node Group Configuration

```yaml
# deploy/cloudformation/eks-nodegroup.yaml
GPUNodeGroup:
  InstanceTypes:
    - g5.2xlarge      # Primary: A10G GPU
    - g4dn.2xlarge    # Fallback: T4 GPU
  DesiredCapacity: 2
  MinSize: 1
  MaxSize: 4
  Labels:
    node-type: gpu
    workload: ml-inference
  Taints:
    - Key: nvidia.com/gpu
      Value: "true"
      Effect: NoSchedule
```

### Kubernetes GPU Pod Spec

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: embedding-service
spec:
  containers:
  - name: titan-embeddings
    resources:
      limits:
        nvidia.com/gpu: 1
        memory: "32Gi"
        cpu: "8"
      requests:
        nvidia.com/gpu: 1
        memory: "16Gi"
        cpu: "4"
  tolerations:
  - key: nvidia.com/gpu
    operator: Exists
    effect: NoSchedule
  nodeSelector:
    node-type: gpu
```

## Performance Benchmarks

### Embedding Generation Throughput

| Hardware | Batch Size | Throughput (embeddings/sec) |
|----------|------------|------------------------------|
| CPU (32 cores) | 10 | ~50 |
| T4 (16GB) | 50 | ~200 |
| A10G (24GB) | 100 | ~500 |
| A100 (80GB) | 500 | ~2000 |

### Latency Targets

| Operation | P50 | P95 | P99 |
|-----------|-----|-----|-----|
| Single embedding | 20ms | 50ms | 100ms |
| Batch (10) | 50ms | 100ms | 200ms |
| LLM inference (Bedrock) | 500ms | 1500ms | 3000ms |

## Cost Optimization

### Recommendations

1. **Use Spot Instances** for embedding batch processing (60-70% savings)
2. **Scale to Zero** during off-hours using KEDA or HPA
3. **Use Bedrock** for LLM inference (pay-per-token, no idle costs)
4. **Cache embeddings** to reduce redundant GPU calls (see issue #152)
5. **Batch requests** to maximize GPU utilization (see issue #155)

### Monthly Cost Estimates

| Workload | On-Demand | Spot | Bedrock |
|----------|-----------|------|---------|
| Light (1K embeddings/day) | $50 | $20 | $5 |
| Medium (10K embeddings/day) | $200 | $80 | $30 |
| Heavy (100K embeddings/day) | $1000 | $400 | $250 |

## CUDA Compatibility Matrix

| PyTorch Version | CUDA | cuDNN | Minimum Driver |
|-----------------|------|-------|----------------|
| 2.0 | 11.8 | 8.7 | 520.61 |
| 2.1 | 12.1 | 8.9 | 530.30 |
| 2.2 | 12.2 | 8.9 | 535.54 |

## Troubleshooting

### Common Issues

1. **CUDA Out of Memory**
   - Reduce batch size
   - Enable gradient checkpointing
   - Use mixed precision (FP16)

2. **Slow GPU Performance**
   - Check GPU utilization with `nvidia-smi`
   - Ensure CUDA version matches PyTorch
   - Verify PCIe bandwidth (x16 recommended)

3. **GPU Not Detected**
   - Check NVIDIA driver installation
   - Verify CUDA toolkit
   - Check kubernetes device plugin

### Monitoring Commands

```bash
# Check GPU status
nvidia-smi

# Monitor GPU in real-time
watch -n 1 nvidia-smi

# Check CUDA version
nvcc --version

# Check PyTorch CUDA
python -c "import torch; print(torch.cuda.is_available())"
```

## References

- [AWS Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [NVIDIA Data Center GPUs](https://www.nvidia.com/en-us/data-center/products/a100/)
- [EKS GPU Support](https://docs.aws.amazon.com/eks/latest/userguide/eks-optimized-ami.html)
- ADR-024: Titan Neural Memory Architecture
- Issue #155: ML Pipeline Optimization
