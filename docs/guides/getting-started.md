# Getting Started with Aura Platform

Welcome to the Aura Platform - an autonomous AI-powered code intelligence platform that helps enterprises detect vulnerabilities, generate patches, and maintain code quality across their entire codebase.

---

## What is Aura?

Aura is an enterprise-grade platform that combines multiple AI agents to automatically:

- **Detect Vulnerabilities**: Scan your codebase for security issues using advanced pattern recognition and AI analysis
- **Generate Patches**: Create fix recommendations with detailed explanations
- **Test in Sandboxes**: Validate patches in isolated environments before deployment
- **Enable Human Review**: Provide Human-in-the-Loop (HITL) approval workflows for all critical changes

```
                                Your Code
                                    |
                                    v
                    +-------------------------------+
                    |       Aura Platform           |
                    |                               |
                    |  +--------+    +----------+   |
                    |  | Coder  |<-->| Reviewer |   |
                    |  | Agent  |    |  Agent   |   |
                    |  +--------+    +----------+   |
                    |       |              |        |
                    |       v              v        |
                    |  +-----------------------+    |
                    |  |   Validator Agent     |    |
                    |  +-----------------------+    |
                    |              |                |
                    +--------------|----------------+
                                   |
                                   v
                    +-------------------------------+
                    |    Sandbox Testing            |
                    +-------------------------------+
                                   |
                                   v
                    +-------------------------------+
                    |    Human Approval (HITL)      |
                    +-------------------------------+
                                   |
                                   v
                              Secure Code
```

---

## Quick Start

### Step 1: Access the Platform

Navigate to your Aura deployment URL:

- **Development**: `https://app.aenealabs.com`
- **API Endpoint**: `https://api.aenealabs.com`

### Step 2: Sign In

1. Click **Sign In** on the login page
2. Enter your credentials (authenticated via AWS Cognito)
3. You will be redirected to the Dashboard

### Step 3: Navigate the Dashboard

The main dashboard provides an overview of your platform status:

| Section | Description |
|---------|-------------|
| **Vulnerabilities** | Active security findings across your repositories |
| **Pending Approvals** | Patches awaiting human review |
| **Agent Activity** | Real-time status of AI agents |
| **Security Alerts** | Critical security notifications |

---

## Core Concepts

### Agents

Aura uses specialized AI agents that work together:

| Agent | Role | What It Does |
|-------|------|--------------|
| **Coder Agent** | Fix Generation | Analyzes vulnerabilities and generates code patches |
| **Reviewer Agent** | Security Review | Reviews patches for security issues and best practices |
| **Validator Agent** | Testing | Tests patches in sandboxes to ensure they work |

### Autonomy Levels

Your organization can configure how much human oversight is required:

| Level | Description | When to Use |
|-------|-------------|-------------|
| **Full HITL** | All operations require human approval | Defense contractors, healthcare, financial services |
| **Critical HITL** | Only HIGH/CRITICAL severity needs approval | Enterprise standard |
| **Audit Only** | Decisions are logged but not blocked | Internal tools with monitoring |
| **Full Autonomous** | Fully automated operation | Development/test environments |

### Integration Modes

Aura supports three deployment configurations:

| Mode | Description | Best For |
|------|-------------|----------|
| **Defense Mode** | Air-gap compatible, no external dependencies | GovCloud, CMMC L3, classified environments |
| **Enterprise Mode** | Full external integrations (Slack, Jira, GitHub) | Commercial enterprises |
| **Hybrid Mode** | Selective integrations with approval controls | Balanced security/productivity |

---

## Your First Vulnerability Scan

### From the Dashboard

1. Navigate to **Vulnerabilities** in the sidebar
2. Click **New Scan**
3. Select the repository you want to scan
4. Choose the scan type:
   - **Quick Scan**: Fast analysis of recent changes
   - **Full Scan**: Comprehensive codebase analysis
5. Click **Start Scan**

### Viewing Results

After the scan completes:

1. Review the list of findings sorted by severity
2. Click on any finding to see:
   - Vulnerability description
   - Affected code location
   - Recommended fix
   - CVSS score and compliance impact

### Requesting a Patch

1. From a vulnerability detail page, click **Generate Patch**
2. The Coder Agent will analyze the issue and create a fix
3. The patch goes through review and validation
4. Once ready, it appears in your **Pending Approvals** queue

---

## Approving Patches

### The Approval Workflow

```
Patch Generated --> Sandbox Testing --> Review Queue --> Human Approval --> Deployment
```

### Steps to Approve

1. Navigate to **Approvals** in the sidebar
2. Review the pending patches list
3. Click on a patch to see:
   - Code diff showing changes
   - Test results from sandbox validation
   - Security scan results
   - Risk assessment
4. Choose an action:
   - **Approve**: Accept the patch for deployment
   - **Reject**: Decline with feedback
   - **Request Changes**: Send back for modifications

### Approval Requirements

Depending on your organization's policy:

- Some patches may require multiple approvers
- Critical patches may require senior approval
- Low-severity patches may be auto-approved after testing

---

## Using the Chat Assistant

Aura includes an AI-powered assistant to help you:

### Accessing the Assistant

Click the chat icon in the bottom-right corner of any page.

### What You Can Ask

| Request Type | Example |
|--------------|---------|
| **Vulnerability Info** | "Show me critical vulnerabilities in the auth module" |
| **Agent Status** | "What agents are currently running?" |
| **Approval Help** | "What approvals are pending for my team?" |
| **Documentation** | "How do I configure HITL settings?" |
| **Reports** | "Generate a security report for last week" |

### Tips for Best Results

- Be specific about what you need
- Include repository or component names when relevant
- Ask follow-up questions to drill deeper

---

## Configuring Your Settings

### Accessing Settings

1. Click **Settings** in the sidebar (gear icon)
2. Navigate between tabs:
   - **Integration Mode**: Defense/Enterprise/Hybrid
   - **HITL Settings**: Approval requirements
   - **MCP Configuration**: External tool connections
   - **Security**: Log retention, isolation levels
   - **Compliance**: Compliance profile selection

### Common Configurations

#### For Defense/Government Users

```
Integration Mode: Defense
Autonomy Level: Full HITL
Log Retention: 365 days (FedRAMP)
Sandbox Isolation: Full
```

#### For Commercial Enterprises

```
Integration Mode: Enterprise
Autonomy Level: Critical HITL
Log Retention: 90 days (CMMC L2)
External Tools: Slack, Jira, GitHub enabled
```

---

## Next Steps

Now that you understand the basics, explore these guides:

| Guide | Learn About |
|-------|-------------|
| [Security and Compliance](./security-compliance.md) | HITL workflows, compliance frameworks |
| [Agent System](./agent-system.md) | How agents work together |
| [Configuration](./configuration.md) | Detailed settings options |
| [Integrations](./integrations.md) | Connecting external tools |

---

## Getting Help

### In-Platform Support

- Use the **Chat Assistant** for immediate help
- Check **Notifications** for system updates

### Documentation

- Full documentation: `docs/` directory
- API Reference: [API Reference Guide](./api-reference.md)

### Contact

For enterprise support inquiries, contact your Aura account representative.

---

## Glossary

| Term | Definition |
|------|------------|
| **Agent** | An AI component that performs a specific task (coding, reviewing, validating) |
| **HITL** | Human-in-the-Loop - requiring human approval for operations |
| **Sandbox** | An isolated environment for testing patches safely |
| **GraphRAG** | Graph-based Retrieval-Augmented Generation for code understanding |
| **MCP** | Model Context Protocol - standard for AI tool integrations |
| **Guardrails** | Safety controls that always require human approval |
