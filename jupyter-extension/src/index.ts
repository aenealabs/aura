/**
 * Aura Code Intelligence JupyterLab Extension
 *
 * Provides:
 * - Cell-level security scanning
 * - Inline findings display with severity indicators
 * - One-click fix application in notebooks
 * - GraphRAG code context panel (P0 Key Differentiator)
 * - Secrets scanning before notebook publish/share
 *
 * ADR-048 Phase 2: Jupyter Extension
 */

import {
    JupyterFrontEnd,
    JupyterFrontEndPlugin,
    ILayoutRestorer,
} from '@jupyterlab/application';
import { ISettingRegistry } from '@jupyterlab/settingregistry';
import { INotebookTracker, NotebookPanel } from '@jupyterlab/notebook';
import { ToolbarButton, MainAreaWidget, ICommandPalette } from '@jupyterlab/apputils';
import { LabIcon } from '@jupyterlab/ui-components';
import { Cell } from '@jupyterlab/cells';
import { Widget, BoxLayout } from '@lumino/widgets';

import { AuraApiClient } from './api/client';
import { FindingsPanel } from './widgets/FindingsPanel';
import { GraphContextPanel } from './widgets/GraphContextPanel';
import { CellAnnotator } from './annotators/CellAnnotator';

// Extension namespace
const EXTENSION_ID = '@aura/jupyterlab-extension:plugin';
const COMMAND_NAMESPACE = 'aura';

// Icons
const auraIconSvg = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
  <path fill="currentColor" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
