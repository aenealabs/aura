# Project Aura: Multi-Cloud Architecture
## AWS GovCloud + Azure Government Deployment

**Version:** 1.1
**Last Updated:** December 16, 2025
**Status:** Phase 2 Complete (Cloud Abstraction Layer Deployed)
**Classification:** Public

---

## Executive Summary

**Objective:** Design a **cloud-agnostic** architecture that deploys seamlessly to both **AWS GovCloud** and **Azure Government**, enabling Aura to serve all defense contractors regardless of their existing cloud investments.

**Business Rationale:**
- **60% of defense contractors** use Azure Government (Microsoft dominance in DoD)
- **40% use AWS GovCloud** (growing, especially in DevOps/ML workloads)
- **Multi-cloud = 2.5x larger addressable market** vs single-cloud

**Technical Strategy:**
- **Abstraction layer** for cloud services (Neptune → Cosmos DB, Bedrock → Azure OpenAI)
- **Kubernetes-based deployment** (EKS + AKS) for portability
- **Infrastructure-as-Code** (Terraform) for consistent provisioning
- **Unified API** that abstracts cloud provider differences

**Investment Required:** $300-500K (architecture + implementation)

**Timeline:** 6-9 months for full multi-cloud parity

---

## Market Drivers for Multi-Cloud

### Defense Contractor Cloud Adoption

| Cloud Provider | Defense Market Share | Top Customers | Key Advantages |
|----------------|---------------------|---------------|----------------|
| **Azure Government** | 58% | Army, Navy, Air Force, DoD CIO | Microsoft Office 365, Active Directory integration |
| **AWS GovCloud** | 35% | CIA, NSA, DIU, Special Ops | Best ML/AI services, DevOps maturity |
| **Google Cloud (GCP)** | 5% | Some DoD labs | BigQuery, niche AI |
| **Oracle Cloud** | 2% | Legacy database migrations | Limited defense presence |

**Key Insight:** Azure dominates **legacy IT** (Office, email, databases), AWS dominates **modern DevOps** (containers, ML, CI/CD).

### Customer Pain Points (Single-Cloud Solutions)

**Scenario 1: Large defense contractor (Azure-primary)**
- Problem: Existing $50M investment in Azure infrastructure
- [Competitor A]: ✅ Available on Azure (via Azure Marketplace)
- Aura (AWS-only): ❌ Requires parallel cloud spend or migration

**Scenario 2: SpaceX (AWS-primary customer)**
- Problem: All ML workloads on AWS Bedrock/SageMaker
- GitHub Copilot: ✅ Cloud-agnostic (SaaS)
- Aura (AWS-only): ✅ Native fit

**Solution:** Multi-cloud Aura supports both scenarios → **2.5x larger TAM**

---

## Architecture Overview

### Design Principles

1. **Cloud Abstraction:** Business logic agnostic to underlying cloud provider
2. **Service Mapping:** 1:1 mapping between AWS and Azure equivalent services
3. **Data Portability:** Cross-cloud data replication for DR/HA
4. **Unified API:** Single API for customers regardless of deployment cloud
5. **Cost Optimization:** Use cheapest cloud for each workload type

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     AURA PLATFORM                            │
│                  (Cloud-Agnostic Layer)                      │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Orchestrator│  │ Context      │  │  LLM         │       │
│  │   Service   │  │ Retrieval    │  │  Service     │       │
│  └─────────────┘  └──────────────┘  └──────────────┘       │
│         │                  │                  │              │
│         ▼                  ▼                  ▼              │
│  ┌──────────────────────────────────────────────────┐       │
│  │         Cloud Abstraction Layer (CAL)            │       │
│  │    GraphDB | VectorDB | ObjectStore | AI        │       │
│  └──────────────────────────────────────────────────┘       │
│         │                                      │             │
├─────────┼──────────────────────────────────────┼─────────────┤
│         ▼                                      ▼             │
│  ┌─────────────┐                       ┌─────────────┐      │
│  │ AWS GOVCLOUD│                       │ AZURE GOV   │      │
│  ├─────────────┤                       ├─────────────┤      │
│  │ Neptune     │                       │ Cosmos DB   │      │
│  │ OpenSearch  │                       │ AI Search   │      │
│  │ Bedrock     │                       │ OpenAI      │      │
│  │ EKS         │                       │ AKS         │      │
│  │ S3          │                       │ Blob Storage│      │
│  │ DynamoDB    │                       │ Cosmos DB   │      │
│  └─────────────┘                       └─────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Service Mapping: AWS ↔ Azure

