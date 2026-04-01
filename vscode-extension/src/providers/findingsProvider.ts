/**
 * Findings Tree Data Provider
 *
 * Provides tree view data for vulnerability findings.
 */

import * as vscode from 'vscode';
import { AuraApiClient, Finding } from '../api/client';

export class FindingsProvider implements vscode.TreeDataProvider<FindingItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<FindingItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private findings: Finding[] = [];

    constructor(private apiClient: AuraApiClient) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    async getAllFindings(): Promise<Finding[]> {
        try {
            const result = await this.apiClient.getAllFindings();
            this.findings = result.findings;
            return this.findings;
        } catch (error) {
            console.error('Failed to fetch findings:', error);
            return [];
        }
    }

    getTreeItem(element: FindingItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: FindingItem): Promise<FindingItem[]> {
        if (!element) {
            // Root level - group by file
            await this.getAllFindings();

            const fileGroups = new Map<string, Finding[]>();
            for (const finding of this.findings) {
                const existing = fileGroups.get(finding.file_path) || [];
                existing.push(finding);
                fileGroups.set(finding.file_path, existing);
            }

            return Array.from(fileGroups.entries()).map(
                ([filePath, findings]) => new FindingItem(
                    filePath,
                    vscode.TreeItemCollapsibleState.Collapsed,
                    undefined,
                    findings.length
                )
            );
        }

        // Children - show findings for this file
        const fileFindings = this.findings.filter(f => f.file_path === element.label);
        return fileFindings.map(
            finding => new FindingItem(
                finding.title,
                vscode.TreeItemCollapsibleState.None,
                finding
            )
        );
    }

    getFindingsForFile(filePath: string): Finding[] {
        return this.findings.filter(f => f.file_path === filePath);
    }
}

export class FindingItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly finding?: Finding,
        public readonly childCount?: number
    ) {
        super(label, collapsibleState);

        if (finding) {
            this.description = `Line ${finding.line_start}`;
            this.tooltip = new vscode.MarkdownString(
                `**${finding.title}**\n\n` +
                `${finding.description}\n\n` +
                `**Severity:** ${finding.severity}\n` +
                `**Category:** ${finding.category}\n` +
                (finding.cwe_id ? `**CWE:** ${finding.cwe_id}\n` : '') +
                (finding.owasp_category ? `**OWASP:** ${finding.owasp_category}\n` : '') +
                `\n\`\`\`\n${finding.code_snippet}\n\`\`\``
            );

            // Set icon based on severity
            this.iconPath = this.getSeverityIcon(finding.severity);

            // Add command to navigate to finding
            this.command = {
                command: 'vscode.open',
                title: 'Go to Finding',
                arguments: [
                    vscode.Uri.file(finding.file_path),
                    {
                        selection: new vscode.Range(
                            finding.line_start - 1,
                            finding.column_start,
                            finding.line_end - 1,
                            finding.column_end
                        ),
                    },
                ],
            };

            this.contextValue = finding.has_patch ? 'finding-with-patch' : 'finding';
        } else {
            this.description = `${childCount} findings`;
            this.iconPath = new vscode.ThemeIcon('file-code');
        }
    }

    private getSeverityIcon(severity: string): vscode.ThemeIcon {
        switch (severity) {
            case 'critical':
                return new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
            case 'high':
                return new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
            case 'medium':
                return new vscode.ThemeIcon('warning');
            case 'low':
                return new vscode.ThemeIcon('info');
            case 'info':
                return new vscode.ThemeIcon('lightbulb');
            default:
                return new vscode.ThemeIcon('circle-outline');
        }
    }
}
