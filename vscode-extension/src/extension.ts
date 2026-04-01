/**
 * Aura Code Intelligence VS Code Extension
 *
 * Main extension entry point. Provides:
 * - Real-time vulnerability scanning
 * - Code review findings in Problems panel
 * - Patch generation and application
 * - HITL approval workflow integration
 * - GraphRAG Code Context Panel (P0 Key Differentiator) - ADR-048
 * - Secrets detection and warning
 *
 * ADR-028 Phase 4: VS Code Extension
 * ADR-048 Phase 1: Enhanced IDE Integration
 */

import * as vscode from 'vscode';
import { AuraApiClient } from './api/client';
import { FindingsProvider } from './providers/findingsProvider';
import { PatchesProvider } from './providers/patchesProvider';
import { ApprovalsProvider } from './providers/approvalsProvider';
import { AuraCodeLensProvider, registerShowFindingDetailsCommand } from './providers/codeLensProvider';
import { AuraDiagnosticsProvider, AuraCodeActionProvider } from './providers/diagnosticsProvider';
import { GraphContextPanelProvider } from './providers/graphContextProvider';

// Global instances
let apiClient: AuraApiClient;
let diagnosticsProvider: AuraDiagnosticsProvider;
let findingsProvider: FindingsProvider;
let patchesProvider: PatchesProvider;
let approvalsProvider: ApprovalsProvider;
let graphContextProvider: GraphContextPanelProvider;

/**
 * Extension activation
 */
export async function activate(context: vscode.ExtensionContext): Promise<void> {
    console.log('Aura Code Intelligence extension activating...');

    // Get configuration
    const config = vscode.workspace.getConfiguration('aura');
    const serverUrl = config.get<string>('serverUrl', 'http://localhost:8080');

    // Initialize API client
    apiClient = new AuraApiClient(serverUrl);

    // Verify connection
    try {
        const extensionConfig = await apiClient.getConfig();
        console.log(`Connected to Aura server (API v${extensionConfig.api_version})`);
    } catch (error) {
        vscode.window.showWarningMessage(
            `Could not connect to Aura server at ${serverUrl}. ` +
            'Some features may be unavailable.'
        );
    }

    // Initialize providers
    diagnosticsProvider = new AuraDiagnosticsProvider(apiClient);
    findingsProvider = new FindingsProvider(apiClient);
    patchesProvider = new PatchesProvider(apiClient);
    approvalsProvider = new ApprovalsProvider(apiClient);

    // Initialize GraphRAG Context Panel (P0 Key Differentiator - ADR-048)
    graphContextProvider = new GraphContextPanelProvider(context.extensionUri, apiClient);

    // Register tree views
    vscode.window.registerTreeDataProvider('aura-findings', findingsProvider);
    vscode.window.registerTreeDataProvider('aura-patches', patchesProvider);
    vscode.window.registerTreeDataProvider('aura-approvals', approvalsProvider);

    // Register GraphRAG Context Panel webview provider
    context.subscriptions.push(
        vscode.window.registerWebviewViewProvider(
            GraphContextPanelProvider.viewType,
            graphContextProvider
        )
    );

    // Supported languages for security scanning
    const supportedLanguages = [
        { language: 'python' },
        { language: 'javascript' },
        { language: 'typescript' },
        { language: 'java' },
        { language: 'go' },
        { language: 'rust' },
    ];

    // Register CodeLens provider
    const codeLensProvider = new AuraCodeLensProvider(findingsProvider);
    const codeLensDisposable = vscode.languages.registerCodeLensProvider(
        supportedLanguages,
        codeLensProvider
    );
    context.subscriptions.push(codeLensDisposable);

    // Register Code Action provider
    const codeActionProvider = new AuraCodeActionProvider(findingsProvider);
    const codeActionDisposable = vscode.languages.registerCodeActionsProvider(
        supportedLanguages,
        codeActionProvider,
        {
            providedCodeActionKinds: AuraCodeActionProvider.providedCodeActionKinds,
        }
    );
    context.subscriptions.push(codeActionDisposable);

    // Register show finding details command
    registerShowFindingDetailsCommand(context);

    // Register commands
    registerCommands(context);

    // Register event handlers
    registerEventHandlers(context);

    console.log('Aura Code Intelligence extension activated');
}

