# ADR-004: Cloud Abstraction Layer for Multi-Cloud Deployment

**Status:** Deployed
**Date:** 2025-11-28
**Deployed:** 2025-12-16
**Decision Makers:** Project Aura Team

## Context

Project Aura targets defense contractors as its primary customer base. Market analysis reveals:

- **60% of defense contractors** use Azure Government (Microsoft dominance in DoD)
- **40% use AWS GovCloud** (growing, especially in DevOps/ML workloads)
- **Multi-cloud = 2.5x larger addressable market** vs single-cloud

Customers with significant existing cloud investments face friction adopting single-cloud solutions:
- An Azure-primary defense contractor would need parallel cloud spend or migration
- An AWS-primary customer can use Aura natively

This decision impacts:
- Total Addressable Market (TAM)
- Engineering investment required ($300-500K estimated)
- Architecture complexity
- Time-to-market tradeoffs

## Decision

We chose to design a **Cloud Abstraction Layer (CAL)** that enables deployment to both AWS GovCloud and Azure Government, with AWS as the primary implementation.

**Strategy:**
1. **Phase 1 (Months 1-6):** Launch on AWS GovCloud only (current state)
2. **Phase 2 (Months 7-9):** Refactor codebase with cloud abstraction interfaces
3. **Phase 3 (Months 10-12):** Implement Azure-specific services (Cosmos DB, Azure OpenAI, AI Search)
4. **Phase 4 (Months 13-15):** Testing, validation, and customer pilots

**Design Principles:**
- Cloud-agnostic business logic
- 1:1 service mapping between AWS and Azure equivalents
- Kubernetes-based deployment (EKS + AKS) for maximum portability
- Unified API abstracting cloud provider differences
- Terraform for consistent IaC across both clouds

## Alternatives Considered

### Alternative 1: AWS-Only Forever

Commit to AWS GovCloud as the sole deployment target.

**Pros:**
- Simpler architecture
- Faster time-to-market
- Deeper AWS integration
- Lower engineering investment

**Cons:**
- Loses 60% of potential market (Azure-primary customers)
- Customer resistance if they have existing Azure investments
- Competitive disadvantage vs multi-cloud solutions

### Alternative 2: Azure-Only

Pivot to Azure Government as primary cloud.

**Pros:**
- Larger initial market (60% vs 40%)
- Microsoft ecosystem integration (Office 365, Active Directory)

**Cons:**
- Team expertise is AWS-focused
- AWS Bedrock (Claude) more mature than Azure OpenAI for code tasks
- Loses AWS-primary customers

### Alternative 3: Multi-Cloud From Day One

Build both AWS and Azure support simultaneously.

**Pros:**
- Full market coverage from launch

**Cons:**
- 2x engineering effort upfront
- Delayed time-to-market
- Higher initial complexity
- More risk (two targets, neither fully validated)

## Consequences

### Positive

1. **Market Expansion**
   - 2.5x larger addressable market
   - Can serve any defense contractor regardless of cloud preference
   - Premium pricing opportunity for multi-cloud deployments

2. **Vendor Lock-In Mitigation**
   - Customers can migrate between clouds if needed
   - Reduces dependency on single cloud provider
   - Attractive for enterprise procurement

3. **Architecture Quality**
   - Forces clean abstractions
   - Improves testability (mock implementations)
   - Better separation of concerns

4. **Future Flexibility**
   - Easier to add GCP or Oracle Cloud later
   - Portable to private cloud if needed

### Negative

1. **Engineering Investment**
   - $300-500K estimated (2-3 engineers × 9 months)
   - Opportunity cost vs. new features

2. **Operational Complexity**
   - Two clouds to monitor and support
   - Different debugging tools per cloud
   - Split documentation and runbooks

3. **Performance Variations**
   - Cosmos DB (Gremlin) may have different performance than Neptune
   - Azure OpenAI may behave differently than Bedrock
   - Need benchmarking on both clouds

4. **Testing Overhead**
   - CI/CD must test both clouds
   - Integration test matrix doubles

### Mitigation

- Start with single-cloud deployments per customer (no cross-cloud sync in V1)
- Use abstraction interfaces to limit cloud-specific code
- Build cloud parity tests into CI/CD
- Document performance differences and set expectations

## Service Mapping

| Function | AWS GovCloud | Azure Government |
|----------|--------------|------------------|
| Graph Database | Amazon Neptune | Azure Cosmos DB (Gremlin API) |
| Vector Database | Amazon OpenSearch | Azure AI Search |
| LLM Inference | Amazon Bedrock (Claude) | Azure OpenAI (GPT-4) |
| Object Storage | Amazon S3 | Azure Blob Storage |
| Container Orchestration | Amazon EKS | Azure AKS |
| Secrets Management | AWS Secrets Manager | Azure Key Vault |
| Identity | IAM | Azure AD + RBAC |