### Core Infrastructure

| Function | AWS GovCloud | Azure Government | Abstraction Interface |
|----------|--------------|------------------|----------------------|
| **Compute (Containers)** | EKS (Kubernetes) | AKS (Kubernetes) | Standard K8s API |
| **Compute (Serverless)** | Lambda | Azure Functions | CloudEvents spec |
| **Networking** | VPC | VNet | Terraform modules |
| **Load Balancer** | ALB/NLB | Azure Load Balancer | Ingress controller |
| **DNS** | Route 53 | Azure DNS | ExternalDNS |
| **Secrets Management** | Secrets Manager | Key Vault | HashiCorp Vault |

**Implementation:** Deploy on **Kubernetes (EKS/AKS)** for maximum portability.

---

### Data Layer

| Function | AWS GovCloud | Azure Government | Abstraction Strategy |
|----------|--------------|------------------|---------------------|
| **Graph Database** | Amazon Neptune | Azure Cosmos DB (Gremlin API) | **Gremlin query language** (standard) |
| **Vector Database** | OpenSearch | Azure AI Search (vector) | **Custom abstraction layer** |
| **Object Storage** | S3 | Blob Storage | **S3-compatible API** (MinIO-like) |
| **NoSQL Database** | DynamoDB | Cosmos DB (NoSQL API) | **Document store interface** |
| **Relational Database** | RDS PostgreSQL | Azure Database for PostgreSQL | **PostgreSQL wire protocol** |
| **Cache** | ElastiCache (Redis) | Azure Cache for Redis | **Redis protocol** |

#### Implementation Details

**Graph Database Abstraction:**
```python
# src/services/graph_service.py
from abc import ABC, abstractmethod
from gremlin_python.driver import client as gremlin_client

class GraphService(ABC):
    """Cloud-agnostic graph database interface."""

    @abstractmethod
    def execute_query(self, gremlin_query: str) -> dict:
        """Execute Gremlin query (supported by both Neptune and Cosmos)."""
        pass

class NeptuneGraphService(GraphService):
    """AWS Neptune implementation."""
    def __init__(self):
        self.client = gremlin_client.Client(
            url=f'wss://{NEPTUNE_ENDPOINT}:8182/gremlin',
            traversal_source='g'
        )

    def execute_query(self, gremlin_query: str) -> dict:
        return self.client.submit(gremlin_query).all().result()

class CosmosGraphService(GraphService):
    """Azure Cosmos DB (Gremlin API) implementation."""
    def __init__(self):
        self.client = gremlin_client.Client(
            url=f'wss://{COSMOS_ENDPOINT}:443/',
            traversal_source='g',
            username=f"/dbs/{DATABASE}/colls/{COLLECTION}",
            password=COSMOS_KEY
        )

    def execute_query(self, gremlin_query: str) -> dict:
        return self.client.submit(gremlin_query).all().result()

# Factory pattern for cloud selection
def create_graph_service() -> GraphService:
    cloud_provider = os.environ.get("CLOUD_PROVIDER", "aws")
    if cloud_provider == "aws":
        return NeptuneGraphService()
    elif cloud_provider == "azure":
        return CosmosGraphService()
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud_provider}")
```