/**
 * Register extension commands
 */
function registerCommands(context: vscode.ExtensionContext): void {
    // Scan current file
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.scanFile', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }

            await scanFile(editor.document);
        })
    );

    // Scan entire workspace
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.scanWorkspace', async () => {
            await scanWorkspace();
        })
    );

    // Generate patch for finding
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.generatePatch', async (findingId?: string) => {
            if (!findingId) {
                // Prompt user to select finding
                const findings = await findingsProvider.getAllFindings();
                const items = findings.map(f => ({
                    label: f.title,
                    description: `${f.file_path}:${f.line_start}`,
                    findingId: f.id,
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: 'Select a finding to patch',
                });

                if (!selected) {
                    return;
                }

                findingId = selected.findingId;
            }

            await generatePatch(findingId);
        })
    );

    // Apply approved patch
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.applyPatch', async (patchId?: string) => {
            if (!patchId) {
                // Prompt user to select patch
                const patches = await patchesProvider.getApprovedPatches();
                const items = patches.map(p => ({
                    label: `Patch for ${p.file_path}`,
                    description: p.status,
                    patchId: p.id,
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: 'Select a patch to apply',
                });

                if (!selected) {
                    return;
                }

                patchId = selected.patchId;
            }

            await applyPatch(patchId);
        })
    );

    // Show HITL approvals
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.showApprovals', async () => {
            vscode.commands.executeCommand('aura-approvals.focus');
        })
    );

    // Toggle scan on save
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.toggleScanOnSave', async () => {
            const config = vscode.workspace.getConfiguration('aura');
            const current = config.get<boolean>('scanOnSave', true);
            await config.update('scanOnSave', !current, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage(
                `Scan on save ${!current ? 'enabled' : 'disabled'}`
            );
        })
    );

    // Show GraphRAG Code Context (P0 Key Differentiator - ADR-048)
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.showGraphContext', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }

            const config = vscode.workspace.getConfiguration('aura');
            if (!config.get<boolean>('showGraphContext', true)) {
                vscode.window.showInformationMessage(
                    'GraphRAG context panel is disabled. Enable it in settings.'
                );
                return;
            }

            // Focus the GraphRAG panel
            await vscode.commands.executeCommand('aura-graph-context.focus');

            // Update with current file
            const relativePath = vscode.workspace.asRelativePath(editor.document.uri);
            const lineNumber = editor.selection.active.line + 1;
            await graphContextProvider.updateForFile(relativePath, lineNumber);
        })
    );

    // Refresh GraphRAG Context
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.refreshGraphContext', async () => {
            await graphContextProvider.refresh();
        })
    );

    // Preview fix for finding (ADR-048)
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.previewFix', async (findingId?: string) => {
            if (!findingId) {
                const findings = await findingsProvider.getAllFindings();
                const items = findings.map(f => ({
                    label: f.title,
                    description: `${f.file_path}:${f.line_start} (${f.severity})`,
                    findingId: f.id,
                }));

                const selected = await vscode.window.showQuickPick(items, {
                    placeHolder: 'Select a finding to preview fix',
                });

                if (!selected) {
                    return;
                }
                findingId = selected.findingId;
            }

            await previewFix(findingId);
        })
    );

    // Check for secrets in current file (ADR-048 Security Control)
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.checkSecrets', async () => {
            const editor = vscode.window.activeTextEditor;
            if (!editor) {
                vscode.window.showWarningMessage('No active editor');
                return;
            }

            await checkFileForSecrets(editor.document);
        })
    );
}

/**
 * Register event handlers
 */