**Key Note:** Both clouds use standard Gremlin query language for graph databases, enabling a single query interface.

## Cost Comparison

| Service | AWS GovCloud | Azure Government | Winner |
|---------|--------------|------------------|--------|
| Kubernetes Control Plane | $72/month | Free | Azure |
| Graph Database | $800/month | $1,200/month | AWS |
| Vector Database | $1,500/month | $2,000/month | AWS |
| LLM API (1M requests) | $12,000/month | $15,000/month | AWS |
| **TOTAL (typical workload)** | **$18,622/month** | **$22,142/month** | **AWS (16% cheaper)** |

**Note:** Customers with Azure Enterprise Agreements may have pre-paid credits making Azure effectively "free" for them.

## Implementation Status (Deployed Dec 16, 2025)

### Cloud Abstraction Layer Structure

```
src/
├── abstractions/                    # Abstract interfaces
│   ├── __init__.py
│   ├── cloud_provider.py           # CloudProvider enum, CloudConfig
│   ├── graph_database.py           # GraphDatabaseService ABC
│   ├── vector_database.py          # VectorDatabaseService ABC
│   ├── llm_service.py              # LLMService ABC
│   ├── storage_service.py          # StorageService ABC
│   └── secrets_service.py          # SecretsService ABC
│
└── services/providers/
    ├── __init__.py
    ├── factory.py                  # CloudServiceFactory
    │
    ├── aws/                        # AWS implementations
    │   ├── neptune_adapter.py      # Neptune → GraphDatabaseService
    │   ├── opensearch_adapter.py   # OpenSearch → VectorDatabaseService
    │   ├── bedrock_adapter.py      # Bedrock → LLMService
    │   ├── s3_adapter.py           # S3 → StorageService
    │   └── secrets_manager_adapter.py
    │
    ├── azure/                      # Azure implementations
    │   ├── cosmos_graph_service.py # Cosmos DB Gremlin → GraphDatabaseService
    │   ├── azure_ai_search_service.py
    │   ├── azure_openai_service.py
    │   ├── azure_blob_service.py
    │   └── azure_keyvault_service.py
    │
    └── mock/                       # Mock for testing
        ├── mock_graph_service.py
        ├── mock_vector_service.py
        ├── mock_llm_service.py
        ├── mock_storage_service.py
        └── mock_secrets_service.py
```

### Service Abstractions

| Service | Abstract Interface | AWS Implementation | Azure Implementation |
|---------|-------------------|-------------------|---------------------|
| Graph Database | `GraphDatabaseService` | `NeptuneGraphAdapter` | `CosmosDBGraphService` |
| Vector Database | `VectorDatabaseService` | `OpenSearchVectorAdapter` | `AzureAISearchService` |
| LLM | `LLMService` | `BedrockLLMAdapter` | `AzureOpenAIService` |
| Storage | `StorageService` | `S3StorageAdapter` | `AzureBlobService` |
| Secrets | `SecretsService` | `SecretsManagerAdapter` | `AzureKeyVaultService` |

### Usage

```python
from src.services.providers import CloudServiceFactory, get_graph_service

# Automatic provider selection from environment
graph = get_graph_service()

# Or explicit provider selection
factory = CloudServiceFactory.for_provider(CloudProvider.AZURE_GOVERNMENT, "usgovvirginia")
graph = factory.create_graph_service()
vector = factory.create_vector_service()
llm = factory.create_llm_service()
```

### Test Coverage

- 46 tests in `tests/test_cloud_abstraction_layer.py`
- Tests cover data models, mock services, factory, and integration workflows
- All tests pass

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CLOUD_PROVIDER` | Provider selection | `aws`, `azure_government`, `mock` |
| `CLOUD_REGION` | Cloud region | `us-gov-west-1`, `usgovvirginia` |
| `NEPTUNE_ENDPOINT` | AWS Neptune endpoint | `neptune.cluster.us-east-1.amazonaws.com` |
| `COSMOS_ENDPOINT` | Azure Cosmos DB endpoint | `https://mydb.documents.azure.com` |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint | `https://myopenai.openai.azure.com` |

## References

- `src/abstractions/` - Cloud abstraction interfaces
- `src/services/providers/` - Cloud provider implementations
- `tests/test_cloud_abstraction_layer.py` - Abstraction layer tests
