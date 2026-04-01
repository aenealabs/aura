# Phase 2 Implementation Guide: Core AI Services Deployment

**Project Aura - Autonomous AI SaaS Platform**
**Date:** November 2025
**Status:** Ready for Implementation

---

## Executive Summary

Phase 2 focuses on deploying and integrating the **core AI services** that power Project Aura's autonomous code intelligence. This phase implements real LLM integration, knowledge graph storage, semantic search, and embedding generation.

**Estimated Timeline:** 2-3 weeks
**Estimated Cost:** $42-111/month (dev environment, optimized: $42/month)
**Prerequisites:** Phase 1 infrastructure deployed ✅ (VPC, security groups, IAM roles)

---

## 📦 What's Being Deployed

### Core AI Services (NEW - Production-Ready)

All services are **already implemented** and ready to deploy:

| Service | File | Status | Purpose |
|---------|------|--------|---------|
| **Bedrock LLM Service** | `src/services/bedrock_llm_service.py` | ✅ **Production-Ready** | Multi-model LLM access (Claude, GPT-4) |
| **Neptune Graph Service** | `src/services/neptune_graph_service.py` | ✅ **Production-Ready** | Knowledge graph for code relationships |
| **OpenSearch Vector Service** | `src/services/opensearch_vector_service.py` | ✅ **Production-Ready** | k-NN semantic search |
| **Titan Embedding Service** | `src/services/titan_embedding_service.py` | ✅ **Production-Ready** | Code embedding generation |

### Infrastructure Components

| Component | Template | Cost (Dev) | Notes |
|-----------|----------|------------|-------|
| **Neptune Cluster** | `deploy/cloudformation/neptune.yaml` | $20-79/month | db.t3.medium, stop/start optimized |
| **OpenSearch Cluster** | `deploy/cloudformation/opensearch.yaml` | $0-27/month | t3.small.search, free tier first year |
| **DynamoDB Cost Table** | Auto-created | <$1/month | LLM cost tracking |
| **CloudWatch Metrics** | Auto-configured | ~$5/month | Monitoring & alarms |

---

## 🎯 Implementation Strategy

### Recommended Approach: **Incremental Deployment**

Deploy services one at a time, test, then integrate. This minimizes risk and allows for cost optimization at each step.

**Week 1:** Neptune + Graph Service
**Week 2:** OpenSearch + Embedding Service
**Week 3:** Integration + Testing

---

## Phase 2.1: Neptune Knowledge Graph (Week 1)

### Step 1.1: Deploy Neptune Database

**Cost:** $20/month (stop/start) or $79/month (always-on)

```bash
# Navigate to deployment directory
cd deploy/cloudformation

# Set environment variables
export AWS_PROFILE=AdministratorAccess-123456789012
export AWS_DEFAULT_REGION=us-east-1
export ENVIRONMENT=dev
export PROJECT_NAME=aura

# Deploy Neptune stack
aws cloudformation create-stack \
  --stack-name aura-neptune-dev \
  --template-body file://neptune.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=VpcId,ParameterValue=vpc-0123456789abcdef0 \
    ParameterKey=PrivateSubnetIds,ParameterValue="subnet-XXXXX\\,subnet-YYYYY" \
    ParameterKey=NeptuneSecurityGroupId,ParameterValue=sg-XXXXX \
    ParameterKey=InstanceType,ParameterValue=db.t3.medium \
  --capabilities CAPABILITY_IAM

# Wait for stack creation (5-10 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name aura-neptune-dev

# Get Neptune endpoint
aws cloudformation describe-stacks \
  --stack-name aura-neptune-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`NeptuneEndpoint`].OutputValue' \
  --output text
```

**Expected Output:**
```
aura-neptune-dev.cluster-XXXXX.us-east-1.neptune.amazonaws.com
```

### Step 1.2: Configure Neptune Service Discovery

Add Neptune endpoint to dnsmasq for local resolution:

```bash
# Update Route53 private hosted zone (or use dnsmasq)
aws route53 change-resource-record-sets \
  --hosted-zone-id Z0123456789ABC \
  --change-batch '{
    "Changes": [{
      "Action": "UPSERT",
      "ResourceRecordSet": {
        "Name": "neptune.aura.local",
        "Type": "CNAME",
        "TTL": 300,
        "ResourceRecords": [{"Value": "aura-neptune-dev.cluster-XXXXX.us-east-1.neptune.amazonaws.com"}]
      }
    }]
  }'
```

### Step 1.3: Install Gremlin Python Client

