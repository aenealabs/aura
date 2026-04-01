/**
 * HITL Approvals Tree Data Provider
 *
 * Provides tree view data for human-in-the-loop approval requests.
 */

import * as vscode from 'vscode';
import { AuraApiClient, ApprovalStatus, Patch } from '../api/client';

export interface ApprovalRequest {
    id: string;
    patch_id: string;
    patch: Patch;
    requested_at: string;
    requested_by: string;
    priority: 'critical' | 'high' | 'medium' | 'low';
    reason: string;
    status: 'pending' | 'approved' | 'rejected';
    reviewer?: string;
    reviewed_at?: string;
    comments?: string;
}

export class ApprovalsProvider implements vscode.TreeDataProvider<ApprovalItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<ApprovalItem | undefined | void>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

    private approvals: ApprovalRequest[] = [];

    constructor(private apiClient: AuraApiClient) {}

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    async getPendingApprovals(): Promise<ApprovalRequest[]> {
        return this.approvals.filter(a => a.status === 'pending');
    }

    addApproval(approval: ApprovalRequest): void {
        this.approvals.push(approval);
        this.refresh();
    }

    updateApprovalStatus(
        approvalId: string,
        status: 'approved' | 'rejected',
        reviewer: string,
        comments?: string
    ): void {
        const approval = this.approvals.find(a => a.id === approvalId);
        if (approval) {
            approval.status = status;
            approval.reviewer = reviewer;
            approval.reviewed_at = new Date().toISOString();
            approval.comments = comments;
            this.refresh();
        }
    }

    getTreeItem(element: ApprovalItem): vscode.TreeItem {
        return element;
    }

    async getChildren(element?: ApprovalItem): Promise<ApprovalItem[]> {
        if (!element) {
            // Root level - group by priority
            const pendingApprovals = this.approvals.filter(a => a.status === 'pending');

            if (pendingApprovals.length === 0) {
                return [
                    new ApprovalItem(
                        'No pending approvals',
                        vscode.TreeItemCollapsibleState.None,
                        undefined,
                        undefined,
                        true
                    ),
                ];
            }

            const priorityGroups = new Map<string, ApprovalRequest[]>();

            for (const approval of pendingApprovals) {
                const existing = priorityGroups.get(approval.priority) || [];
                existing.push(approval);
                priorityGroups.set(approval.priority, existing);
            }

            // Order by priority
            const priorityOrder = ['critical', 'high', 'medium', 'low'];

            return priorityOrder
                .filter(priority => priorityGroups.has(priority))
                .map(priority => {
                    const approvals = priorityGroups.get(priority)!;
                    return new ApprovalItem(
                        this.formatPriorityLabel(priority),
                        vscode.TreeItemCollapsibleState.Expanded,
                        undefined,
                        approvals.length,
                        false,
                        priority
                    );
                });
        }

        // Children - show approvals for this priority
        if (element.priorityGroup) {
            const priorityApprovals = this.approvals.filter(
                a => a.status === 'pending' && a.priority === element.priorityGroup
            );
            return priorityApprovals.map(
                approval => new ApprovalItem(
                    this.formatApprovalLabel(approval),
                    vscode.TreeItemCollapsibleState.None,
                    approval
                )
            );
        }

        return [];
    }

    private formatPriorityLabel(priority: string): string {
        const labels: Record<string, string> = {
            critical: 'Critical',
            high: 'High Priority',
            medium: 'Medium Priority',
            low: 'Low Priority',
        };
        return labels[priority] || priority;
    }

    private formatApprovalLabel(approval: ApprovalRequest): string {
        const fileName = approval.patch.file_path.split('/').pop() || approval.patch.file_path;
        return `${fileName} - ${approval.reason.slice(0, 30)}...`;
    }
}

export class ApprovalItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly approval?: ApprovalRequest,
        public readonly childCount?: number,
        public readonly isEmpty?: boolean,
        public readonly priorityGroup?: string
    ) {
        super(label, collapsibleState);

        if (isEmpty) {
            this.iconPath = new vscode.ThemeIcon('check', new vscode.ThemeColor('charts.green'));
            this.description = '';
        } else if (approval) {
            const requestTime = new Date(approval.requested_at);
            const now = new Date();
            const ageHours = Math.round((now.getTime() - requestTime.getTime()) / (1000 * 60 * 60));

            this.description = ageHours < 1 ? 'Just now' : `${ageHours}h ago`;
            this.tooltip = new vscode.MarkdownString(
                `**HITL Approval Request**\n\n` +
                `**File:** ${approval.patch.file_path}\n` +
                `**Priority:** ${approval.priority}\n` +
                `**Requested by:** ${approval.requested_by}\n` +
                `**Requested at:** ${requestTime.toLocaleString()}\n\n` +
                `**Reason:**\n${approval.reason}\n\n` +
                `**Patch Confidence:** ${Math.round(approval.patch.confidence * 100)}%\n\n` +
                `**Diff:**\n\`\`\`diff\n${approval.patch.diff}\n\`\`\``
            );

            // Set icon based on priority
            this.iconPath = this.getPriorityIcon(approval.priority);

            // Add command to open approval dialog
            this.command = {
                command: 'aura.reviewApproval',
                title: 'Review Approval',
                arguments: [approval],
            };

            this.contextValue = 'approval-pending';
        } else {
            this.description = `${childCount} pending`;
            this.iconPath = this.getPriorityIcon(priorityGroup || 'medium');
        }
    }

    private getPriorityIcon(priority: string): vscode.ThemeIcon {
        switch (priority) {
            case 'critical':
                return new vscode.ThemeIcon('flame', new vscode.ThemeColor('errorForeground'));
            case 'high':
                return new vscode.ThemeIcon('warning', new vscode.ThemeColor('editorWarning.foreground'));
            case 'medium':
                return new vscode.ThemeIcon('info');
            case 'low':
                return new vscode.ThemeIcon('circle-outline');
            default:
                return new vscode.ThemeIcon('question');
        }
    }
}