**Vector Database Abstraction:**
```python
# src/services/vector_service.py
from abc import ABC, abstractmethod
from typing import List, Dict

class VectorService(ABC):
    """Cloud-agnostic vector search interface."""

    @abstractmethod
    def index_documents(self, documents: List[Dict]) -> None:
        """Index code documents with embeddings."""
        pass

    @abstractmethod
    def similarity_search(self, query_vector: List[float], top_k: int = 20) -> List[Dict]:
        """Find similar code chunks."""
        pass

class OpenSearchVectorService(VectorService):
    """AWS OpenSearch implementation."""
    def __init__(self):
        from opensearchpy import OpenSearch
        self.client = OpenSearch(
            hosts=[{'host': OPENSEARCH_ENDPOINT, 'port': 443}],
            http_auth=(USERNAME, PASSWORD),
            use_ssl=True
        )

    def index_documents(self, documents: List[Dict]) -> None:
        for doc in documents:
            self.client.index(
                index="code-embeddings",
                body={
                    "vector": doc["embedding"],
                    "content": doc["code"],
                    "metadata": doc["metadata"]
                }
            )

    def similarity_search(self, query_vector: List[float], top_k: int = 20) -> List[Dict]:
        response = self.client.search(
            index="code-embeddings",
            body={
                "size": top_k,
                "query": {
                    "knn": {
                        "vector": {
                            "vector": query_vector,
                            "k": top_k
                        }
                    }
                }
            }
        )
        return [hit["_source"] for hit in response["hits"]["hits"]]

class AzureAISearchVectorService(VectorService):
    """Azure AI Search (Cognitive Search) implementation."""
    def __init__(self):
        from azure.search.documents import SearchClient
        from azure.core.credentials import AzureKeyCredential

        self.client = SearchClient(
            endpoint=f"https://{SEARCH_SERVICE_NAME}.search.windows.net",
            index_name="code-embeddings",
            credential=AzureKeyCredential(SEARCH_API_KEY)
        )

    def index_documents(self, documents: List[Dict]) -> None:
        formatted_docs = [
            {
                "id": doc["id"],
                "vector": doc["embedding"],
                "content": doc["code"],
                "metadata": doc["metadata"]
            }
            for doc in documents
        ]
        self.client.upload_documents(documents=formatted_docs)

    def similarity_search(self, query_vector: List[float], top_k: int = 20) -> List[Dict]:
        results = self.client.search(
            search_text=None,
            vector_queries=[{
                "vector": query_vector,
                "k": top_k,
                "fields": "vector"
            }]
        )
        return [{"content": r["content"], "metadata": r["metadata"]} for r in results]

# Factory
def create_vector_service() -> VectorService:
    cloud_provider = os.environ.get("CLOUD_PROVIDER", "aws")
    if cloud_provider == "aws":
        return OpenSearchVectorService()
    elif cloud_provider == "azure":
        return AzureAISearchVectorService()
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud_provider}")
```

---

### AI/ML Layer

| Function | AWS GovCloud | Azure Government | Abstraction Strategy |
|----------|--------------|------------------|---------------------|
| **LLM Inference** | Bedrock (Claude, Llama) | Azure OpenAI (GPT-4, GPT-4o) | **LiteLLM proxy** or custom abstraction |
| **Embeddings** | Bedrock (Titan Embeddings) | Azure OpenAI (text-embedding-3) | **Unified embedding interface** |
| **Model Training** | SageMaker | Azure ML | **MLflow tracking** (cloud-agnostic) |

#### LLM Service Multi-Cloud Implementation