```bash
# Install dependencies
pip install gremlinpython boto3

# Add to requirements.txt
echo "gremlinpython==3.7.1" >> requirements.txt
echo "boto3==1.34.0" >> requirements.txt
```

### Step 1.4: Test Neptune Connection

```bash
# Set environment variable
export NEPTUNE_ENDPOINT=aura-neptune-dev.cluster-XXXXX.us-east-1.neptune.amazonaws.com

# Run Neptune service demo
python src/services/neptune_graph_service.py
```

**Expected Output:**
```
Project Aura - Neptune Graph Service Demo
============================================================

Mode: aws
Endpoint: aura-neptune-dev.cluster-XXXXX.us-east-1.neptune.amazonaws.com:8182

----------------------------------------------------------
Testing graph operations...
✓ Added class: src/validators/security.py::SecurityValidator
✓ Added method: src/validators/security.py::validate_input

✓ Found 1 related entities:
  - validate_input (method)

============================================================
Demo complete!
```

### Step 1.5: Cost Optimization - Stop/Start Schedule

**Save 70% on Neptune costs** by running only during working hours:

```bash
# Create Lambda function for Neptune stop/start
cd deploy/lambda
cat > neptune-scheduler.py <<'EOF'
import boto3

neptune = boto3.client('neptune')

def lambda_handler(event, context):
    cluster_id = 'aura-neptune-dev'
    action = event.get('action', 'stop')  # 'stop' or 'start'

    if action == 'stop':
        neptune.stop_db_cluster(DBClusterIdentifier=cluster_id)
        return {'status': 'stopping', 'cluster': cluster_id}
    elif action == 'start':
        neptune.start_db_cluster(DBClusterIdentifier=cluster_id)
        return {'status': 'starting', 'cluster': cluster_id}
EOF

# Create EventBridge rules
# Stop at 23:00 UTC (weekdays off-hours)
aws events put-rule \
  --name aura-neptune-stop-schedule \
  --schedule-expression "cron(0 23 ? * MON-FRI *)" \
  --state ENABLED

# Start at 13:00 UTC (weekday business hours)
aws events put-rule \
  --name aura-neptune-start-schedule \
  --schedule-expression "cron(0 13 ? * MON-FRI *)" \
  --state ENABLED
```

**Cost Savings:**
- **Always-on:** $79/month
- **Stop/start (8hrs/day, 5 days/week):** $20/month
- **Savings:** $59/month (75% reduction)

---

## Phase 2.2: OpenSearch Vector Store (Week 2)

### Step 2.1: Deploy OpenSearch Cluster

**Cost:** $0/month (free tier first year) or $27/month after

```bash
# Deploy OpenSearch stack
aws cloudformation create-stack \
  --stack-name aura-opensearch-dev \
  --template-body file://opensearch.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=ProjectName,ParameterValue=aura \
    ParameterKey=VpcId,ParameterValue=vpc-0123456789abcdef0 \
    ParameterKey=PrivateSubnetIds,ParameterValue="subnet-XXXXX" \
    ParameterKey=OpenSearchSecurityGroupId,ParameterValue=sg-YYYYY \
    ParameterKey=InstanceType,ParameterValue=t3.small.search \
    ParameterKey=InstanceCount,ParameterValue=1 \
  --capabilities CAPABILITY_IAM

# Wait for deployment (10-15 minutes)
aws cloudformation wait stack-create-complete \
  --stack-name aura-opensearch-dev

# Get OpenSearch endpoint
aws cloudformation describe-stacks \
  --stack-name aura-opensearch-dev \
  --query 'Stacks[0].Outputs[?OutputKey==`OpenSearchEndpoint`].OutputValue' \
  --output text
```

### Step 2.2: Install OpenSearch Python Client

```bash
# Install dependencies
pip install opensearch-py requests-aws4auth

# Add to requirements.txt
echo "opensearch-py==2.4.0" >> requirements.txt
echo "requests-aws4auth==1.2.3" >> requirements.txt
```

### Step 2.3: Test OpenSearch Connection

```bash
# Set environment variable
export OPENSEARCH_ENDPOINT=search-aura-dev-XXXXX.us-east-1.es.amazonaws.com

# Run OpenSearch service demo
python src/services/opensearch_vector_service.py
```

**Expected Output:**
```
Project Aura - OpenSearch Vector Service Demo
============================================================

Mode: aws
Endpoint: search-aura-dev-XXXXX.us-east-1.es.amazonaws.com:9200
Index: aura-code-embeddings
Vector Dimension: 1024

----------------------------------------------------------
Testing vector operations...
✓ Indexed 2 code embeddings

✓ Found 2 similar code snippets:
  1. def validate_input(data): return sanitize(data)... (score: 0.953)
     File: src/validators.py
  2. def process_data(input): return transform(input)... (score: 0.847)
     File: src/processors.py

============================================================
Demo complete!
```