</svg>`;

const scanIcon = new LabIcon({
    name: 'aura:scan',
    svgstr: auraIconSvg,
});

/**
 * Extension state
 */
interface ExtensionState {
    apiClient: AuraApiClient;
    cellAnnotator: CellAnnotator;
    findingsPanel: FindingsPanel | null;
    graphContextPanel: GraphContextPanel | null;
}

/**
 * Main plugin activation
 */
const plugin: JupyterFrontEndPlugin<void> = {
    id: EXTENSION_ID,
    autoStart: true,
    requires: [INotebookTracker],
    optional: [ISettingRegistry, ILayoutRestorer, ICommandPalette],
    activate: async (
        app: JupyterFrontEnd,
        notebookTracker: INotebookTracker,
        settingRegistry: ISettingRegistry | null,
        restorer: ILayoutRestorer | null,
        palette: ICommandPalette | null
    ) => {
        console.log('Aura Code Intelligence extension activating...');

        // Load settings
        let serverUrl = 'http://localhost:8080';
        let autoScanOnSave = true;
        let showGraphContext = true;

        if (settingRegistry) {
            try {
                const settings = await settingRegistry.load(EXTENSION_ID);
                serverUrl = settings.get('serverUrl').composite as string || serverUrl;
                autoScanOnSave = settings.get('autoScanOnSave').composite as boolean ?? true;
                showGraphContext = settings.get('showGraphContext').composite as boolean ?? true;
            } catch (error) {
                console.warn('Failed to load settings, using defaults:', error);
            }
        }

        // Initialize state
        const state: ExtensionState = {
            apiClient: new AuraApiClient(serverUrl),
            cellAnnotator: new CellAnnotator(),
            findingsPanel: null,
            graphContextPanel: null,
        };

        // Verify connection
        try {
            const config = await state.apiClient.getConfig();
            console.log(`Connected to Aura server (API v${config.api_version})`);
        } catch (error) {
            console.warn('Could not connect to Aura server:', error);
        }

        // Register commands
        registerCommands(app, state, notebookTracker);

        // Add to command palette
        if (palette) {
            addToCommandPalette(palette);
        }

        // Create sidebar panels
        createSidebarPanels(app, state, restorer, showGraphContext);

        // Add toolbar button to notebooks
        notebookTracker.widgetAdded.connect((_, panel: NotebookPanel) => {
            addToolbarButton(panel, state);

            // Auto-scan on save if enabled
            if (autoScanOnSave) {
                panel.context.saveState.connect(async () => {
                    await scanNotebook(panel, state);
                });
            }
        });

        // Track active cell for GraphRAG context
        if (showGraphContext) {
            notebookTracker.activeCellChanged.connect(async (_, cell: Cell | null) => {
                if (cell && state.graphContextPanel) {
                    await state.graphContextPanel.updateForCell(cell);
                }
            });
        }

        console.log('Aura Code Intelligence extension activated');
    },
};

/**
 * Register extension commands
 */
function registerCommands(
    app: JupyterFrontEnd,
    state: ExtensionState,
    notebookTracker: INotebookTracker
): void {
    // Scan current notebook
    app.commands.addCommand(`${COMMAND_NAMESPACE}:scan-notebook`, {
        label: 'Aura: Scan Notebook for Vulnerabilities',
        icon: scanIcon,
        execute: async () => {
            const panel = notebookTracker.currentWidget;
            if (panel) {
                await scanNotebook(panel, state);
            }
        },
    });

    // Scan current cell
    app.commands.addCommand(`${COMMAND_NAMESPACE}:scan-cell`, {
        label: 'Aura: Scan Current Cell',
        execute: async () => {
            const panel = notebookTracker.currentWidget;
            const cell = panel?.content.activeCell;
            if (cell) {
                await scanCell(cell, panel.context.path, state);
            }
        },
    });

    // Check for secrets before sharing
    app.commands.addCommand(`${COMMAND_NAMESPACE}:check-secrets`, {
        label: 'Aura: Check for Secrets Before Sharing',
        execute: async () => {
            const panel = notebookTracker.currentWidget;
            if (panel) {
                await checkNotebookSecrets(panel, state);
            }
        },
    });

    // Apply fix to cell
    app.commands.addCommand(`${COMMAND_NAMESPACE}:apply-fix`, {
        label: 'Aura: Apply Fix to Finding',
        execute: async (args) => {
            const findingId = args.findingId as string;
            if (findingId) {
                await applyFix(findingId, notebookTracker, state);
            }
        },
    });

    // Show GraphRAG context panel
    app.commands.addCommand(`${COMMAND_NAMESPACE}:show-graph-context`, {
        label: 'Aura: Show Code Context Graph',
        execute: () => {
            if (state.graphContextPanel) {
                app.shell.activateById(state.graphContextPanel.id);
            }
        },
    });

    // Show findings panel
    app.commands.addCommand(`${COMMAND_NAMESPACE}:show-findings`, {
        label: 'Aura: Show Findings',
        execute: () => {
            if (state.findingsPanel) {
                app.shell.activateById(state.findingsPanel.id);
            }
        },
    });
}

/**
 * Add commands to palette
 */
function addToCommandPalette(palette: ICommandPalette): void {
    const category = 'Aura Security';
    palette.addItem({ command: `${COMMAND_NAMESPACE}:scan-notebook`, category });
    palette.addItem({ command: `${COMMAND_NAMESPACE}:scan-cell`, category });
    palette.addItem({ command: `${COMMAND_NAMESPACE}:check-secrets`, category });
    palette.addItem({ command: `${COMMAND_NAMESPACE}:show-graph-context`, category });
    palette.addItem({ command: `${COMMAND_NAMESPACE}:show-findings`, category });
}

/**
 * Create sidebar panels
 */
function createSidebarPanels(
    app: JupyterFrontEnd,
    state: ExtensionState,
    restorer: ILayoutRestorer | null,
    showGraphContext: boolean
): void {
    // Findings panel
    state.findingsPanel = new FindingsPanel(state.apiClient, app.commands);
    state.findingsPanel.id = 'aura-findings-panel';
    state.findingsPanel.title.label = 'Aura Findings';
    state.findingsPanel.title.icon = scanIcon;
    app.shell.add(state.findingsPanel, 'right', { rank: 100 });

    // GraphRAG context panel (P0 Key Differentiator)
    if (showGraphContext) {
        state.graphContextPanel = new GraphContextPanel(state.apiClient);
        state.graphContextPanel.id = 'aura-graph-context-panel';
        state.graphContextPanel.title.label = 'Code Context';
        state.graphContextPanel.title.icon = scanIcon;
        app.shell.add(state.graphContextPanel, 'right', { rank: 101 });
    }

    // Restore panels if layout restorer available
    if (restorer) {
        restorer.add(state.findingsPanel, 'aura-findings-panel');
        if (state.graphContextPanel) {
            restorer.add(state.graphContextPanel, 'aura-graph-context-panel');
        }
    }
}

/**
 * Add scan button to notebook toolbar
 */
function addToolbarButton(panel: NotebookPanel, state: ExtensionState): void {
    const button = new ToolbarButton({
        icon: scanIcon,
        onClick: async () => {
            await scanNotebook(panel, state);
        },
        tooltip: 'Scan for security vulnerabilities',
    });

    panel.toolbar.insertItem(10, 'aura-scan', button);
}

/**
 * Scan entire notebook
 */
async function scanNotebook(panel: NotebookPanel, state: ExtensionState): Promise<void> {
    const notebook = panel.content;
    const path = panel.context.path;

    console.log(`Scanning notebook: ${path}`);

    // Get all code cells
    const cells = notebook.widgets.filter(cell => cell.model.type === 'code');

    // Scan each cell
    for (let i = 0; i < cells.length; i++) {
        await scanCell(cells[i], path, state, i);
    }

    // Refresh findings panel
    if (state.findingsPanel) {
        state.findingsPanel.refresh();
    }
}

/**
 * Scan a single cell
 */
async function scanCell(
    cell: Cell,
    notebookPath: string,
    state: ExtensionState,
    cellIndex?: number
): Promise<void> {
    const source = cell.model.sharedModel.getSource();
    const cellId = cell.model.id || `cell-${cellIndex ?? 0}`;

    try {
        const result = await state.apiClient.scanCell({
            notebook_path: notebookPath,
            cell_id: cellId,
            cell_index: cellIndex ?? 0,
            source_code: source,
            language: 'python', // Jupyter primarily uses Python
        });

        // Get findings for this cell
        const findings = await state.apiClient.getCellFindings(notebookPath, cellId);

        // Annotate cell with findings
        state.cellAnnotator.annotateCell(cell, findings.findings);

        // Show notification if critical/high findings
        const criticalHigh = findings.findings.filter(
            f => f.severity === 'critical' || f.severity === 'high'
        ).length;

        if (criticalHigh > 0) {
            console.warn(`Cell ${cellIndex}: Found ${criticalHigh} critical/high severity issues`);
        }
    } catch (error) {
        console.error(`Failed to scan cell ${cellIndex}:`, error);
    }
}

/**
 * Check notebook for secrets before sharing
 */
async function checkNotebookSecrets(panel: NotebookPanel, state: ExtensionState): Promise<void> {
    const notebook = panel.content;
    const path = panel.context.path;

    // Collect all cell sources and outputs
    let content = '';
    for (const cell of notebook.widgets) {
        content += cell.model.sharedModel.getSource() + '\n';
        // Also check outputs for secrets
        if (cell.model.type === 'code') {
            const outputs = (cell.model as any).outputs;
            if (outputs) {
                for (let i = 0; i < outputs.length; i++) {
                    const output = outputs.get(i);
                    if (output?.data) {
                        content += JSON.stringify(output.data) + '\n';
                    }
                }
            }
        }
    }

    try {
        const result = await state.apiClient.checkSecrets(path, content);

        if (result.is_clean) {
            // Show success dialog
            console.log('No secrets detected - safe to share');
        } else {
            // Show warning dialog with details
            console.warn(`Found ${result.secret_count} potential secrets in notebook`);

            // Mark cells with secrets
            for (const secret of result.secrets) {
                const cellIndex = findCellByLineNumber(notebook.widgets, secret.line_number);
                if (cellIndex >= 0) {
                    state.cellAnnotator.markSecretsWarning(notebook.widgets[cellIndex], secret);
                }
            }
        }
    } catch (error) {
        console.error('Failed to check for secrets:', error);
    }
}

/**
 * Apply fix to a finding
 */
async function applyFix(
    findingId: string,
    notebookTracker: INotebookTracker,
    state: ExtensionState
): Promise<void> {
    const panel = notebookTracker.currentWidget;
    if (!panel) {
        return;
    }

    try {
        // Get fix preview first
        const preview = await state.apiClient.previewFix({
            finding_id: findingId,
            file_content: '', // Not needed for cell-based fixes
        });

        // TODO: Show confirmation dialog with diff preview

        // Apply the fix
        const result = await state.apiClient.applyFix(findingId, panel.context.path, true);

        if (result.success) {
            // Refresh the notebook to show changes
            await panel.context.revert();

            // Re-scan to update findings
            await scanNotebook(panel, state);
        }
    } catch (error) {
        console.error('Failed to apply fix:', error);
    }
}

/**
 * Find cell index by line number
 */
function findCellByLineNumber(cells: readonly Widget[], lineNumber: number): number {
    let currentLine = 0;
    for (let i = 0; i < cells.length; i++) {
        const cell = cells[i] as Cell;
        const source = cell.model.sharedModel.getSource();
        const lines = source.split('\n').length;

        if (lineNumber >= currentLine && lineNumber < currentLine + lines) {
            return i;
        }
        currentLine += lines;
    }
    return -1;
}

/**
 * Export the plugin
 */
export default plugin;
