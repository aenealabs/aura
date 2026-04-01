# Knowledge Graph User Guide

The Knowledge Graph (formerly GraphRAG Explorer) provides an interactive visualization of your codebase as a knowledge graph. Access it from the **Intelligence** section in the sidebar. This guide explains how to navigate the graph, query for insights, and interpret the visual representation of your code relationships.

---

## Interface Overview

The Knowledge Graph interface consists of three main areas:

| Area | Location | Purpose |
|------|----------|---------|
| **Graph Canvas** | Center/Left (70%) | Interactive visualization of nodes and edges |
| **Query Panel** | Right side (30%) | Query input, node details, results, and metrics |
| **Header** | Top | Title, filter controls, and refresh button |

---

## Graph Navigation

### Panning (Moving the View)

- **Click and drag on empty space** to move the entire graph around
- The cursor displays as an open hand when you can pan
- While dragging, the cursor changes to a closed hand

### Zooming

**Mouse wheel zoom:**
- Scroll **up** to zoom in
- Scroll **down** to zoom out
- Zoom focuses toward your cursor position for precision navigation

**Zoom buttons (bottom-left corner):**

| Button | Action |
|--------|--------|
| **+** (Plus) | Zoom in by 20% |
| **-** (Minus) | Zoom out by 20% |
| **Expand arrows** | Reset view to default zoom and position |

**Zoom level indicator:** The current zoom percentage appears in the bottom-right corner (e.g., "100%").

### Zoom Limits

- Minimum zoom: 30%
- Maximum zoom: 300%

### Label Visibility

Node labels adjust their visibility based on zoom level to reduce visual clutter:

| Zoom Level | Label Behavior |
|------------|----------------|
| **70% and above** | Labels fully visible |
| **50% to 70%** | Labels fade out gradually |
| **Below 50%** | Labels hidden |

**Note:** Selected or hovered nodes always display their labels regardless of zoom level.

### Smart Label Positioning

Labels automatically position themselves opposite to connected nodes to avoid overlap. Each label has a semi-transparent background halo that improves readability when labels overlap with edges or other graph elements.

---

## Node Interaction

### Node Types

The graph displays five types of nodes, each with a distinct color:

| Node Type | Color | Icon Letter | Description |
|-----------|-------|-------------|-------------|
| **File** | Blue | F | Source code files in your repository |
| **Class** | Olive/Green | C | Classes and class definitions |
| **Function** | Gray | F | Functions and methods |
| **Dependency** | Amber/Yellow | D | External dependencies and packages |
| **Vulnerability** | Red | V | Security vulnerabilities (CVEs) |

### Hovering Over Nodes

When you hover over a node:
- The cursor changes from a hand to a pointer
- A glow effect appears around the node
- A tooltip appears showing the node label and type

### Selecting Nodes

**Click on a node** to select it. When selected:
- The node displays a thicker border and larger radius
- Connected edges become highlighted (thicker, full opacity)
- Full node details appear in the side panel

### Cursor States

| Cursor | Meaning |
|--------|---------|
| Open hand (grab) | Default state - you can pan the graph |
| Closed hand (grabbing) | Currently panning/dragging the graph |
| Pointer | Hovering over a node - click to select |

---

## Query Interface

The query panel at the top-right allows you to search the knowledge graph using natural language.

### Entering Queries

1. Click the search input field
2. Type your query (natural language or Cypher)
3. Click **Execute** or press Enter

### Suggested Queries

When you focus on the search input, a dropdown appears with pre-built queries:

- "Find all SQL injection vulnerabilities"
- "Show classes with high cyclomatic complexity"
- "List functions that access sensitive data"
- "Find unused dependencies"
- "Show all CVEs affecting authentication"

Click any suggestion to populate the search field.

### Query Results

After executing a query:
- Results appear below the query input
- Each result shows the node icon, label, and type
- Click any result to select that node in the graph
- The result count displays in the header (e.g., "5 nodes found")

---

## Filtering

### Accessing Filters

Click the **Filters** button in the header to expand the filter panel.

### Node Type Filters

Toggle visibility for each node type:

| Filter | Effect When Disabled |
|--------|---------------------|
| **File** | Hides all file nodes |
| **Class** | Hides all class nodes |
| **Function** | Hides all function nodes |
| **Dependency** | Hides all dependency nodes |
| **Vulnerability** | Hides all vulnerability nodes |