---

## Phase 2.3: Bedrock LLM & Titan Embeddings (Week 2-3)

### Step 3.1: Enable Bedrock Models

**Important:** Bedrock models must be enabled in your AWS account before use.

```bash
# Check available models
aws bedrock list-foundation-models \
  --region us-east-1 \
  --query 'modelSummaries[?contains(modelId, `claude`) || contains(modelId, `titan-embed`)].modelId'

# Expected output:
[
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "amazon.titan-embed-text-v2:0"
]
```

**Enable models via AWS Console:**
1. Navigate to Bedrock console → Model access
2. Request access to:
   - Claude 3.5 Sonnet (primary LLM)
   - Claude 3 Haiku (fallback LLM)
   - Amazon Titan Embeddings v2 (code embeddings)
3. Wait 1-5 minutes for approval (automatic for most models)

### Step 3.2: Configure Bedrock LLM Service

```bash
# Create config directory
mkdir -p src/config

# Bedrock config already exists at src/config/bedrock_config.py
# Verify configuration
cat src/config/bedrock_config.py
```

### Step 3.3: Create DynamoDB Cost Tracking Table

```bash
# Create DynamoDB table for LLM cost tracking
aws dynamodb create-table \
  --table-name aura-llm-costs \
  --attribute-definitions \
    AttributeName=request_id,AttributeType=S \
    AttributeName=date,AttributeType=S \
    AttributeName=month,AttributeType=S \
  --key-schema \
    AttributeName=request_id,KeyType=HASH \
  --global-secondary-indexes \
    '[
      {
        "IndexName": "date-index",
        "KeySchema": [{"AttributeName": "date", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
      },
      {
        "IndexName": "month-index",
        "KeySchema": [{"AttributeName": "month", "KeyType": "HASH"}],
        "Projection": {"ProjectionType": "ALL"},
        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5}
      }
    ]' \
  --provisioned-throughput ReadCapacityUnits=5,WriteCapacityUnits=5 \
  --tags Key=Project,Value=aura Key=Environment,Value=dev
```

### Step 3.4: Test Bedrock LLM Service

```bash
# Set AWS environment
export AWS_PROFILE=AdministratorAccess-123456789012
export AWS_DEFAULT_REGION=us-east-1
export AURA_ENV=development

# Run Bedrock LLM demo
python src/services/bedrock_llm_service.py
```

**Expected Output:**
```
Project Aura - Bedrock LLM Service Demo
============================================================

Mode: aws
Environment: development
Primary Model: claude-3-5-sonnet-20241022-v2:0
Daily Budget: $50.00

----------------------------------------------------------
Testing model invocation...

✓ Success!
Response: To prevent SQL injection vulnerabilities in Python, you should...
Input Tokens: 25
Output Tokens: 187
Cost: $0.000612
Model: sonnet

----------------------------------------------------------
Spend Summary:
  Daily: $0.00 / $50.00 (0.0%)
  Monthly: $0.00 / $500.00 (0.0%)
  Total Requests: 1

============================================================
Demo complete!
```

### Step 3.5: Test Titan Embedding Service

```bash
# Run Titan embedding demo
python src/services/titan_embedding_service.py
```

**Expected Output:**
```
Project Aura - Titan Embedding Service Demo
============================================================

Mode: aws
Model: amazon.titan-embed-text-v2:0
Vector Dimension: 1024
Daily Budget: $5.00

----------------------------------------------------------
Testing embedding generation...

✓ Generated embedding for code snippet
  Vector dimension: 1024
  First 5 values: [0.0234, -0.0156, 0.0891, -0.0045, 0.0312]
  Cost: $0.000012

✓ Generated 3 embeddings in batch
  Total cost: $0.000036

✓ Embedded full file into 2 chunks

----------------------------------------------------------
Service Statistics:
  Total Tokens: 1,245
  Total Cost: $0.000124
  Daily Budget: $0.000124 / $5.00 (0.0%)
  Cache Hit Rate: 33.3% (1/3)

============================================================
Demo complete!
```

---

## Phase 2.4: Integration with Existing Agents (Week 3)

### Step 4.1: Update Agent Orchestrator

Replace mock implementations with real services:

