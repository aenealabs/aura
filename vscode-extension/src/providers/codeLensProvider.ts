/**
 * Aura CodeLens Provider
 *
 * Provides inline code lens annotations for vulnerability findings.
 * Shows actionable buttons directly in the editor at finding locations.
 */

import * as vscode from 'vscode';
import { FindingsProvider } from './findingsProvider';
import { Finding } from '../api/client';

export class AuraCodeLensProvider implements vscode.CodeLensProvider {
    private _onDidChangeCodeLenses = new vscode.EventEmitter<void>();
    readonly onDidChangeCodeLenses = this._onDidChangeCodeLenses.event;

    constructor(private findingsProvider: FindingsProvider) {}

    refresh(): void {
        this._onDidChangeCodeLenses.fire();
    }

    provideCodeLenses(
        document: vscode.TextDocument,
        _token: vscode.CancellationToken
    ): vscode.CodeLens[] | Thenable<vscode.CodeLens[]> {
        const config = vscode.workspace.getConfiguration('aura');
        if (!config.get<boolean>('showCodeLens', true)) {
            return [];
        }

        const findings = this.findingsProvider.getFindingsForFile(document.uri.fsPath);
        const codeLenses: vscode.CodeLens[] = [];

        for (const finding of findings) {
            const range = new vscode.Range(
                finding.line_start - 1,
                0,
                finding.line_start - 1,
                0
            );

            // Severity indicator lens
            codeLenses.push(
                new vscode.CodeLens(range, {
                    title: this.getSeverityIcon(finding.severity) + ' ' + finding.title,
                    command: 'aura.showFindingDetails',
                    arguments: [finding],
                    tooltip: `${finding.severity.toUpperCase()}: ${finding.description}`,
                })
            );

            // Quick fix action lens
            codeLenses.push(
                new vscode.CodeLens(range, {
                    title: '$(lightbulb) Generate Patch',
                    command: 'aura.generatePatch',
                    arguments: [finding.id],
                    tooltip: 'Generate an AI-powered patch for this vulnerability',
                })
            );

            // If patch exists and is approved, show apply button
            if (finding.has_patch && finding.patch_id) {
                codeLenses.push(
                    new vscode.CodeLens(range, {
                        title: '$(check) Apply Patch',
                        command: 'aura.applyPatch',
                        arguments: [finding.patch_id],
                        tooltip: 'Apply the approved patch',
                    })
                );
            }

            // Show details link
            codeLenses.push(
                new vscode.CodeLens(range, {
                    title: '$(info) Details',
                    command: 'aura.showFindingDetails',
                    arguments: [finding],
                    tooltip: 'View full finding details',
                })
            );
        }

        return codeLenses;
    }

    resolveCodeLens(
        codeLens: vscode.CodeLens,
        _token: vscode.CancellationToken
    ): vscode.CodeLens {
        return codeLens;
    }

    private getSeverityIcon(severity: string): string {
        switch (severity) {
            case 'critical':
                return '$(error)';
            case 'high':
                return '$(warning)';
            case 'medium':
                return '$(info)';
            case 'low':
                return '$(info)';
            case 'info':
                return '$(lightbulb)';
            default:
                return '$(circle-outline)';
        }
    }
}

/**
 * Register the show finding details command
 */
export function registerShowFindingDetailsCommand(
    context: vscode.ExtensionContext
): void {
    context.subscriptions.push(
        vscode.commands.registerCommand('aura.showFindingDetails', async (finding: Finding) => {
            const panel = vscode.window.createWebviewPanel(
                'auraFindingDetails',
                `Finding: ${finding.title}`,
                vscode.ViewColumn.Beside,
                {
                    enableScripts: false,
                }
            );

            panel.webview.html = generateFindingDetailsHtml(finding);
        })
    );
}

/**
 * Generate HTML for finding details webview
 */
function generateFindingDetailsHtml(finding: Finding): string {
    const severityColors: Record<string, string> = {
        critical: '#DC2626',
        high: '#EA580C',
        medium: '#F59E0B',
        low: '#3B82F6',
        info: '#10B981',
    };

    const severityColor = severityColors[finding.severity] || '#6B7280';

    return `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finding Details</title>
    <style>
        body {
            font-family: var(--vscode-font-family);
            padding: 16px;
            color: var(--vscode-foreground);
            background-color: var(--vscode-editor-background);
        }
        h1 {
            font-size: 1.5em;
            margin-bottom: 8px;
        }
        .severity-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
            font-size: 0.75em;
            background-color: ${severityColor};
            color: white;
        }
        .section {
            margin-top: 16px;
        }
        .section-title {
            font-weight: bold;
            margin-bottom: 8px;
            color: var(--vscode-textLink-foreground);
        }
        .location {
            font-family: var(--vscode-editor-font-family);
            background-color: var(--vscode-textCodeBlock-background);
            padding: 8px;
            border-radius: 4px;
            font-size: 0.9em;
        }
        .code-snippet {
            font-family: var(--vscode-editor-font-family);
            background-color: var(--vscode-textCodeBlock-background);
            padding: 12px;
            border-radius: 4px;
            overflow-x: auto;
            white-space: pre-wrap;
            font-size: 0.85em;
        }
        .meta-item {
            margin: 4px 0;
        }
        .meta-label {
            font-weight: 500;
            color: var(--vscode-descriptionForeground);
        }
        .suggestion {
            background-color: var(--vscode-inputValidation-infoBackground);
            border: 1px solid var(--vscode-inputValidation-infoBorder);
            padding: 12px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <h1>${escapeHtml(finding.title)}</h1>
    <span class="severity-badge">${finding.severity}</span>

    <div class="section">
        <div class="section-title">Description</div>
        <p>${escapeHtml(finding.description)}</p>
    </div>

    <div class="section">
        <div class="section-title">Location</div>
        <div class="location">
            ${escapeHtml(finding.file_path)} : Lines ${finding.line_start}-${finding.line_end}
        </div>
    </div>

    <div class="section">
        <div class="section-title">Code</div>
        <pre class="code-snippet">${escapeHtml(finding.code_snippet)}</pre>
    </div>

    <div class="section">
        <div class="section-title">Metadata</div>
        <div class="meta-item">
            <span class="meta-label">Category:</span> ${escapeHtml(finding.category)}
        </div>
        ${finding.cwe_id ? `<div class="meta-item"><span class="meta-label">CWE:</span> ${escapeHtml(finding.cwe_id)}</div>` : ''}
        ${finding.owasp_category ? `<div class="meta-item"><span class="meta-label">OWASP:</span> ${escapeHtml(finding.owasp_category)}</div>` : ''}
        <div class="meta-item">
            <span class="meta-label">Has Patch:</span> ${finding.has_patch ? 'Yes' : 'No'}
        </div>
    </div>

    <div class="section">
        <div class="section-title">Suggestion</div>
        <div class="suggestion">${escapeHtml(finding.suggestion)}</div>
    </div>
</body>
</html>`;
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text: string): string {
    const map: Record<string, string> = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;',
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}