```python
# src/services/llm_service_multicloud.py
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from enum import Enum

class CloudProvider(Enum):
    AWS = "aws"
    AZURE = "azure"

class LLMService(ABC):
    """Cloud-agnostic LLM service interface."""

    @abstractmethod
    def invoke_model(
        self,
        prompt: str,
        model_id: str,
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Invoke LLM and return standardized response."""
        pass

class BedrockLLMService(LLMService):
    """AWS Bedrock implementation (existing)."""
    # ... existing implementation from bedrock_llm_service.py

class AzureOpenAILLMService(LLMService):
    """Azure OpenAI implementation."""
    def __init__(self):
        from openai import AzureOpenAI

        self.client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            api_version="2024-02-15-preview",
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"]
        )

    def invoke_model(
        self,
        prompt: str,
        model_id: str = "gpt-4o",
        max_tokens: int = 4096,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Invoke Azure OpenAI."""

        # Map model IDs (AWS → Azure)
        model_mapping = {
            "anthropic.claude-3-5-sonnet-20241022-v1:0": "gpt-4o",
            "anthropic.claude-3-haiku-20240307-v1:0": "gpt-4o-mini"
        }
        azure_model = model_mapping.get(model_id, model_id)

        response = self.client.chat.completions.create(
            model=azure_model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=temperature
        )

        # Standardize response format to match Bedrock
        return {
            "response": response.choices[0].message.content,
            "input_tokens": response.usage.prompt_tokens,
            "output_tokens": response.usage.completion_tokens,
            "cost_usd": self._calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                azure_model
            ),
            "model": azure_model,
            "cached": False,
            "request_id": response.id
        }

    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate Azure OpenAI costs."""
        # Azure OpenAI Gov pricing (as of Nov 2024)
        pricing = {
            "gpt-4o": {"input": 5.00 / 1_000_000, "output": 15.00 / 1_000_000},
            "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000}
        }

        model_pricing = pricing.get(model, pricing["gpt-4o"])
        cost = (input_tokens * model_pricing["input"]) + (output_tokens * model_pricing["output"])
        return round(cost, 6)

# Unified factory
def create_llm_service(cloud_provider: Optional[CloudProvider] = None) -> LLMService:
    """Create LLM service based on cloud provider."""
    if cloud_provider is None:
        cloud_provider = CloudProvider(os.environ.get("CLOUD_PROVIDER", "aws"))

    if cloud_provider == CloudProvider.AWS:
        from services.bedrock_llm_service import BedrockLLMService
        return BedrockLLMService(mode=BedrockMode.AWS)
    elif cloud_provider == CloudProvider.AZURE:
        return AzureOpenAILLMService()
    else:
        raise ValueError(f"Unsupported cloud provider: {cloud_provider}")
```

---

### Security & Compliance

| Function | AWS GovCloud | Azure Government | Notes |
|----------|--------------|------------------|-------|
| **Identity & Access** | IAM | Azure AD + RBAC | Use SAML/OIDC for unified auth |
| **Encryption (at rest)** | KMS | Azure Key Vault | Both FIPS 140-2 Level 3 |
| **Encryption (in transit)** | TLS 1.3 | TLS 1.3 | Standard across both |
| **Compliance** | FedRAMP High | FedRAMP High | Both certified |
| **Audit Logging** | CloudTrail | Azure Monitor | Centralize to Splunk/Datadog |
| **DDoS Protection** | AWS Shield | Azure DDoS Protection | Enabled by default (Gov) |

---

## Deployment Architecture

### Kubernetes-Based Multi-Cloud

**Why Kubernetes:**
- Portable across AWS EKS and Azure AKS
- Standard APIs (no cloud lock-in)
- Rich ecosystem (Helm, operators, service mesh)

```
┌───────────────────────────────────────────────────────┐
│              KUBERNETES CLUSTER                        │
│         (EKS on AWS or AKS on Azure)                  │
├───────────────────────────────────────────────────────┤
│                                                        │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────┐  │
│  │ Orchestrator│   │   Context    │   │   LLM    │  │
│  │   Pod       │   │ Retrieval Pod│   │ Service  │  │
│  │             │   │              │   │   Pod    │  │
│  └─────────────┘   └──────────────┘   └──────────┘  │
│                                                        │
│  ┌─────────────────────────────────────────────────┐ │
│  │          Cloud Abstraction Layer                │ │
│  │       (ConfigMaps + Secrets + Env Vars)         │ │
│  └─────────────────────────────────────────────────┘ │
│                                                        │
│  ┌─────────────────────────────────────────────────┐ │
│  │     External Services (via K8s Service)         │ │
│  │  - Graph DB (Neptune / Cosmos DB)               │ │
│  │  - Vector DB (OpenSearch / AI Search)           │ │
│  │  - Object Store (S3 / Blob Storage)             │ │
│  │  - LLM API (Bedrock / Azure OpenAI)             │ │
│  └─────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────┘
```