```python
# File: src/agents/agent_orchestrator.py

# OLD (Mock):
class GraphBuilderAgent:
    def __init__(self):
        self.graph = {}  # In-memory mock

# NEW (Production):
from src.services.neptune_graph_service import create_graph_service
from src.services.opensearch_vector_service import create_vector_service
from src.services.bedrock_llm_service import create_llm_service
from src.services.titan_embedding_service import create_embedding_service

class System2Orchestrator:
    def __init__(self):
        # Initialize production services
        self.llm = create_llm_service()
        self.graph = create_graph_service()
        self.vectors = create_vector_service()
        self.embeddings = create_embedding_service()

        logger.info("System2Orchestrator initialized with production services")
```

### Step 4.2: Update Context Retrieval Service

```python
# File: src/agents/agent_orchestrator.py (ContextRetrievalService class)

class ContextRetrievalService:
    def __init__(self, graph_service, vector_service):
        self.graph = graph_service
        self.vectors = vector_service

    def retrieve_context(self, query: str, vulnerability: str) -> HybridContext:
        """Retrieve hybrid context from Neptune + OpenSearch."""

        # 1. Graph traversal (structural context)
        graph_results = self.graph.find_related_code(
            entity_name=vulnerability,
            max_depth=2,
            relationship_types=['CALLS', 'IMPORTS', 'INHERITS']
        )

        # 2. Vector search (semantic context)
        # Generate query embedding
        query_vector = embeddings.generate_embedding(query)

        # Search similar code
        vector_results = self.vectors.search_similar(
            query_vector=query_vector,
            k=5,
            min_score=0.7
        )

        # 3. Combine results into HybridContext
        context = HybridContext()

        for item in graph_results:
            context.add_item(
                content=item['name'],
                source=ContextSource.GRAPH,
                confidence=0.9,
                metadata=item
            )

        for item in vector_results:
            context.add_item(
                content=item['text'],
                source=ContextSource.VECTOR,
                confidence=item['score'],
                metadata=item['metadata']
            )

        return context
```

### Step 4.3: Test End-to-End Workflow

```bash
# Run orchestrator with real services
python -c "
from src.agents.agent_orchestrator import System2Orchestrator

# Initialize with production services
orchestrator = System2Orchestrator()

# Test autonomous remediation workflow
result = orchestrator.run_autonomous_remediation(
    prompt='Fix the insecure hash function in DataProcessor.generate_checksum'
)

print(f'Success: {result[\"success\"]}')
print(f'Patches Generated: {len(result.get(\"patches\", []))}')
"
```

---

## 📊 Cost Summary & Optimization

### Monthly Cost Breakdown (Dev Environment)

| Service | Always-On | Optimized | Savings |
|---------|-----------|-----------|---------|
| **Neptune** | $79 | $20 (stop/start) | $59 |
| **OpenSearch** | $27 | $0 (free tier year 1) | $27 |
| **VPC (Phase 1)** | $5 | $5 | $0 |
| **Bedrock LLM** | $10 (est) | $10 | $0 |
| **Titan Embeddings** | $2 | $2 | $0 |
| **DynamoDB** | $1 | $1 | $0 |
| **CloudWatch** | $5 | $5 | $0 |
| **Total** | **$129** | **$43** | **$86** |

**✅ Optimized Monthly Cost: $43** (well under $100 target)

### Cost Optimization Best Practices

1. **Neptune Stop/Start Automation** (saves $59/month)
   - Automated Lambda + EventBridge schedule
   - Run 8 hours/day, 5 days/week during development

2. **Use Free Tier** (saves $27/month first year)
   - OpenSearch t3.small.search: 750 hours/month free (first 12 months)
   - DynamoDB: 25 GB storage free

3. **Cache Aggressively**
   - LLM responses cached (saves on duplicate queries)
   - Embedding vectors cached (reduces Titan API calls)

4. **Budget Enforcement**
   - Daily LLM budget: $10 (prevents runaway costs)
   - Daily embedding budget: $5
   - CloudWatch alarms at 80% threshold

5. **Use Spot Instances** (future optimization)
   - ECS Fargate Spot for non-critical workloads (70% savings)

---

## ✅ Testing & Validation

### Service Health Checks

Create monitoring dashboard:

```bash
# Test all services are reachable
python -c "
from src.services.neptune_graph_service import create_graph_service
from src.services.opensearch_vector_service import create_vector_service
from src.services.bedrock_llm_service import create_llm_service
from src.services.titan_embedding_service import create_embedding_service

services = {
    'Neptune': create_graph_service(),
    'OpenSearch': create_vector_service(),
    'Bedrock LLM': create_llm_service(),
    'Titan Embeddings': create_embedding_service()
}

for name, service in services.items():
    print(f'✓ {name}: {service.mode.value} mode')
"
```

