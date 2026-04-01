# Agent System Guide

This guide explains how Aura's multi-agent system works, including the different agent types, how they collaborate, and how to monitor their activity.

---

## Agent Architecture Overview

Aura uses a coordinated multi-agent system where specialized AI agents work together to analyze code, generate fixes, and validate solutions.

```
                    +----------------------------------+
                    |       MetaOrchestrator           |
                    |   (Coordinates All Agents)       |
                    +-----------------|----------------+
                                      |
          +---------------------------+---------------------------+
          |                           |                           |
          v                           v                           v
    +-----------+              +-----------+              +-----------+
    |  Coder    |              | Reviewer  |              | Validator |
    |  Agent    |              |  Agent    |              |  Agent    |
    +-----------+              +-----------+              +-----------+
          |                           |                           |
          v                           v                           v
    Code Generation            Security Review            Sandbox Testing
```

---

## Core Agents

### Coder Agent

The Coder Agent generates code fixes for identified vulnerabilities.

**Capabilities**:
- Analyzes vulnerability context and code structure
- Generates patch recommendations
- Provides explanations for each change
- Suggests multiple fix approaches when appropriate

**Input**:
```
- Vulnerability details
- Affected code location
- Code context from GraphRAG
- Security policies
```

**Output**:
```
- Code patch (diff format)
- Explanation of changes
- Risk assessment
- Test recommendations
```

### Reviewer Agent

The Reviewer Agent performs security analysis of generated patches.

**Capabilities**:
- Security vulnerability assessment
- Code quality review
- Compliance validation
- Best practice checking

**Features**:
- **Self-Reflection**: Reviews its own output for false positives
- **Multi-Pass Analysis**: Iterates until confidence threshold met
- **Context Awareness**: Understands code relationships via graph

**Review Categories**:

| Category | What It Checks |
|----------|----------------|
| Security | OWASP Top 10, injection flaws, auth issues |
| Quality | Clean code, SOLID principles, readability |
| Compliance | Framework-specific requirements |
| Performance | Resource usage, efficiency |

### Validator Agent

The Validator Agent tests patches in isolated sandbox environments.

**Capabilities**:
- Sandbox provisioning and management
- Test execution
- Result analysis
- Rollback coordination

**Validation Process**:
1. Provision isolated sandbox
2. Apply patch to test environment
3. Run automated tests
4. Analyze results
5. Report findings
6. Clean up sandbox

---

## Specialized Agents

### Security Agent

Advanced security analysis capabilities:

| Component | Function |
|-----------|----------|
| PR Security Scanner | SAST, secret detection, SCA, IaC security |
| Dynamic Attack Planner | MITRE ATT&CK-based threat modeling |
| Org Standards Validator | Custom rule enforcement |

### DevOps Agent

Operational intelligence and automation:

| Component | Function |
|-----------|----------|
| Deployment History Correlator | Links incidents to deployments |
| Resource Topology Mapper | Infrastructure dependency tracking |
| Incident Pattern Analyzer | Root cause analysis |

### Transform Agent

Legacy code modernization:

| Component | Function |
|-----------|----------|
| COBOL Parser | Legacy system analysis |
| .NET Parser | C#/VB.NET code understanding |
| Cross-Language Translator | COBOL to Python, VB.NET to C# |
| Architecture Reimaginer | Microservices decomposition |

### Runtime Incident Agent

Code-aware incident response:

- Correlates runtime errors with code changes
- Performs automated root cause analysis
- Integrates with HITL for remediation approval
- Generates incident reports

### Browser Tool Agent

Web automation capabilities:

- Multi-page navigation
- Form filling
- Screenshot capture
- JavaScript execution

### Code Interpreter Agent

Multi-language code execution:

| Languages Supported |
|---------------------|
| Python, JavaScript, TypeScript |
| Go, Rust, Java, C++ |
| Ruby, PHP, Shell, SQL |

---

## Agent Orchestration

### MetaOrchestrator

The MetaOrchestrator coordinates all agent activities:

```
Request Received
       |
       v
+------------------+
| Parse Request    |
| Load Context     |
+---------|--------+
          |
          v
+------------------+
| Memory Phase     |  <-- Load relevant context from Titan Memory
| (Optional)       |
+---------|--------+
          |
          v
+------------------+
| Agent Selection  |  <-- Choose appropriate agents
+---------|--------+
          |
          v
+------------------+
| Parallel/Serial  |  <-- Execute agents based on dependencies
| Execution        |
+---------|--------+
          |
          v
+------------------+
| Result Synthesis |  <-- Combine agent outputs
+---------|--------+
          |
          v
+------------------+
| Learn Phase      |  <-- Store experience in memory
| (Optional)       |
+------------------+
```

### Agent Spawning

The MetaOrchestrator dynamically spawns agents based on:

- Task complexity
- Required capabilities
- Resource availability
- Priority level

### Workflow Phases

| Phase | Description |
|-------|-------------|
| MEMORY | Load relevant context from neural memory |
| ANALYZE | Understand the problem scope |
| PLAN | Determine approach and agent selection |
| EXECUTE | Run agent workflows |
| VALIDATE | Verify results |
| LEARN | Store outcomes for future reference |

---

## Agent Optimization Features

### Semantic Caching

Reduces LLM costs by caching similar queries:

- **How It Works**: Queries are embedded and compared for similarity
- **Hit Threshold**: 92% similarity required for cache hit
- **TTLs by Query Type**:
  - Vulnerability queries: 24 hours
  - Review queries: 12 hours
  - Generation queries: 1 hour

### Self-Reflection

The Reviewer Agent critiques its own output:

