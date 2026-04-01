/**
 * GraphRAG Context Panel Widget (P0 Key Differentiator)
 *
 * Displays code relationships from Neptune graph for the current cell.
 * Shows how the current code connects to other parts of the codebase
 * through imports, calls, and references.
 *
 * ADR-048 Phase 2: Jupyter Extension
 */

import { Widget } from '@lumino/widgets';
import { Cell } from '@jupyterlab/cells';
import { AuraApiClient, GraphNode, GraphEdge, GraphContextResponse } from '../api/client';

/**
 * Node type icon mapping
 */
const NODE_ICONS: Record<string, { label: string; color: string }> = {
    file: { label: 'F', color: '#4fc3f7' },
    class: { label: 'C', color: '#ff8a65' },
    function: { label: 'fn', color: '#ba68c8' },
    method: { label: 'M', color: '#9575cd' },
    module: { label: 'mod', color: '#81c784' },
    variable: { label: 'V', color: '#64b5f6' },
    import: { label: 'I', color: '#ffb74d' },
    cell: { label: '[]', color: '#90caf9' },
};

/**
 * GraphRAG Context Panel
 */
export class GraphContextPanel extends Widget {
    private apiClient: AuraApiClient;
    private currentPath: string | null = null;
    private currentCellId: string | null = null;
    private graphData: GraphContextResponse | null = null;
    private depth: number = 2;

    constructor(apiClient: AuraApiClient) {
        super();
        this.apiClient = apiClient;
        this.addClass('aura-graph-context-panel');
        this.initializeUI();
    }

    /**
     * Initialize the panel UI
     */
    private initializeUI(): void {
        this.node.innerHTML = `
            <div class="aura-panel-header">
                <h3>Code Context</h3>
                <div class="aura-panel-controls">
                    <select class="aura-depth-select" title="Traversal Depth">
                        <option value="1">Depth: 1</option>
                        <option value="2" selected>Depth: 2</option>
                        <option value="3">Depth: 3</option>
                    </select>
                    <button class="aura-refresh-btn" title="Refresh">↻</button>
                </div>
            </div>
            <div class="aura-graph-stats"></div>
            <div class="aura-graph-container">
                <div class="aura-empty-state">
                    <p>Select a cell to see its code relationships</p>
                    <p class="aura-hint">The graph shows imports, function calls, and references</p>
                </div>
            </div>
            <div class="aura-relationships-summary"></div>
        `;

        // Attach event listeners
        const depthSelect = this.node.querySelector('.aura-depth-select') as HTMLSelectElement;
        depthSelect?.addEventListener('change', (e) => {
            this.depth = parseInt((e.target as HTMLSelectElement).value);
            this.refresh();
        });

        const refreshBtn = this.node.querySelector('.aura-refresh-btn') as HTMLButtonElement;
        refreshBtn?.addEventListener('click', () => this.refresh());
    }

    /**
     * Update panel for a specific cell
     */
    async updateForCell(cell: Cell): Promise<void> {
        // Extract cell info
        const cellId = cell.model.id;
        const source = cell.model.sharedModel.getSource();

        // Get notebook path from cell's parent
        const notebook = cell.parent;
        const path = (notebook as any)?.context?.path;

        if (!path) {
            return;
        }

        this.currentPath = path;
        this.currentCellId = cellId;

        await this.loadGraphContext();
    }

    /**
     * Refresh the current view
     */
    async refresh(): Promise<void> {
        if (this.currentPath && this.currentCellId) {
            await this.loadGraphContext();
        }
    }

    /**
     * Load graph context from API
     */
    private async loadGraphContext(): Promise<void> {
        if (!this.currentPath) {
            return;
        }

        const container = this.node.querySelector('.aura-graph-container') as HTMLElement;

        try {
            // Show loading state
            container.innerHTML = '<div class="aura-loading">Loading graph context...</div>';

            // Fetch graph context
            this.graphData = await this.apiClient.getGraphContext({
                file_path: this.currentPath,
                cell_id: this.currentCellId || undefined,
                depth: this.depth,
            });

            // Render the graph
            this.renderGraph();
        } catch (error) {
            console.error('Failed to load graph context:', error);
            container.innerHTML = `
                <div class="aura-error">
                    Failed to load graph context: ${error}
                </div>
            `;
        }
    }

    /**
     * Render the graph visualization
     */
    private renderGraph(): void {
        if (!this.graphData) {
            return;
        }

        const { nodes, edges, relationships, query_duration_ms } = this.graphData;
        const container = this.node.querySelector('.aura-graph-container') as HTMLElement;
        const statsContainer = this.node.querySelector('.aura-graph-stats') as HTMLElement;
        const relContainer = this.node.querySelector('.aura-relationships-summary') as HTMLElement;

        // Show empty state if no nodes
        if (nodes.length === 0) {
            container.innerHTML = `
                <div class="aura-empty-state">
                    <p>No code relationships found for this cell</p>
                </div>
            `;
            statsContainer.innerHTML = '';
            relContainer.innerHTML = '';
            return;
        }

        // Render stats
        statsContainer.innerHTML = `
            <div class="aura-stat"><strong>${nodes.length}</strong> nodes</div>
            <div class="aura-stat"><strong>${edges.length}</strong> edges</div>
            <div class="aura-stat"><strong>${query_duration_ms.toFixed(0)}</strong>ms</div>
        `;

        // Render node list
        container.innerHTML = `
            <ul class="aura-node-list">
                ${nodes.map(node => this.renderNodeItem(node)).join('')}
            </ul>
        `;

        // Render relationships summary
        if (Object.keys(relationships).length > 0) {
            relContainer.innerHTML = `
                <h4>Relationships</h4>
                <div class="aura-relationship-list">
                    ${Object.entries(relationships).map(([type, count]) => `
                        <div class="aura-relationship-item">
                            <span class="aura-relationship-type">${type.replace('_', ' ')}</span>
                            <span class="aura-relationship-count">${count}</span>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            relContainer.innerHTML = '';
        }

        // Attach click handlers for node navigation
        container.querySelectorAll('.aura-node-item').forEach(item => {
            item.addEventListener('click', () => {
                const nodeId = (item as HTMLElement).dataset.nodeId;
                this.navigateToNode(nodeId!);
            });
        });
    }

    /**
     * Render a single node item
     */
    private renderNodeItem(node: GraphNode): string {
        const isFocused = node.id === this.graphData?.focus_node_id;
        const icon = NODE_ICONS[node.type] || { label: '?', color: '#999' };
        const location = node.line_start ? `:${node.line_start}` : '';
        const fileName = node.file_path ? this.getFileName(node.file_path) : '';

        return `
            <li class="aura-node-item${isFocused ? ' aura-node-focused' : ''}"
                data-node-id="${node.id}">
                <span class="aura-node-icon" style="background: ${icon.color}">
                    ${icon.label}
                </span>
                <span class="aura-node-name">${this.escapeHtml(node.name)}</span>
                ${fileName ? `
                    <span class="aura-node-location">${this.escapeHtml(fileName)}${location}</span>
                ` : ''}
            </li>
        `;
    }

    /**
     * Navigate to a node's location
     */
    private navigateToNode(nodeId: string): void {
        if (!this.graphData) {
            return;
        }

        const node = this.graphData.nodes.find(n => n.id === nodeId);
        if (!node) {
            return;
        }

        // TODO: Implement navigation to file/cell/line
        console.log('Navigate to node:', node);
    }

    /**
     * Get filename from path
     */
    private getFileName(path: string): string {
        return path.split('/').pop() || path;
    }

    /**
     * Escape HTML entities
     */
    private escapeHtml(text: string): string {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}