### Integration Tests

```bash
# Run integration tests with real AWS services
pytest tests/test_integration_aws.py -v

# Expected output:
tests/test_integration_aws.py::test_neptune_connection PASSED
tests/test_integration_aws.py::test_opensearch_indexing PASSED
tests/test_integration_aws.py::test_bedrock_llm_invocation PASSED
tests/test_integration_aws.py::test_titan_embeddings PASSED
tests/test_integration_aws.py::test_end_to_end_workflow PASSED
```

---

## 🚀 Deployment Checklist

### Pre-Deployment

- [x] Phase 1 infrastructure deployed (VPC, security groups, IAM)
- [ ] AWS Bedrock models enabled (Claude 3.5, Titan Embeddings)
- [ ] Private subnets have internet access (NAT Gateway or VPC endpoints)
- [ ] Security groups configured (Neptune 8182, OpenSearch 443)

### Week 1: Neptune

- [ ] Deploy Neptune CloudFormation stack
- [ ] Configure service discovery (Route53 or dnsmasq)
- [ ] Install Gremlin Python client
- [ ] Test Neptune connection
- [ ] Set up stop/start automation (optional, saves $59/month)

### Week 2: OpenSearch + Embeddings

- [ ] Deploy OpenSearch CloudFormation stack
- [ ] Install OpenSearch Python client
- [ ] Test OpenSearch connection
- [ ] Test Bedrock LLM service
- [ ] Test Titan embedding service
- [ ] Create DynamoDB cost tracking table

### Week 3: Integration

- [ ] Update agent orchestrator with real services
- [ ] Update context retrieval service
- [ ] Run end-to-end integration tests
- [ ] Set up CloudWatch alarms
- [ ] Document service endpoints
- [ ] Train team on new services

---

## 📚 Service Documentation

### Service Endpoints

| Service | Endpoint | Port | Auth |
|---------|----------|------|------|
| **Neptune** | `neptune.aura.local` | 8182 | IAM |
| **OpenSearch** | `opensearch.aura.local` | 443 | IAM |
| **Bedrock** | API Gateway | - | IAM |

### Environment Variables

```bash
# Add to ~/.bashrc or deployment config
export NEPTUNE_ENDPOINT=aura-neptune-dev.cluster-XXXXX.us-east-1.neptune.amazonaws.com
export OPENSEARCH_ENDPOINT=search-aura-dev-XXXXX.us-east-1.es.amazonaws.com
export AURA_ENV=development
export AWS_DEFAULT_REGION=us-east-1
```

### Python Dependencies

```bash
# requirements.txt additions
boto3==1.34.0
gremlinpython==3.7.1
opensearch-py==2.4.0
requests-aws4auth==1.2.3
```

---

## 🔍 Troubleshooting

### Common Issues

**Issue:** "Neptune connection timeout"
- **Cause:** Security group blocking port 8182 or Neptune in wrong subnet
- **Fix:** Verify security group allows inbound 8182 from application subnet

**Issue:** "Bedrock model not available"
- **Cause:** Model access not enabled in AWS account
- **Fix:** Navigate to Bedrock console → Model access → Request access

**Issue:** "OpenSearch cluster unreachable"
- **Cause:** VPC configuration or IAM permissions
- **Fix:** Ensure cluster is in VPC mode with proper security group, verify IAM role

**Issue:** "Budget exceeded errors"
- **Cause:** Daily LLM budget set too low for development
- **Fix:** Increase budget in `src/config/bedrock_config.py`

---

## 🎯 Success Criteria

Phase 2 is complete when:

- [ ] All 4 services deployed and accessible
- [ ] Integration tests passing (100%)
- [ ] Monthly cost under $100 (target: $43)
- [ ] End-to-end autonomous remediation workflow functional
- [ ] CloudWatch alarms configured and tested
- [ ] Team trained on new services

---

## Next Steps: Phase 3

After Phase 2 completion:

1. **Git Ingestion Pipeline** - Automated repository scanning
2. **GitHub Actions Integration** - PR-based code review automation
3. **HITL Approval Dashboard** - React UI for patch review
4. **Production Optimization** - Fine-tune costs, performance, monitoring

---

**Questions or Issues?**
Refer to service-specific documentation:
- Bedrock: `src/services/bedrock_llm_service.py` (docstrings)
- Neptune: `src/services/neptune_graph_service.py`
- OpenSearch: `src/services/opensearch_vector_service.py`
- Titan: `src/services/titan_embedding_service.py`