```
Initial Review
     |
     v
Self-Critique  <--+
     |            |
     v            |
Confidence OK? ---+
     |  No (iterate up to 3 times)
     | Yes
     v
Final Output
```

**Benefits**:
- 30% fewer false positives
- Higher confidence outputs
- Better explanations

### A2AS Security Framework

Agent-to-Agent Security protects against malicious inputs:

| Layer | Protection |
|-------|------------|
| Injection Filter | Blocks prompt/code/SQL injection |
| Command Verifier | HMAC-signed command validation |
| Sandbox Enforcer | Runtime restrictions |
| Behavioral Analysis | Anomaly detection |

---

## Agent Deployment Modes

Choose how agents are deployed based on your needs:

### On-Demand Mode

- **Cost**: Lowest (pay-per-use)
- **Behavior**: EKS jobs created per request
- **Latency**: Cold start delay
- **Best For**: Low-volume usage

### Warm Pool Mode

- **Cost**: Low (fixed)
- **Behavior**: Always-on replica
- **Latency**: Near-instant
- **Best For**: Consistent workloads

### Hybrid Mode

- **Cost**: Low + burst
- **Behavior**: Warm pool with burst capacity
- **Latency**: Instant with overflow handling
- **Best For**: Variable workloads

### Configuring Deployment Mode

1. Navigate to **Settings > Orchestrator**
2. Select your preferred mode
3. Configure mode-specific settings
4. Click **Apply**

---

## Monitoring Agents

### Agent Activity Dashboard

The main dashboard shows:

- Active agent count
- Tasks in progress
- Completion rates
- Error rates

### Real-Time Status

Check individual agent status:

1. Navigate to **Agents** in the sidebar
2. View the Agent Registry
3. Click on any agent to see:
   - Current status
   - Recent activity
   - Performance metrics
   - Error logs

### Performance Metrics

| Metric | Description | Target |
|--------|-------------|--------|
| Task Completion Rate | Successful completions | > 95% |
| Average Latency | Time to complete | < 30 seconds |
| Error Rate | Failed tasks | < 5% |
| Cache Hit Rate | Semantic cache efficiency | > 60% |

### Agent Health Checks

The system continuously monitors agent health:

| Check | Frequency |
|-------|-----------|
| Liveness | Every 10 seconds |
| Readiness | Every 30 seconds |
| Resource Usage | Every minute |

---

## Using the Agent Registry

### Viewing Available Agents

The Agent Registry shows all available agents:

| Category | Agents |
|----------|--------|
| Internal | Coder, Reviewer, Validator, Security, DevOps, Transform |
| External | Connected via A2A protocol |
| Marketplace | Community and third-party agents |

### Connecting External Agents

1. Navigate to **Agents > Registry**
2. Click **Connect External Agent**
3. Provide the A2A endpoint URL
4. Configure authentication
5. Test the connection
6. Enable the agent

### Agent Capabilities

Each agent exposes capabilities via a standard interface:

```
Agent Capabilities:
- Name and description
- Supported input types
- Output formats
- Resource requirements
- Security requirements
```

---

## Evaluation and Quality

### Agent Evaluation Service

Aura includes 13 built-in evaluators to assess agent quality:

| Evaluator | What It Measures |
|-----------|------------------|
| Accuracy | Correctness of outputs |
| Relevance | Output matches request |
| Completeness | All requirements addressed |
| Security | No security issues introduced |
| Performance | Efficiency of solutions |
| Consistency | Reliable outputs over time |

### A/B Testing

Test different agent configurations:

1. Define experiment parameters
2. Split traffic between variants
3. Measure outcomes
4. Choose the winner

### Regression Detection

The system automatically detects:

- Quality degradation
- Performance regression
- Increased error rates
- Behavioral changes

---

## Cognitive Memory System

### Titan Neural Memory

Agents have access to a cognitive memory system:

**Features**:
- Test-time training (TTT) for adaptation
- Long-term pattern storage
- Experience replay
- Surprise-driven learning

**Memory Types**:

| Type | Purpose |
|------|---------|
| Episodic | Specific past interactions |
| Semantic | General knowledge patterns |
| Working | Current task context |

### How Memory Improves Agents

```
New Request
     |
     v
+------------------+
| Load Relevant    |
| Memories         |
+---------|--------+
          |
          v
+------------------+
| Enhanced Context |
| for Agent        |
+---------|--------+
          |
          v
+------------------+
| Better Decision  |
| Making           |
+---------|--------+
          |
          v
+------------------+
| Store Outcome    |
| for Future       |
+------------------+
```

---

## Best Practices

### For Optimal Agent Performance

1. **Provide Clear Context**: Include relevant code and requirements
2. **Use Appropriate Autonomy**: Match HITL level to risk
3. **Monitor Metrics**: Track performance over time
4. **Review Rejections**: Understand why patches are rejected
5. **Leverage Memory**: Let agents learn from outcomes

### For Security

1. **Enable A2AS**: Protect against malicious inputs
2. **Use Guardrails**: Critical operations always need approval
3. **Audit Agent Actions**: Review logs regularly
4. **Limit External Agents**: Vet before connecting

### For Cost Optimization

1. **Use Semantic Caching**: Reduce redundant LLM calls
2. **Choose Right Deployment Mode**: Match usage patterns
3. **Set Budget Limits**: Control MCP costs
4. **Review Usage Reports**: Identify optimization opportunities

---

## Related Guides

| Guide | Topic |
|-------|-------|
| [Getting Started](./getting-started.md) | Platform basics |
| [Configuration](./configuration.md) | Agent settings |
| [Monitoring](./monitoring-observability.md) | Observability details |
| [Troubleshooting](./troubleshooting.md) | Agent issue resolution |
