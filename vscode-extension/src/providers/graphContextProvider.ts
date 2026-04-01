/**
 * GraphRAG Context Panel Provider (ADR-048 P0 - Key Differentiator)
 *
 * Provides a webview panel that visualizes code relationships from Neptune graph.
 * Shows how the current file/function connects to other parts of the codebase
 * through calls, imports, inheritance, and references.
 *
 * This is Aura's unique value proposition - competitors don't have Neptune-powered
 * code relationship visualization in their IDE extensions.
 */

import * as vscode from 'vscode';
import { AuraApiClient, GraphContextResponse, GraphNode, GraphEdge } from '../api/client';

export class GraphContextPanelProvider implements vscode.WebviewViewProvider {
    public static readonly viewType = 'aura-graph-context';

    private _view?: vscode.WebviewView;
    private _currentFilePath?: string;
    private _graphData?: GraphContextResponse;

    constructor(
        private readonly _extensionUri: vscode.Uri,
        private readonly _apiClient: AuraApiClient
    ) {}

    public resolveWebviewView(
        webviewView: vscode.WebviewView,
        _context: vscode.WebviewViewResolveContext,
        _token: vscode.CancellationToken
    ): void {
        this._view = webviewView;

        webviewView.webview.options = {
            enableScripts: true,
            localResourceRoots: [this._extensionUri],
        };

        webviewView.webview.html = this._getHtmlForWebview(webviewView.webview);

        // Handle messages from the webview
        webviewView.webview.onDidReceiveMessage((message) => {
            switch (message.command) {
                case 'navigateToNode':
                    this._navigateToNode(message.nodeId);
                    break;
                case 'refresh':
                    this.refresh();
                    break;
                case 'setDepth':
                    this._loadGraphContext(this._currentFilePath, undefined, message.depth);
                    break;
            }
        });
    }

    /**
     * Update the panel for a new file
     */
    public async updateForFile(filePath: string, lineNumber?: number): Promise<void> {
        this._currentFilePath = filePath;
        await this._loadGraphContext(filePath, lineNumber);
    }

    /**
     * Refresh the current view
     */
    public async refresh(): Promise<void> {
        if (this._currentFilePath) {
            await this._loadGraphContext(this._currentFilePath);
        }
    }

    /**
     * Load graph context from API
     */
    private async _loadGraphContext(filePath?: string, lineNumber?: number, depth: number = 2): Promise<void> {
        if (!this._view || !filePath) {
            return;
        }

        try {
            // Show loading state
            this._view.webview.postMessage({
                command: 'setLoading',
                loading: true,
            });

            // Fetch graph context
            this._graphData = await this._apiClient.getGraphContext({
                file_path: filePath,
                line_number: lineNumber,
                depth: depth,
            });

            // Send data to webview
            this._view.webview.postMessage({
                command: 'updateGraph',
                data: this._graphData,
            });
        } catch (error) {
            console.error('Failed to load graph context:', error);
            this._view.webview.postMessage({
                command: 'setError',
                error: `Failed to load graph context: ${error}`,
            });
        }
    }

    /**
     * Navigate to a node's file and line
     */
    private async _navigateToNode(nodeId: string): Promise<void> {
        if (!this._graphData) {
            return;
        }

        const node = this._graphData.nodes.find(n => n.id === nodeId);
        if (!node || !node.file_path) {
            return;
        }

        try {
            const uri = vscode.Uri.file(node.file_path);
            const document = await vscode.workspace.openTextDocument(uri);
            const editor = await vscode.window.showTextDocument(document);

            if (node.line_start) {
                const position = new vscode.Position(node.line_start - 1, 0);
                editor.selection = new vscode.Selection(position, position);
                editor.revealRange(
                    new vscode.Range(position, position),
                    vscode.TextEditorRevealType.InCenter
                );
            }
        } catch (error) {
            vscode.window.showErrorMessage(`Could not navigate to ${node.file_path}`);
        }
    }