function registerEventHandlers(context: vscode.ExtensionContext): void {
    // Scan on save
    context.subscriptions.push(
        vscode.workspace.onDidSaveTextDocument(async (document) => {
            const config = vscode.workspace.getConfiguration('aura');
            if (config.get<boolean>('scanOnSave', true)) {
                await scanFile(document);
            }
        })
    );

    // Update diagnostics when document changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeTextDocument((event) => {
            // Clear stale diagnostics
            diagnosticsProvider.clearDiagnostics(event.document.uri);
        })
    );

    // Update GraphRAG context when active editor changes (ADR-048)
    context.subscriptions.push(
        vscode.window.onDidChangeActiveTextEditor(async (editor) => {
            const config = vscode.workspace.getConfiguration('aura');
            if (!config.get<boolean>('showGraphContext', true)) {
                return;
            }

            if (editor) {
                const relativePath = vscode.workspace.asRelativePath(editor.document.uri);
                const lineNumber = editor.selection.active.line + 1;
                await graphContextProvider.updateForFile(relativePath, lineNumber);
            }
        })
    );

    // Update GraphRAG context when cursor position changes
    context.subscriptions.push(
        vscode.window.onDidChangeTextEditorSelection(async (event) => {
            const config = vscode.workspace.getConfiguration('aura');
            if (!config.get<boolean>('showGraphContext', true)) {
                return;
            }

            // Debounce: only update if line changed significantly
            const relativePath = vscode.workspace.asRelativePath(event.textEditor.document.uri);
            const lineNumber = event.selections[0]?.active.line + 1;

            // Only update on significant cursor movement (e.g., when navigating to a function)
            // This prevents excessive API calls during normal editing
            if (lineNumber && event.kind === vscode.TextEditorSelectionChangeKind.Command) {
                await graphContextProvider.updateForFile(relativePath, lineNumber);
            }
        })
    );

    // Configuration changes
    context.subscriptions.push(
        vscode.workspace.onDidChangeConfiguration((event) => {
            if (event.affectsConfiguration('aura.serverUrl')) {
                const config = vscode.workspace.getConfiguration('aura');
                const serverUrl = config.get<string>('serverUrl', 'http://localhost:8080');
                apiClient.setBaseUrl(serverUrl);
            }
        })
    );
}

/**
 * Scan a single file
 */
async function scanFile(document: vscode.TextDocument): Promise<void> {
    const workspaceFolder = vscode.workspace.getWorkspaceFolder(document.uri);
    const relativePath = workspaceFolder
        ? vscode.workspace.asRelativePath(document.uri)
        : document.uri.fsPath;

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Scanning ${relativePath}...`,
                cancellable: false,
            },
            async () => {
                const result = await apiClient.scanFile({
                    file_path: relativePath,
                    file_content: document.getText(),
                    language: document.languageId,
                    workspace_path: workspaceFolder?.uri.fsPath || '',
                });

                // Fetch and display findings
                const findings = await apiClient.getFindings(relativePath);

                // Update diagnostics
                diagnosticsProvider.updateDiagnostics(document.uri, findings.findings);

                // Update tree view
                findingsProvider.refresh();

                // Show summary
                const criticalHigh = findings.findings.filter(
                    f => f.severity === 'critical' || f.severity === 'high'
                ).length;

                if (criticalHigh > 0) {
                    vscode.window.showWarningMessage(
                        `Found ${criticalHigh} critical/high severity issues in ${relativePath}`
                    );
                } else if (findings.findings.length > 0) {
                    vscode.window.showInformationMessage(
                        `Found ${findings.findings.length} issues in ${relativePath}`
                    );
                }
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Scan failed: ${error}`);
    }
}

/**
 * Scan entire workspace
 */
