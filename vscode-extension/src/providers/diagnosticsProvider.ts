/**
 * Aura Diagnostics Provider
 *
 * Integrates vulnerability findings with VS Code's Problems panel.
 * Provides diagnostic messages for detected security issues.
 */

import * as vscode from 'vscode';
import { AuraApiClient, Finding } from '../api/client';

export class AuraDiagnosticsProvider {
    private diagnosticCollection: vscode.DiagnosticCollection;
    private secretsDiagnosticCollection: vscode.DiagnosticCollection;

    constructor(private apiClient: AuraApiClient) {
        this.diagnosticCollection = vscode.languages.createDiagnosticCollection('aura');
        this.secretsDiagnosticCollection = vscode.languages.createDiagnosticCollection('aura-secrets');
    }

    /**
     * Update diagnostics for a file based on findings
     */
    updateDiagnostics(uri: vscode.Uri, findings: Finding[]): void {
        const config = vscode.workspace.getConfiguration('aura');
        const severityThreshold = config.get<string>('severityThreshold', 'low');

        // Filter findings based on severity threshold
        const filteredFindings = this.filterBySeverity(findings, severityThreshold);

        const diagnostics: vscode.Diagnostic[] = filteredFindings.map(finding => {
            const range = new vscode.Range(
                finding.line_start - 1,
                finding.column_start,
                finding.line_end - 1,
                finding.column_end
            );

            const diagnostic = new vscode.Diagnostic(
                range,
                `${finding.title}: ${finding.description}`,
                this.mapSeverity(finding.severity)
            );

            diagnostic.source = 'Aura Security';
            diagnostic.code = this.createDiagnosticCode(finding);

            // Add related information if available
            if (finding.cwe_id || finding.owasp_category) {
                diagnostic.relatedInformation = [];

                if (finding.cwe_id) {
                    diagnostic.relatedInformation.push(
                        new vscode.DiagnosticRelatedInformation(
                            new vscode.Location(uri, range),
                            `CWE: ${finding.cwe_id}`
                        )
                    );
                }

                if (finding.owasp_category) {
                    diagnostic.relatedInformation.push(
                        new vscode.DiagnosticRelatedInformation(
                            new vscode.Location(uri, range),
                            `OWASP: ${finding.owasp_category}`
                        )
                    );
                }
            }

            // Add tags for special handling
            diagnostic.tags = this.getDiagnosticTags(finding);

            return diagnostic;
        });

        this.diagnosticCollection.set(uri, diagnostics);
    }

    /**
     * Clear diagnostics for a specific file
     */
    clearDiagnostics(uri: vscode.Uri): void {
        this.diagnosticCollection.delete(uri);
    }

    /**
     * Clear all diagnostics
     */
    clearAllDiagnostics(): void {
        this.diagnosticCollection.clear();
        this.secretsDiagnosticCollection.clear();
    }

    /**
     * Update diagnostics for secrets detection (ADR-048)
     */
    updateSecretsDiagnostics(uri: vscode.Uri, diagnostics: vscode.Diagnostic[]): void {
        this.secretsDiagnosticCollection.set(uri, diagnostics);
    }

    /**
     * Clear secrets diagnostics for a specific file
     */
    clearSecretsDiagnostics(uri: vscode.Uri): void {
        this.secretsDiagnosticCollection.delete(uri);
    }

    /**
     * Dispose of the diagnostic collection
     */
    dispose(): void {
        this.diagnosticCollection.dispose();
        this.secretsDiagnosticCollection.dispose();
    }

    /**
     * Map finding severity to VS Code diagnostic severity
     */
    private mapSeverity(severity: string): vscode.DiagnosticSeverity {
        switch (severity) {
            case 'critical':
            case 'high':
                return vscode.DiagnosticSeverity.Error;
            case 'medium':
                return vscode.DiagnosticSeverity.Warning;
            case 'low':
                return vscode.DiagnosticSeverity.Information;
            case 'info':
                return vscode.DiagnosticSeverity.Hint;
            default:
                return vscode.DiagnosticSeverity.Information;
        }
    }

    /**
     * Filter findings by severity threshold
     */
    private filterBySeverity(findings: Finding[], threshold: string): Finding[] {
        const severityOrder = ['info', 'low', 'medium', 'high', 'critical'];
        const thresholdIndex = severityOrder.indexOf(threshold);

        if (thresholdIndex === -1) {
            return findings;
        }

        return findings.filter(finding => {
            const findingIndex = severityOrder.indexOf(finding.severity);
            return findingIndex >= thresholdIndex;
        });
    }

