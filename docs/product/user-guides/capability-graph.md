# Capability Graph

**Version:** 1.0
**Last Updated:** January 2026
**Product:** Project Aura by Aenea Labs

---

## Introduction

The Capability Graph is a powerful visualization tool that displays the relationships between agents and their assigned capabilities (tools) in your Project Aura deployment. This interactive graph helps security engineers and administrators understand permission structures, identify potential security risks, and ensure compliance with separation of duties policies.

The Capability Graph implements ADR-071 (Cross-Agent Capability Graph Analysis) and provides real-time insights into your agent ecosystem's security posture.

---

## Accessing the Capability Graph

Navigate to **Security > Capability Graph** from the main navigation menu, or access it through:

- The Security Dashboard quick links
- The Agent Registry detail panel
- Direct URL: `/security/capability-graph`

**Required Permissions:** Admin or Security Engineer role

---

## Understanding the Graph Visualization

### Node Types

The graph displays two types of nodes:

| Node Type | Appearance | Description |
|-----------|------------|-------------|
| **Agents** | Large blue circles (30px radius) | Represent autonomous agents in your system |
| **Tools** | Smaller colored circles (20px radius) | Represent capabilities/tools assigned to agents |

### Node Colors

Nodes are color-coded by their classification level:

| Color | Classification | Description |
|-------|----------------|-------------|
| Blue | Agent | Autonomous agent nodes |
| Green | SAFE | Read-only operations with no side effects |
| Amber | MONITORING | Observation tools with audit trails |
| Orange | DANGEROUS | Write operations requiring approval |
| Red | CRITICAL | High-impact operations with strict controls |

### Edge Types

Edges (connections) between nodes indicate relationships:

| Edge Style | Relationship | Description |
|------------|--------------|-------------|
| Solid gray | HAS_CAPABILITY | Direct tool assignment to agent |
| Dashed amber | DELEGATES_TO | Delegation of capabilities to another agent |
| Dashed purple | INHERITS_FROM | Inherited capabilities from parent agent |
| Solid red | ESCALATION | Part of a detected privilege escalation path |

---

## Using Graph Filters

The Capability Graph includes a comprehensive filter panel to help you focus on specific aspects of your agent ecosystem.

### Agent Types Filter

Filter which types of agents are displayed in the graph:

- **Coder** - Code generation and modification agents
- **Reviewer** - Code review and analysis agents
- **Validator** - Testing and validation agents
- **Security** - Security scanning agents
- **Orchestrator** - Workflow coordination agents

**Usage:** Check/uncheck agent types to show or hide them. When all checkboxes are unchecked (empty selection), all agent types are displayed.

### Tool Classification Filter

Toggle tool classifications to filter which tools appear:

- Click a classification badge to toggle it on/off
- Active classifications are highlighted with their corresponding color
- Tools with deactivated classifications are hidden from the graph

### Risk Analysis Filters

These filters help identify potential security issues:

#### Show Escalation Paths

When enabled, highlights edges that are part of detected privilege escalation paths:

- Edges turn red with arrow markers
- Helps identify paths where lower-tier agents can reach CRITICAL capabilities
- Use with the Risk Threshold slider to filter by severity

#### Highlight Coverage Gaps

When enabled, shows an amber "?" badge on agents that:

- Have DANGEROUS or CRITICAL tools assigned
- Lack MONITORING tools for audit coverage

This helps identify agents that may need additional oversight.

#### Show Toxic Combinations

When enabled, shows a pulsing red dashed ring around nodes involved in toxic tool pairs. Toxic combinations are tool pairings that violate separation of duties, such as:

- `deployment` + `database_access`
- `iam_modify` + `production_access`
- `secrets_manager` + `deployment`
- `file_write` + `production_access`

### Risk Threshold Slider

Adjust the risk threshold (0-100%) to filter which escalation paths are highlighted:

- Set to 0% to see all potential escalation paths
- Set higher to focus only on paths with elevated risk scores
- The slider only affects the "Show Escalation Paths" filter

---

## Graph Interactions

### Zoom and Pan

| Action | Mouse | Result |
|--------|-------|--------|
| Zoom in | Scroll up or click + button | Increase zoom level |
| Zoom out | Scroll down or click - button | Decrease zoom level |
| Pan | Click and drag on background | Move the entire graph |
| Reset view | Click reset button | Return to default zoom and position |

The current zoom level is displayed between the zoom buttons (e.g., "100%").

### Fullscreen Mode

Click the fullscreen button to expand the graph to fill your entire screen:

- Press **Escape** or click the button again to exit fullscreen
- Useful for complex graphs with many nodes

### Node Selection

| Action | Interaction | Result |
|--------|-------------|--------|
| Hover | Mouse over node | Shows tooltip with node details, highlights connected nodes |
| Click | Click on node | Selects node, opens detail drawer (if available) |
| Click background | Click empty space | Deselects current node |

When a node is selected or hovered:

- Connected nodes and edges remain fully visible
- Unrelated nodes and edges are dimmed for focus
- A tooltip shows node properties

### Node Tooltips

Hovering over a node displays a tooltip with:

- **Name** - Full name of the agent or tool
- **Type** - Node type (agent or tool)
- **Classification** - Tool classification level (for tools)
- **Agent Type** - Agent category (for agents)
- **Capabilities** - Number of assigned capabilities (for agents)
- **Risk Indicators** - Warning if escalation risk detected

---

## Understanding the Legend

The legend in the bottom-left corner shows:

**Node Types Section:**
- Visual representation of each node color and its meaning

**Indicators Section (when active):**
- Escalation Path - Red edge indicator
- Coverage Gap - Amber badge with "?"
- Toxic Combo - Pulsing red dashed ring

The Indicators section only appears when the corresponding filter is enabled.

---

## Common Use Cases

### Security Audit

1. Enable **Show Escalation Paths** with Risk Threshold at 0%
2. Review all highlighted red edges
3. Click on agents in escalation paths to understand the permission chain
4. Document findings and plan remediation

### Compliance Review

1. Enable **Highlight Coverage Gaps**
2. Identify agents with amber "?" badges
3. Add MONITORING tools to agents with gaps
4. Verify separation of duties with **Show Toxic Combinations**

### Agent Configuration

1. Filter by specific **Agent Type**
2. Review assigned tools for each agent
3. Verify classification levels are appropriate
4. Check for over-provisioned permissions

### Risk Assessment

1. Set **Risk Threshold** slider to 50%
2. Enable all risk analysis filters
3. Focus on high-risk escalation paths first
4. Use node hover to understand permission chains

---

## Troubleshooting

### Graph is Empty

- Verify you have agents configured in the system
- Check if agent policies have been synchronized
- Click **Sync Policies** button to refresh data

### Filters Not Working

- Ensure at least one classification is selected
- Empty agent type selection shows all agents (this is expected)
- Clear all filters using the "Clear all" link

### Performance Issues

- Reduce visible nodes using agent type filters
- Zoom out to see full graph layout
- Use fullscreen mode for more rendering space

---

## Related Documentation

- [Agent Capability Governance](../../architecture-decisions/ADR-066-agent-capability-governance.md) - Understanding tool classifications
- [Cross-Agent Capability Graph](../../architecture-decisions/ADR-071-cross-agent-capability-graph.md) - Technical architecture
- [Patch Approval Workflows](./patch-approval.md) - HITL approval process for DANGEROUS/CRITICAL operations
- [Security Architecture](../../support/architecture/security-architecture.md) - Overall security model