async function scanWorkspace(): Promise<void> {
    const config = vscode.workspace.getConfiguration('aura');

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Scanning workspace...',
                cancellable: true,
            },
            async (progress, token) => {
                // Find all supported files
                const files = await vscode.workspace.findFiles(
                    '**/*.{py,js,ts,java,go,rs}',
                    '**/node_modules/**'
                );

                let scanned = 0;
                for (const fileUri of files) {
                    if (token.isCancellationRequested) {
                        break;
                    }

                    progress.report({
                        message: `Scanning ${vscode.workspace.asRelativePath(fileUri)}`,
                        increment: (1 / files.length) * 100,
                    });

                    try {
                        const document = await vscode.workspace.openTextDocument(fileUri);
                        await scanFile(document);
                        scanned++;
                    } catch (error) {
                        console.error(`Failed to scan ${fileUri.fsPath}: ${error}`);
                    }
                }

                vscode.window.showInformationMessage(`Scanned ${scanned} files`);
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Workspace scan failed: ${error}`);
    }
}

/**
 * Generate a patch for a finding
 */
async function generatePatch(findingId: string): Promise<void> {
    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Generating patch...',
                cancellable: false,
            },
            async () => {
                // Get finding details
                const findings = await findingsProvider.getAllFindings();
                const finding = findings.find(f => f.id === findingId);

                if (!finding) {
                    throw new Error('Finding not found');
                }

                // Get file content
                const document = await vscode.workspace.openTextDocument(
                    vscode.Uri.file(finding.file_path)
                );

                // Generate patch
                const result = await apiClient.generatePatch({
                    finding_id: findingId,
                    file_path: finding.file_path,
                    file_content: document.getText(),
                    context_lines: 10,
                });

                // Refresh patches view
                patchesProvider.refresh();

                // Show diff preview
                const patchDoc = await vscode.workspace.openTextDocument({
                    content: result.patch.diff,
                    language: 'diff',
                });

                await vscode.window.showTextDocument(patchDoc, {
                    viewColumn: vscode.ViewColumn.Beside,
                    preview: true,
                });

                if (result.patch.requires_approval) {
                    vscode.window.showInformationMessage(
                        'Patch generated. HITL approval required before applying.'
                    );
                } else {
                    vscode.window.showInformationMessage(
                        'Patch generated and ready to apply.'
                    );
                }
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Patch generation failed: ${error}`);
    }
}

/**
 * Apply an approved patch
 */
async function applyPatch(patchId: string): Promise<void> {
    try {
        // Get patch details
        const patch = await apiClient.getPatch(patchId);

        if (patch.requires_approval && patch.status !== 'approved') {
            vscode.window.showWarningMessage(
                'This patch requires HITL approval before it can be applied.'
            );
            return;
        }

        // Confirm with user
        const confirm = await vscode.window.showWarningMessage(
            `Apply patch to ${patch.file_path}?`,
            { modal: true },
            'Apply'
        );

        if (confirm !== 'Apply') {
            return;
        }

        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Applying patch...',
                cancellable: false,
            },
            async () => {
                // Apply via API
                await apiClient.applyPatch(patchId, true);

                // Refresh views
                patchesProvider.refresh();
                findingsProvider.refresh();

                vscode.window.showInformationMessage(
                    `Patch applied to ${patch.file_path}`
                );
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Failed to apply patch: ${error}`);
    }
}

/**
 * Preview a fix for a finding (ADR-048)
 */
async function previewFix(findingId: string): Promise<void> {
    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: 'Generating fix preview...',
                cancellable: false,
            },
            async () => {
                // Get finding details
                const findings = await findingsProvider.getAllFindings();
                const finding = findings.find(f => f.id === findingId);

                if (!finding) {
                    throw new Error('Finding not found');
                }

                // Get file content
                const document = await vscode.workspace.openTextDocument(
                    vscode.Uri.file(finding.file_path)
                );

                // Get fix preview
                const preview = await apiClient.previewFix({
                    finding_id: findingId,
                    file_content: document.getText(),
                });

                // Show diff preview in a new document
                const previewDoc = await vscode.workspace.openTextDocument({
                    content: formatFixPreview(preview, finding),
                    language: 'markdown',
                });

                await vscode.window.showTextDocument(previewDoc, {
                    viewColumn: vscode.ViewColumn.Beside,
                    preview: true,
                });

                // Show summary
                if (preview.requires_review) {
                    vscode.window.showWarningMessage(
                        `Fix preview ready. Confidence: ${(preview.confidence * 100).toFixed(0)}%. Manual review recommended.`
                    );
                } else {
                    vscode.window.showInformationMessage(
                        `Fix preview ready. Confidence: ${(preview.confidence * 100).toFixed(0)}%.`
                    );
                }
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Fix preview failed: ${error}`);
    }
}