- Enabled filters show with a colored border and full opacity
- Disabled filters appear dimmed (50% opacity)
- Edges are automatically hidden when their connected nodes are filtered out

### Filter Indicators

Each filter button displays:
- A colored dot matching the node type color
- The node type label

---

## Legend and Metrics

### Legend Panel

Located in the **top-left corner** of the graph canvas, the legend shows:
- Color-coded dots for each node type
- Labels identifying what each color represents

### Graph Metrics Panel

Located at the **bottom of the query panel**, metrics include:

| Metric | Description |
|--------|-------------|
| **Nodes** | Total number of nodes currently visible |
| **Edges** | Total number of edges (relationships) visible |
| **Classes** | Count of class nodes |
| **CVEs** | Count of vulnerability nodes |

Metrics update automatically when filters are applied.

---

## Node Details Panel

When a node is selected, the detail panel displays comprehensive information including descriptions, properties, relationships, and quick actions.

### Panel Layout

The enhanced Node Detail Panel contains six sections:

| Section | Description |
|---------|-------------|
| **Header** | Node icon, name, type, and close button |
| **Description** | AI-generated summary and impact analysis |
| **Properties** | Type-specific metadata (methods, complexity, etc.) |
| **Documentation** | External documentation link (dependencies and vulnerabilities only) |
| **Action Bar** | Quick actions for Center, Copy ID, Filter, and Open |
| **Relationships** | Collapsible lists of incoming, outgoing, and vulnerability connections |

### Description Section

Each node displays two types of descriptions:

- **Summary**: A 1-2 sentence explanation of what the node does (e.g., "Handles user authentication and session management for the web API.")
- **Impact Summary**: Shows downstream effects and dependencies (e.g., "Central controller affecting 8 downstream services.")

### Relationships Section

Relationships are grouped into collapsible sections:

| Section | Description |
|---------|-------------|
| **Incoming** | Nodes that connect *to* this node (imports, calls, dependencies) |
| **Outgoing** | Nodes this node connects *to* (what it calls, imports, or depends on) |
| **Affected by** | Vulnerabilities that impact this node |

Click any relationship to navigate directly to that connected node. If more than 5 relationships exist, click "Show N more" to expand the list.

### Action Bar

Quick actions available for each node:

| Action | Icon | Description | Keyboard |
|--------|------|-------------|----------|
| **Center** | Arrows | Pan/zoom to center the node in view | `C` |
| **Copy ID** | Clipboard | Copy the node's unique ID to clipboard | - |
| **Filter** | Funnel | Show only nodes connected to this one | `F` |
| **Open** | External link | Open source file (code nodes only) | `O` |

### Type-Specific Properties

#### File Nodes

| Field | Description |
|-------|-------------|
| **Path** | Full file path in the repository |
| **Lines** | Total lines in the file |

#### Class Nodes

| Field | Description |
|-------|-------------|
| **Methods** | Number of methods in the class |
| **Attributes** | Number of class attributes |

#### Function Nodes

| Field | Description |
|-------|-------------|
| **Complexity** | Cyclomatic complexity score (color-coded) |
| **Call Count** | Number of times the function is called |

Complexity is color-coded:
- Green: Low (1-5)
- Amber: Medium (6-10)
- Red: High (>10)

#### Dependency Nodes

| Field | Description |
|-------|-------------|
| **Version** | Package version number |
| **Risk** | Security risk assessment (low/medium/high) |

#### Vulnerability Nodes

| Field | Description |
|-------|-------------|
| **Severity** | Vulnerability severity (critical/high/medium/low) |
| **CWE** | Common Weakness Enumeration identifier |

### Documentation Links

For **Dependency** and **Vulnerability** nodes, the panel displays an external documentation link section:

#### Available Documentation

When official documentation exists:

```
┌─────────────────────────────────────────────┐
│  📄 Official Documentation ↗                │
│     spring.io/projects/spring-boot          │
└─────────────────────────────────────────────┘
```

- Click to open the official vendor documentation in a new tab
- The domain is displayed for transparency
- Links use `rel="noopener noreferrer"` for security

#### Unavailable Documentation

When no official documentation is available:

```
┌─────────────────────────────────────────────┐
│  ○ No official documentation available      │
│    Search on: Internet ↗                    │
└─────────────────────────────────────────────┘
```

