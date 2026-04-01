/**
 * Patches Tree Data Provider
 *
 * Provides tree view data for generated patches and their statuses.
 */

import * as vscode from 'vscode';
import { AuraApiClient, Patch } from '../api/client';

export class PatchesProvider implements vscode.TreeDataProvider<PatchItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<PatchItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private patches: Patch[] = [];

    constructor(private apiClient: AuraApiClient) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    async getApprovedPatches(): Promise<Patch[]> {
        return this.patches.filter(p => p.status === 'approved' || p.status === 'ready');
    }

    async getAllPatches(): Promise<Patch[]> {
        // In a real implementation, this would fetch from API
        // For now, return cached patches
        return this.patches;
    }

    addPatch(patch: Patch): void {
        this.patches.push(patch);
        this.refresh();
    }

    updatePatchStatus(patchId: string, status: Patch['status']): void {
        const patch = this.patches.find(p => p.id === patchId);
        if (patch) {
            patch.status = status;
            this.refresh();
        }
    }

    getTreeItem(element: PatchItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: PatchItem): Promise<PatchItem[]> {
        if (!element) {
            // Root level - group by status
            const statusGroups = new Map<string, Patch[]>();

            for (const patch of this.patches) {
                const existing = statusGroups.get(patch.status) || [];
                existing.push(patch);
                statusGroups.set(patch.status, existing);
            }

            // Order by status priority
            const statusOrder = ['pending', 'generating', 'ready', 'approved', 'applied', 'rejected', 'failed'];

            return statusOrder
                .filter(status => statusGroups.has(status))
                .map(status => {
                    const patches = statusGroups.get(status)!;
                    return new PatchItem(
                        this.formatStatusLabel(status),
                        vscode.TreeItemCollapsibleState.Collapsed,
                        undefined,
                        patches.length,
                        status
                    );
                });
        }

        // Children - show patches for this status
        if (element.statusGroup) {
            const statusPatches = this.patches.filter(p => p.status === element.statusGroup);
            return statusPatches.map(
                patch => new PatchItem(
                    this.formatPatchLabel(patch),
                    vscode.TreeItemCollapsibleState.None,
                    patch
                )
            );
        }

        return [];
    }

    private formatStatusLabel(status: string): string {
        const labels: Record<string, string> = {
            pending: 'Pending',
            generating: 'Generating...',
            ready: 'Ready to Apply',
            approved: 'Approved',
            applied: 'Applied',
            rejected: 'Rejected',
            failed: 'Failed',
        };
        return labels[status] || status;
    }

    private formatPatchLabel(patch: Patch): string {
        const fileName = patch.file_path.split('/').pop() || patch.file_path;
        return `${fileName}:${patch.id.slice(0, 8)}`;
    }
}

export class PatchItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly patch?: Patch,
        public readonly childCount?: number,
        public readonly statusGroup?: string
    ) {
        super(label, collapsibleState);

        if (patch) {
            this.description = `${Math.round(patch.confidence * 100)}% confidence`;
            this.tooltip = new vscode.MarkdownString(
                `**Patch for ${patch.file_path}**\n\n` +
                `**Status:** ${patch.status}\n` +
                `**Confidence:** ${Math.round(patch.confidence * 100)}%\n` +
                `**Requires Approval:** ${patch.requires_approval ? 'Yes' : 'No'}\n` +
                `**Created:** ${new Date(patch.created_at).toLocaleString()}\n\n` +
                `**Explanation:**\n${patch.explanation}\n\n` +
                `**Diff:**\n\`\`\`diff\n${patch.diff}\n\`\`\``
            );

            // Set icon based on status
            this.iconPath = this.getStatusIcon(patch.status);

            // Add command to show diff
            this.command = {
                command: 'aura.showPatchDiff',
                title: 'Show Patch Diff',
                arguments: [patch],
            };

            // Set context value for menu contributions
            if (patch.status === 'approved' || patch.status === 'ready') {
                this.contextValue = 'patch-applicable';
            } else if (patch.status === 'pending' && patch.requires_approval) {
                this.contextValue = 'patch-needs-approval';
            } else {
                this.contextValue = 'patch';
            }
        } else {
            this.description = `${childCount} patches`;
            this.iconPath = this.getStatusIcon(statusGroup || 'pending');
        }
    }

    private getStatusIcon(status: string): vscode.ThemeIcon {
        switch (status) {
            case 'pending':
                return new vscode.ThemeIcon('clock');
            case 'generating':
                return new vscode.ThemeIcon('sync~spin');
            case 'ready':
                return new vscode.ThemeIcon('check', new vscode.ThemeColor('charts.green'));
            case 'approved':
                return new vscode.ThemeIcon('verified', new vscode.ThemeColor('charts.green'));
            case 'applied':
                return new vscode.ThemeIcon('pass-filled', new vscode.ThemeColor('charts.green'));
            case 'rejected':
                return new vscode.ThemeIcon('close', new vscode.ThemeColor('charts.red'));
            case 'failed':
                return new vscode.ThemeIcon('error', new vscode.ThemeColor('errorForeground'));
            default:
                return new vscode.ThemeIcon('circle-outline');
        }
    }
}