### Helm Chart Structure

```yaml
# helm/aura/values.yaml
cloudProvider: aws  # or azure

# Cloud-specific configurations
aws:
  region: us-gov-west-1
  neptune:
    endpoint: aura-graph.cluster-xxx.neptune.amazonaws.com
  opensearch:
    endpoint: aura-search-xxx.us-gov-west-1.es.amazonaws.com
  bedrock:
    region: us-gov-west-1
  s3:
    bucket: aura-artifacts-govcloud

azure:
  region: usgovvirginia
  cosmosdb:
    endpoint: https://aura-cosmos.documents.azure.com
    database: aura
    container: code-graph
  aisearch:
    endpoint: https://aura-search.search.windows.net
    index: code-embeddings
  openai:
    endpoint: https://aura-openai.openai.azure.com
  storage:
    account: auraartifacts
    container: artifacts

# Application configuration
orchestrator:
  replicas: 3
  resources:
    requests:
      memory: "2Gi"
      cpu: "1"
    limits:
      memory: "4Gi"
      cpu: "2"

contextRetrieval:
  replicas: 5
  resources:
    requests:
      memory: "4Gi"
      cpu: "2"
    limits:
      memory: "8Gi"
      cpu: "4"

llmService:
  replicas: 10
  caching:
    enabled: true
    ttl: 86400
  budgets:
    daily: 100
    monthly: 2000
```

### Terraform Multi-Cloud Provisioning

```hcl
# terraform/main.tf
variable "cloud_provider" {
  description = "Cloud provider (aws or azure)"
  type        = string
  default     = "aws"
}

# AWS Module
module "aura_aws" {
  source = "./modules/aws"
  count  = var.cloud_provider == "aws" ? 1 : 0

  region          = "us-gov-west-1"
  environment     = var.environment
  neptune_config  = var.neptune_config
  opensearch_config = var.opensearch_config
}

# Azure Module
module "aura_azure" {
  source = "./modules/azure"
  count  = var.cloud_provider == "azure" ? 1 : 0

  location        = "usgovvirginia"
  environment     = var.environment
  cosmos_config   = var.cosmos_config
  aisearch_config = var.aisearch_config
}

# Common Kubernetes resources (cloud-agnostic)
module "aura_k8s" {
  source = "./modules/kubernetes"

  cloud_provider    = var.cloud_provider
  kubeconfig        = var.cloud_provider == "aws" ? module.aura_aws[0].kubeconfig : module.aura_azure[0].kubeconfig
  external_services = var.cloud_provider == "aws" ? module.aura_aws[0].service_endpoints : module.aura_azure[0].service_endpoints
}
```

---

## Data Synchronization Strategy

### Cross-Cloud Replication (Optional)

**Use Case:** Active-active deployment or disaster recovery

```
AWS GovCloud (Primary)                 Azure Government (Secondary)
┌───────────────────┐                 ┌────────────────────┐
│  Neptune          │ ──── sync ────▶ │  Cosmos DB         │
│  (Code Graph)     │                 │  (Code Graph)      │
└───────────────────┘                 └────────────────────┘

┌───────────────────┐                 ┌────────────────────┐
│  OpenSearch       │ ──── sync ────▶ │  AI Search         │
│  (Vectors)        │                 │  (Vectors)         │
└───────────────────┘                 └────────────────────┘

┌───────────────────┐                 ┌────────────────────┐
│  S3               │ ◀──── sync ───▶ │  Blob Storage      │
│  (Artifacts)      │   (bidirectional)│ (Artifacts)       │
└───────────────────┘                 └────────────────────┘
```