/**
 * Format fix preview for display
 */
function formatFixPreview(preview: {
    finding_id: string;
    diff: string;
    confidence: number;
    explanation: string;
    side_effects: string[];
    test_suggestions: string[];
    requires_review: boolean;
}, finding: { title: string; severity: string; file_path: string }): string {
    let content = `# Fix Preview: ${finding.title}\n\n`;
    content += `**File:** ${finding.file_path}\n`;
    content += `**Severity:** ${finding.severity}\n`;
    content += `**Confidence:** ${(preview.confidence * 100).toFixed(0)}%\n`;
    content += `**Requires Review:** ${preview.requires_review ? 'Yes' : 'No'}\n\n`;

    content += `## Explanation\n\n${preview.explanation}\n\n`;

    content += `## Diff\n\n\`\`\`diff\n${preview.diff}\n\`\`\`\n\n`;

    if (preview.side_effects.length > 0) {
        content += `## Potential Side Effects\n\n`;
        preview.side_effects.forEach(effect => {
            content += `- ${effect}\n`;
        });
        content += '\n';
    }

    if (preview.test_suggestions.length > 0) {
        content += `## Suggested Tests\n\n`;
        preview.test_suggestions.forEach(test => {
            content += `- ${test}\n`;
        });
        content += '\n';
    }

    return content;
}

/**
 * Check file for secrets (ADR-048 Security Control)
 */
async function checkFileForSecrets(document: vscode.TextDocument): Promise<void> {
    const relativePath = vscode.workspace.asRelativePath(document.uri);

    try {
        await vscode.window.withProgress(
            {
                location: vscode.ProgressLocation.Notification,
                title: `Checking ${relativePath} for secrets...`,
                cancellable: false,
            },
            async () => {
                const result = await apiClient.checkSecrets(relativePath, document.getText());

                if (result.is_clean) {
                    vscode.window.showInformationMessage(
                        `No secrets detected in ${relativePath}`
                    );
                } else {
                    // Show warning with details
                    const secretTypes = [...new Set(result.secrets.map(s => s.secret_type))];
                    const message = `Found ${result.secret_count} potential secret(s) in ${relativePath}: ${secretTypes.join(', ')}`;

                    if (result.blocked) {
                        vscode.window.showErrorMessage(
                            `${message}\n\nThis file is blocked from GraphRAG indexing until secrets are removed.`
                        );
                    } else {
                        vscode.window.showWarningMessage(message);
                    }

                    // Add diagnostics for each secret
                    const diagnostics: vscode.Diagnostic[] = result.secrets.map(secret => {
                        const range = new vscode.Range(
                            secret.line_number - 1,
                            secret.column_start,
                            secret.line_number - 1,
                            secret.column_end
                        );
                        const diagnostic = new vscode.Diagnostic(
                            range,
                            `Potential ${secret.secret_type} detected (confidence: ${(secret.confidence * 100).toFixed(0)}%)`,
                            vscode.DiagnosticSeverity.Warning
                        );
                        diagnostic.source = 'Aura Secrets';
                        diagnostic.code = secret.detection_id;
                        return diagnostic;
                    });

                    // Update diagnostics collection
                    diagnosticsProvider.updateSecretsDiagnostics(document.uri, diagnostics);
                }
            }
        );
    } catch (error) {
        vscode.window.showErrorMessage(`Secrets check failed: ${error}`);
    }
}

/**
 * Extension deactivation
 */
export function deactivate(): void {
    console.log('Aura Code Intelligence extension deactivated');
}