    /**
     * Generate HTML for the webview
     */
    private _getHtmlForWebview(webview: vscode.Webview): string {
        // Use a nonce for content security policy
        const nonce = getNonce();

        return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src 'nonce-${nonce}';">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Code Context</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            font-size: var(--vscode-font-size);
            color: var(--vscode-foreground);
            background-color: var(--vscode-sideBar-background);
            padding: 10px;
            margin: 0;
        }

        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--vscode-sideBar-border);
        }

        .header h3 {
            margin: 0;
            font-size: 13px;
            font-weight: 600;
        }

        .controls {
            display: flex;
            gap: 8px;
            align-items: center;
        }

        .controls select {
            background: var(--vscode-dropdown-background);
            color: var(--vscode-dropdown-foreground);
            border: 1px solid var(--vscode-dropdown-border);
            border-radius: 2px;
            padding: 2px 6px;
            font-size: 12px;
        }

        .controls button {
            background: var(--vscode-button-secondaryBackground);
            color: var(--vscode-button-secondaryForeground);
            border: none;
            padding: 4px 8px;
            border-radius: 2px;
            cursor: pointer;
            font-size: 12px;
        }

        .controls button:hover {
            background: var(--vscode-button-secondaryHoverBackground);
        }

        .stats {
            display: flex;
            gap: 16px;
            margin-bottom: 12px;
            font-size: 11px;
            color: var(--vscode-descriptionForeground);
        }

        .stat {
            display: flex;
            align-items: center;
            gap: 4px;
        }

        .stat-value {
            font-weight: 600;
            color: var(--vscode-foreground);
        }

        .graph-container {
            min-height: 200px;
            background: var(--vscode-editor-background);
            border-radius: 4px;
            padding: 10px;
            position: relative;
        }

        .loading {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 150px;
            color: var(--vscode-descriptionForeground);
        }

        .error {
            padding: 20px;
            text-align: center;
            color: var(--vscode-errorForeground);
        }

        .node-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .node-item {
            display: flex;
            align-items: center;
            padding: 6px 8px;
            margin: 2px 0;
            background: var(--vscode-list-hoverBackground);
            border-radius: 3px;
            cursor: pointer;
            gap: 8px;
        }

        .node-item:hover {
            background: var(--vscode-list-activeSelectionBackground);
        }

        .node-item.focused {
            background: var(--vscode-list-activeSelectionBackground);
            border-left: 3px solid var(--vscode-focusBorder);
        }

        .node-icon {
            width: 16px;
            height: 16px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: bold;
            border-radius: 2px;
        }

        .node-icon.file { background: #4fc3f7; color: #000; }
        .node-icon.class { background: #ff8a65; color: #000; }
        .node-icon.function { background: #ba68c8; color: #fff; }
        .node-icon.method { background: #9575cd; color: #fff; }
        .node-icon.module { background: #81c784; color: #000; }
        .node-icon.variable { background: #64b5f6; color: #000; }
        .node-icon.import { background: #ffb74d; color: #000; }

        .node-name {
            flex: 1;
            font-size: 12px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .node-location {
            font-size: 10px;
            color: var(--vscode-descriptionForeground);
        }

        .relationships {
            margin-top: 12px;
        }

        .relationships h4 {
            font-size: 11px;
            font-weight: 600;
            margin: 0 0 8px 0;
            color: var(--vscode-descriptionForeground);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .relationship-item {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            font-size: 12px;
            border-bottom: 1px solid var(--vscode-sideBar-border);
        }

        .relationship-type {
            text-transform: capitalize;
        }

        .relationship-count {
            font-weight: 600;
            color: var(--vscode-badge-foreground);
            background: var(--vscode-badge-background);
            padding: 0 6px;
            border-radius: 10px;
            font-size: 10px;
        }

        .empty-state {
            text-align: center;
            padding: 40px 20px;
            color: var(--vscode-descriptionForeground);
        }

        .empty-state svg {
            width: 48px;
            height: 48px;
            margin-bottom: 16px;
            opacity: 0.5;
        }

        .empty-state p {
            margin: 0;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h3>Code Context</h3>
        <div class="controls">
            <select id="depth-select" title="Traversal Depth">
                <option value="1">Depth: 1</option>
                <option value="2" selected>Depth: 2</option>
                <option value="3">Depth: 3</option>
            </select>
            <button id="refresh-btn" title="Refresh">&#x21bb;</button>
        </div>
    </div>

    <div id="content">
        <div class="empty-state">
            <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            <p>Open a file to see its code relationships</p>
        </div>
    </div>

    <script nonce="${nonce}">
        (function() {
            const vscode = acquireVsCodeApi();
            const content = document.getElementById('content');
            const depthSelect = document.getElementById('depth-select');
            const refreshBtn = document.getElementById('refresh-btn');

            // Handle depth change
            depthSelect.addEventListener('change', (e) => {
                vscode.postMessage({
                    command: 'setDepth',
                    depth: parseInt(e.target.value)
                });
            });

            // Handle refresh
            refreshBtn.addEventListener('click', () => {
                vscode.postMessage({ command: 'refresh' });
            });

            // Handle messages from extension
            window.addEventListener('message', event => {
                const message = event.data;

                switch (message.command) {
                    case 'setLoading':
                        if (message.loading) {
                            content.innerHTML = '<div class="loading">Loading...</div>';
                        }
                        break;

                    case 'updateGraph':
                        renderGraph(message.data);
                        break;

                    case 'setError':
                        content.innerHTML = '<div class="error">' + message.error + '</div>';
                        break;
                }
            });

            function renderGraph(data) {
                if (!data || !data.nodes || data.nodes.length === 0) {
                    content.innerHTML = '<div class="empty-state"><p>No code relationships found</p></div>';
                    return;
                }

                let html = '';

                // Stats
                html += '<div class="stats">';
                html += '<div class="stat"><span class="stat-value">' + data.nodes.length + '</span> nodes</div>';
                html += '<div class="stat"><span class="stat-value">' + data.edges.length + '</span> edges</div>';
                html += '<div class="stat"><span class="stat-value">' + data.query_duration_ms.toFixed(0) + '</span>ms</div>';
                html += '</div>';

                // Nodes
                html += '<div class="graph-container">';
                html += '<ul class="node-list">';

                for (const node of data.nodes) {
                    const isFocused = node.id === data.focus_node_id;
                    const iconLabel = getIconLabel(node.type);
                    const location = node.line_start ? ':' + node.line_start : '';

                    html += '<li class="node-item' + (isFocused ? ' focused' : '') + '" data-node-id="' + node.id + '">';
                    html += '<span class="node-icon ' + node.type + '">' + iconLabel + '</span>';
                    html += '<span class="node-name">' + escapeHtml(node.name) + '</span>';
                    if (node.file_path) {
                        html += '<span class="node-location">' + escapeHtml(getFileName(node.file_path)) + location + '</span>';
                    }
                    html += '</li>';
                }

                html += '</ul>';
                html += '</div>';

                // Relationships summary
                if (data.relationships && Object.keys(data.relationships).length > 0) {
                    html += '<div class="relationships">';
                    html += '<h4>Relationships</h4>';

                    for (const [type, count] of Object.entries(data.relationships)) {
                        html += '<div class="relationship-item">';
                        html += '<span class="relationship-type">' + type.replace('_', ' ') + '</span>';
                        html += '<span class="relationship-count">' + count + '</span>';
                        html += '</div>';
                    }

                    html += '</div>';
                }

                content.innerHTML = html;

                // Add click handlers for nodes
                document.querySelectorAll('.node-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const nodeId = item.getAttribute('data-node-id');
                        vscode.postMessage({
                            command: 'navigateToNode',
                            nodeId: nodeId
                        });
                    });
                });
            }

            function getIconLabel(type) {
                const labels = {
                    'file': 'F',
                    'class': 'C',
                    'function': 'fn',
                    'method': 'M',
                    'module': 'mod',
                    'variable': 'V',
                    'import': 'I'
                };
                return labels[type] || '?';
            }

            function getFileName(filePath) {
                return filePath.split('/').pop() || filePath;
            }

            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
        })();
    </script>
</body>
</html>`;
    }
}

/**
 * Generate a random nonce for CSP
 */
function getNonce(): string {
    let text = '';
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    for (let i = 0; i < 32; i++) {
        text += possible.charAt(Math.floor(Math.random() * possible.length));
    }
    return text;
}