**Implementation Options:**
1. **Event-Driven Sync:** AWS Lambda → Azure Functions (trigger on data changes)
2. **Batch Sync:** Nightly replication jobs (Kubernetes CronJob)
3. **No Sync:** Customers choose one cloud (simpler, recommended for MVP)

**Recommendation:** Start with **single-cloud deployments** (no sync). Add cross-cloud replication in V2.0 if customers demand it.

---

## Cost Comparison: AWS vs Azure

### Pricing for Typical Defense Contractor (500 developers)

| Service | AWS GovCloud | Azure Government | Winner |
|---------|--------------|------------------|--------|
| **Kubernetes** | EKS: $0.10/hr ($72/month) | AKS: Free (compute only) | Azure (-$72) |
| **Compute (100 pods)** | EC2: $3,500/month | Azure VMs: $3,200/month | Azure (-$300) |
| **Graph Database** | Neptune: $800/month | Cosmos DB: $1,200/month | AWS (-$400) |
| **Vector Database** | OpenSearch: $1,500/month | AI Search: $2,000/month | AWS (-$500) |
| **Object Storage (10TB)** | S3: $250/month | Blob: $220/month | Azure (-$30) |
| **LLM API (1M requests)** | Bedrock: $12,000/month | Azure OpenAI: $15,000/month | AWS (-$3,000) |
| **Networking (outbound)** | $500/month | $450/month | Azure (-$50) |
| **TOTAL** | **$18,622/month** | **$22,142/month** | **AWS saves $3,520/month (16%)** |

**Key Insight:** AWS is **16% cheaper** for AI-heavy workloads due to Bedrock pricing vs Azure OpenAI.

**BUT:** If customer already has Azure EA (Enterprise Agreement) with credits, Azure might be "free" (pre-paid).

---

## Migration Strategy

### Phase 1: AWS-First MVP (Months 1-6)

**Focus:** Launch on AWS GovCloud only
- Faster time-to-market
- Leverage existing AWS expertise
- Test with 5-10 AWS-native customers

**Investment:** $0 (already planned)

---

### Phase 2: Cloud Abstraction Layer (Months 7-9) - COMPLETE

**Status:** Deployed December 16, 2025

**Completed Tasks:**
1. Extracted cloud-specific code into abstract interfaces (`src/abstractions/`)
   - `GraphDatabaseService` - Graph database abstraction
   - `VectorDatabaseService` - Vector search abstraction
   - `LLMService` - LLM inference abstraction
   - `StorageService` - Object storage abstraction
   - `SecretsService` - Secrets management abstraction
2. Implemented `CloudServiceFactory` for provider selection (`src/services/providers/factory.py`)
3. Created AWS adapters (`src/services/providers/aws/`)
   - `NeptuneGraphAdapter`, `OpenSearchVectorAdapter`, `BedrockLLMAdapter`, `S3StorageAdapter`, `SecretsManagerAdapter`
4. Created Azure implementations (`src/services/providers/azure/`)
   - `CosmosDBGraphService`, `AzureAISearchService`, `AzureOpenAIService`, `AzureBlobService`, `AzureKeyVaultService`
5. Created mock services for testing (`src/services/providers/mock/`)
6. Added 46 comprehensive tests (`tests/test_cloud_abstraction_layer.py`)

**Total Implementation:** 29 files, 7,238 lines of code

**Investment:** Completed within budget

---

### Phase 3: Azure Implementation (Months 10-12)

**Focus:** Implement Azure-specific services

**Tasks:**
1. Deploy Cosmos DB (Gremlin API) and migrate sample data
2. Deploy Azure AI Search and index code embeddings
3. Integrate Azure OpenAI service
4. Create Azure-specific Terraform modules
5. Deploy Aura on AKS

**Investment:** $200-300K (3 engineers × 3 months + Azure costs)

---

### Phase 4: Testing & Validation (Months 13-15)

**Focus:** Ensure feature parity across clouds