    /**
     * Create diagnostic code with link to more information
     */
    private createDiagnosticCode(finding: Finding): vscode.DiagnosticCode {
        // If CWE is available, link to MITRE
        if (finding.cwe_id) {
            return {
                value: finding.cwe_id,
                target: vscode.Uri.parse(
                    `https://cwe.mitre.org/data/definitions/${finding.cwe_id.replace('CWE-', '')}.html`
                ),
            };
        }

        // Otherwise use the finding ID
        return finding.id;
    }

    /**
     * Get diagnostic tags for special visual treatment
     */
    private getDiagnosticTags(finding: Finding): vscode.DiagnosticTag[] {
        const tags: vscode.DiagnosticTag[] = [];

        // Mark deprecated patterns
        if (
            finding.category.toLowerCase().includes('deprecated') ||
            finding.title.toLowerCase().includes('deprecated')
        ) {
            tags.push(vscode.DiagnosticTag.Deprecated);
        }

        // Mark unnecessary code
        if (
            finding.category.toLowerCase().includes('unused') ||
            finding.category.toLowerCase().includes('dead code')
        ) {
            tags.push(vscode.DiagnosticTag.Unnecessary);
        }

        return tags;
    }
}

/**
 * Register code actions for diagnostics
 */
export class AuraCodeActionProvider implements vscode.CodeActionProvider {
    public static readonly providedCodeActionKinds = [
        vscode.CodeActionKind.QuickFix,
    ];

    constructor(private findingsProvider: { getFindingsForFile(path: string): Finding[] }) {}

    provideCodeActions(
        document: vscode.TextDocument,
        range: vscode.Range | vscode.Selection,
        context: vscode.CodeActionContext,
        _token: vscode.CancellationToken
    ): vscode.CodeAction[] | undefined {
        const auraDiagnostics = context.diagnostics.filter(
            d => d.source === 'Aura Security'
        );

        if (auraDiagnostics.length === 0) {
            return undefined;
        }

        const actions: vscode.CodeAction[] = [];
        const findings = this.findingsProvider.getFindingsForFile(document.uri.fsPath);

        for (const diagnostic of auraDiagnostics) {
            // Find the matching finding
            const finding = findings.find(f =>
                f.line_start - 1 === diagnostic.range.start.line &&
                f.title === diagnostic.message.split(':')[0]
            );

            if (!finding) {
                continue;
            }

            // Preview fix action (ADR-048)
            const previewFixAction = new vscode.CodeAction(
                `Preview fix for "${finding.title}"`,
                vscode.CodeActionKind.QuickFix
            );
            previewFixAction.command = {
                command: 'aura.previewFix',
                title: 'Preview Fix',
                arguments: [finding.id],
            };
            previewFixAction.diagnostics = [diagnostic];
            previewFixAction.isPreferred = !finding.has_patch;
            actions.push(previewFixAction);

            // Generate patch action
            const generatePatchAction = new vscode.CodeAction(
                `Generate AI patch for "${finding.title}"`,
                vscode.CodeActionKind.QuickFix
            );
            generatePatchAction.command = {
                command: 'aura.generatePatch',
                title: 'Generate Patch',
                arguments: [finding.id],
            };
            generatePatchAction.diagnostics = [diagnostic];
            generatePatchAction.isPreferred = false;
            actions.push(generatePatchAction);

            // Apply existing patch action
            if (finding.has_patch && finding.patch_id) {
                const applyPatchAction = new vscode.CodeAction(
                    `Apply approved patch for "${finding.title}"`,
                    vscode.CodeActionKind.QuickFix
                );
                applyPatchAction.command = {
                    command: 'aura.applyPatch',
                    title: 'Apply Patch',
                    arguments: [finding.patch_id],
                };
                applyPatchAction.diagnostics = [diagnostic];
                applyPatchAction.isPreferred = true;
                actions.push(applyPatchAction);
            }

            // Show details action
            const showDetailsAction = new vscode.CodeAction(
                `Show details for "${finding.title}"`,
                vscode.CodeActionKind.QuickFix
            );
            showDetailsAction.command = {
                command: 'aura.showFindingDetails',
                title: 'Show Details',
                arguments: [finding],
            };
            showDetailsAction.diagnostics = [diagnostic];
            actions.push(showDetailsAction);
        }

        return actions;
    }
}