- A neutral indicator shows documentation is unavailable
- A generic search link helps you find information
- Avoids recommending unofficial or potentially outdated sources

**Note:** Documentation links only appear for dependency and vulnerability nodes. File, class, and function nodes do not display this section since they represent code within your repository.

---

## Edge Types

Edges (curved lines connecting nodes) represent relationships between code elements. All edges use quadratic Bezier curves instead of straight lines, which improves readability and reduces visual clutter when multiple edges cross.

| Edge Type | Color | Line Style | Meaning |
|-----------|-------|------------|---------|
| **Imports** | Blue | Solid | File imports or uses another component |
| **Extends** | Olive | Solid | Class inheritance relationship |
| **Implements** | Purple | Solid | Interface implementation |
| **Calls** | Gray | Solid | Function or method invocation |
| **Depends On** | Amber | Solid | Dependency relationship |
| **Affects** | Red | Dashed | Vulnerability impacts a component |

### Node Spacing

The graph enforces a minimum distance of 80 pixels between nodes. A stronger repulsion force prevents node overlap, making dense graphs easier to read.

---

## Fullscreen Mode

Fullscreen mode maximizes the graph canvas to use the entire browser window, providing more space for exploring large graphs.

### Entering Fullscreen

Use either method:
- Click the **Expand** button in the header
- Press the `F` key on your keyboard

### Fullscreen Interface

When in fullscreen mode, the interface adapts:

| Element | Location | Description |
|---------|----------|-------------|
| **Collapsible Sidebar** | Right side | Query panel and node details (toggle with chevron button) |
| **Legend Panel** | Top-left corner | Node type color reference |
| **Control Bar** | Bottom | Zoom controls and keyboard shortcut hints |

### Sidebar Panel

The sidebar panel contains the query interface and node details. Click the chevron button on the left edge of the sidebar to collapse or expand it. When collapsed, the graph canvas uses the full width of the screen.

### Exiting Fullscreen

Press the `Escape` key to exit fullscreen mode and return to the standard interface layout.

---

## Keyboard and Mouse Reference

| Action | Input |
|--------|-------|
| Pan the graph | Click and drag on empty space |
| Zoom in | Scroll wheel up |
| Zoom out | Scroll wheel down |
| Select node | Click on node |
| Execute query | Enter (when focused on search) |
| Enter fullscreen | `F` key or click Expand button |
| Exit fullscreen | `Escape` key |
| Center selected node | `C` key (when node selected) |
| Copy node ID | Click Copy ID in action bar |
| Filter connected nodes | Click Filter in action bar |
| Open source file | Click Open in action bar (code nodes) |
| Navigate to connected node | Click relationship item in panel |

---

## Tips for Effective Use

### Finding Vulnerabilities Quickly

1. Use the query "Find all SQL injection vulnerabilities"
2. Or filter to show only Vulnerability nodes
3. Look for red nodes with dashed edges to see what they affect

### Tracing Code Dependencies

1. Select a file or class node
2. Review the **Relationships** section in the detail panel
3. Click on any incoming or outgoing relationship to navigate directly to that node
4. Use the **Filter** action to isolate just the connected nodes in the graph

### Identifying High-Risk Code

1. Query for "functions with complexity > 10"
2. Look for functions connected to vulnerability nodes
3. Check the Call Count metric for heavily-used functions

### Performance Optimization

- Use filters to reduce visual clutter when exploring large graphs
- Zoom out for a high-level view, zoom in for details
- Reset the view if you lose orientation

---

## Related Guides

| Guide | Description |
|-------|-------------|
| [Getting Started](./getting-started.md) | Platform overview and first steps |
| [Agent System](./agent-system.md) | How AI agents analyze your code |
| [Security and Compliance](./security-compliance.md) | Understanding security findings |

---

## Glossary

| Term | Definition |
|------|------------|
| **CKGE** | Code Knowledge Graph Explorer |
| **GraphRAG** | Graph-based Retrieval-Augmented Generation |
| **Node** | A visual element representing a code entity (file, class, function, etc.) |
| **Edge** | A line connecting two nodes, representing a relationship |
| **Cyclomatic Complexity** | A metric measuring the number of linearly independent paths through code |
| **CVE** | Common Vulnerabilities and Exposures identifier |
| **CWE** | Common Weakness Enumeration - a category of vulnerability |