**Tasks:**
1. End-to-end testing on Azure
2. Performance benchmarking (AWS vs Azure)
3. Cost optimization (right-sizing)
4. Security validation (FedRAMP requirements)
5. Customer pilot (2-3 Azure-native customers)

**Investment:** $100-150K (QA + infrastructure)

**Total Multi-Cloud Investment:** $450-650K over 15 months

---

## Customer Deployment Options

### Option 1: Single-Cloud (Recommended for most customers)

**Customer Profile:** Standardized on one cloud (e.g., 100% Azure)

**Deployment:**
```bash
# Customer deploys to their preferred cloud
helm install aura ./aura-chart \
  --set cloudProvider=azure \
  --set azure.cosmosdb.endpoint=<customer-cosmos> \
  --set azure.openai.endpoint=<customer-openai>
```

**Benefits:**
- Lower complexity
- No cross-cloud data transfer costs
- Easier to manage

---

### Option 2: Multi-Cloud (Active-Passive DR)

**Customer Profile:** Mission-critical workload, needs disaster recovery

**Deployment:**
```bash
# Primary on AWS
helm install aura-primary ./aura-chart \
  --set cloudProvider=aws \
  --set replication.enabled=true \
  --set replication.target=azure

# Secondary on Azure (standby)
helm install aura-secondary ./aura-chart \
  --set cloudProvider=azure \
  --set mode=standby \
  --set replication.source=aws
```

**Benefits:**
- High availability (cross-cloud failover)
- Protects against cloud outages

**Drawbacks:**
- 2x infrastructure cost
- Complex data synchronization

---

### Option 3: Multi-Cloud (Active-Active)

**Customer Profile:** Global contractor with teams in multiple regions

**Deployment:**
```bash
# US West team uses AWS
helm install aura-west ./aura-chart \
  --set cloudProvider=aws \
  --set region=us-gov-west-1

# US East team uses Azure
helm install aura-east ./aura-chart \
  --set cloudProvider=azure \
  --set region=usgovvirginia
```

**Benefits:**
- Lowest latency for distributed teams
- Cloud flexibility

**Drawbacks:**
- Complex (eventual consistency, data conflicts)
- Not recommended for V1.0

---

## Vendor Lock-In Mitigation

### Services with No Equivalent (Handle Carefully)

| AWS-Specific | Azure Alternative | Mitigation Strategy |
|--------------|-------------------|---------------------|
| **Lambda@Edge** | Azure Front Door Functions | Use CloudFlare Workers (cloud-agnostic) |
| **SageMaker** | Azure ML | Abstract with MLflow |
| **Step Functions** | Logic Apps | Use Temporal.io (self-hosted) |
| **EventBridge** | Event Grid | Use NATS or Kafka (self-hosted) |

**Principle:** For orchestration/workflow, prefer **self-hosted open-source** (Temporal, Kafka) over cloud-native services (Step Functions, Logic Apps).

---

## Testing & Validation

### Multi-Cloud Test Matrix

| Test Type | AWS GovCloud | Azure Government | Status |
|-----------|--------------|------------------|--------|
| **Unit Tests** | ✅ Pass (46 tests) | ✅ Pass (46 tests) | Automated (CI/CD) |
| **Integration Tests** | ✅ Pass | ✅ Pass (Mock) | Azure mock services complete |
| **E2E Tests (Orchestrator)** | ✅ Pass | 🔶 Pending | Azure-specific LLM integration |
| **Performance (Graph Query)** | ✅ 50ms p95 | ❓ TBD | Benchmark after Azure deployment |
| **Performance (Vector Search)** | ✅ 100ms p95 | ❓ TBD | AI Search performance unknown |
| **Cost (1M requests)** | ✅ $18K | ❓ TBD | Projected $22K (Azure) |
| **Security (FedRAMP)** | ✅ Compliant | 🔶 In progress | Azure Gov inherits FedRAMP |

**Cloud Abstraction Layer Tests (46 total):**
- Data model tests (CloudProvider, CloudConfig)
- Mock service tests (all 5 services)
- Factory pattern tests (provider selection, region configuration)
- Integration workflow tests (multi-service scenarios)

---

## Rollout Plan

### Customer Segmentation

**Segment 1: AWS-Native Customers (Months 1-12)**
- Deploy on AWS GovCloud only
- Cloud abstraction layer: Not customer-facing yet

**Segment 2: Azure-Native Customers (Months 13-24)**
- Deploy on Azure Government
- Leverage cloud abstraction work from Segment 1

**Segment 3: Multi-Cloud Customers (Months 25+)**
- Offer active-active or DR deployments
- Premium tier for multi-cloud deployments

---

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Cloud Abstraction Coverage** | 95%+ | % of code that's cloud-agnostic |
| **Azure Feature Parity** | 100% | All AWS features work on Azure |
| **Performance Delta (AWS vs Azure)** | <10% | p95 latency difference |
| **Cost Delta (AWS vs Azure)** | <25% | Total infrastructure cost |
| **Customer Adoption (Azure)** | 40% | % of customers choosing Azure |
| **Cross-Cloud Migration Time** | <7 days | Time to migrate customer AWS→Azure |

---

## Risks & Mitigation

### Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Cosmos DB (Gremlin) performance lags Neptune** | Medium | High | Benchmark early, optimize queries |
| **Azure AI Search vector quality differs from OpenSearch** | Medium | Medium | A/B test retrieval accuracy |
| **Azure OpenAI rate limits stricter than Bedrock** | Low | Medium | Implement queueing, caching |
| **Cross-cloud data sync complexity** | High | High | Avoid sync in V1.0 (single-cloud only) |

### Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Azure deployment delays MVP launch** | Medium | High | Prioritize AWS, defer Azure to Phase 2 |
| **Customers demand GCP support** | Low | Medium | Evaluate after Azure success |
| **Multi-cloud confuses sales messaging** | Medium | Medium | Lead with AWS, Azure as "also available" |

---

## Next Steps

### Immediate Actions (Next 30 Days)

1. **Hire Cloud Architect** (AWS + Azure expertise) - $180-250K
2. **Provision Azure Gov Tenant** (requires DoD customer proof or sponsorship)
3. **Prototype Cosmos DB Graph Queries** (validate Gremlin compatibility)
4. **Prototype Azure OpenAI Integration** (validate API parity with Bedrock)

### Phase 2 Kickoff (Months 7-9)

1. Refactor existing codebase for cloud abstraction
2. Create multi-cloud CI/CD pipeline (test on both clouds)
3. Develop Terraform modules for Azure
4. Document cloud provider selection guide for customers

---

## Appendix: Azure Government Specifics

### Azure Government Regions

| Region | Location | Services | Notes |
|--------|----------|----------|-------|
| **USGov Virginia** | Virginia | All services | Primary Gov region |
| **USGov Texas** | Texas | Most services | DR/HA option |
| **USGov Arizona** | Arizona | Limited services | DoD-specific |
| **USDoD East** | Classified | DoD IL5/IL6 only | Secret/Top Secret |
| **USDoD Central** | Classified | DoD IL5/IL6 only | Secret/Top Secret |

**Recommendation:** Deploy to **USGov Virginia** (primary) + **USGov Texas** (DR)

### Azure Government Compliance

| Certification | Status | Scope |
|--------------|--------|-------|
| **FedRAMP High** | ✅ Authorized | All USGov regions |
| **DoD IL2** | ✅ Authorized | USGov regions |
| **DoD IL4** | ✅ Authorized | USGov regions |
| **DoD IL5** | ✅ Authorized | USDoD regions only |
| **DoD IL6** | ✅ Authorized | USDoD regions only |

**Aura's Deployment:** Start with **USGov Virginia** (FedRAMP High) for Level 2/3 CMMC customers.

---

**Document Version:** 1.0
**Last Updated:** December 2025
**Next Review:** Quarterly
**Owner:** Chief Technology Officer (CTO)

---

**Classification:** Public
**Distribution:** Open source community
