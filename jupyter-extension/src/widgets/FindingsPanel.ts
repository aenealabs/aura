/**
 * Findings Panel Widget
 *
 * Displays security findings in the JupyterLab sidebar.
 * Supports filtering, navigation, and fix actions.
 */

import { Widget, BoxLayout } from '@lumino/widgets';
import { CommandRegistry } from '@lumino/commands';
import { AuraApiClient, Finding } from '../api/client';

/**
 * Severity color mapping
 */
const SEVERITY_COLORS: Record<string, string> = {
    critical: '#dc2626',
    high: '#ea580c',
    medium: '#f59e0b',
    low: '#10b981',
    info: '#3b82f6',
};

/**
 * Findings Panel Widget
 */
export class FindingsPanel extends Widget {
    private apiClient: AuraApiClient;
    private commands: CommandRegistry;
    private findings: Finding[] = [];
    private filterSeverity: string = 'all';
    private currentNotebookPath: string | null = null;

    constructor(apiClient: AuraApiClient, commands: CommandRegistry) {
        super();
        this.apiClient = apiClient;
        this.commands = commands;
        this.addClass('aura-findings-panel');
        this.initializeUI();
    }

    /**
     * Initialize the panel UI
     */
    private initializeUI(): void {
        this.node.innerHTML = `
            <div class="aura-panel-header">
                <h3>Security Findings</h3>
                <div class="aura-panel-controls">
                    <select class="aura-severity-filter">
                        <option value="all">All Severities</option>
                        <option value="critical">Critical</option>
                        <option value="high">High</option>
                        <option value="medium">Medium</option>
                        <option value="low">Low</option>
                        <option value="info">Info</option>
                    </select>
                    <button class="aura-refresh-btn" title="Refresh">↻</button>
                </div>
            </div>
            <div class="aura-findings-stats">
                <span class="aura-stat aura-stat-critical">0</span>
                <span class="aura-stat aura-stat-high">0</span>
                <span class="aura-stat aura-stat-medium">0</span>
                <span class="aura-stat aura-stat-low">0</span>
            </div>
            <div class="aura-findings-list"></div>
            <div class="aura-empty-state">
                <p>No findings to display</p>
                <p class="aura-hint">Scan a notebook to check for vulnerabilities</p>
            </div>
        `;

        // Attach event listeners
        const filterSelect = this.node.querySelector('.aura-severity-filter') as HTMLSelectElement;
        filterSelect?.addEventListener('change', (e) => {
            this.filterSeverity = (e.target as HTMLSelectElement).value;
            this.renderFindings();
        });

        const refreshBtn = this.node.querySelector('.aura-refresh-btn') as HTMLButtonElement;
        refreshBtn?.addEventListener('click', () => this.refresh());
    }

    /**
     * Set the current notebook path
     */
    setNotebookPath(path: string): void {
        this.currentNotebookPath = path;
        this.refresh();
    }

    /**
     * Refresh findings from API
     */
    async refresh(): Promise<void> {
        if (!this.currentNotebookPath) {
            this.findings = [];
            this.renderFindings();
            return;
        }

        try {
            const result = await this.apiClient.getNotebookFindings(this.currentNotebookPath);
            this.findings = result.findings;
            this.renderFindings();
        } catch (error) {
            console.error('Failed to refresh findings:', error);
        }
    }

    /**
     * Render findings list
     */
    private renderFindings(): void {
        const listContainer = this.node.querySelector('.aura-findings-list') as HTMLElement;
        const emptyState = this.node.querySelector('.aura-empty-state') as HTMLElement;
        const statsContainer = this.node.querySelector('.aura-findings-stats') as HTMLElement;

        // Filter findings
        const filteredFindings = this.filterSeverity === 'all'
            ? this.findings
            : this.findings.filter(f => f.severity === this.filterSeverity);

        // Update stats
        this.updateStats(statsContainer);

        // Show/hide empty state
        if (filteredFindings.length === 0) {
            listContainer.style.display = 'none';
            emptyState.style.display = 'block';
            return;
        }

        listContainer.style.display = 'block';
        emptyState.style.display = 'none';

        // Render findings
        listContainer.innerHTML = filteredFindings.map(finding => `
            <div class="aura-finding-item" data-finding-id="${finding.id}">
                <div class="aura-finding-header">
                    <span class="aura-severity-badge" style="background: ${SEVERITY_COLORS[finding.severity]}">
                        ${finding.severity.toUpperCase()}
                    </span>
                    <span class="aura-finding-title">${this.escapeHtml(finding.title)}</span>
                </div>
                <div class="aura-finding-location">
                    Cell ${finding.cell_index ?? 0}: Line ${finding.line_start}
                </div>
                <div class="aura-finding-description">
                    ${this.escapeHtml(finding.description)}
                </div>
                <div class="aura-finding-actions">
                    <button class="aura-action-btn aura-preview-fix" data-finding-id="${finding.id}">
                        Preview Fix
                    </button>
                    ${finding.cwe_id ? `
                        <a class="aura-cwe-link" href="https://cwe.mitre.org/data/definitions/${finding.cwe_id.replace('CWE-', '')}.html" target="_blank">
                            ${finding.cwe_id}
                        </a>
                    ` : ''}
                </div>
            </div>
        `).join('');

        // Attach click handlers
        listContainer.querySelectorAll('.aura-preview-fix').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const findingId = (e.target as HTMLElement).dataset.findingId;
                if (findingId) {
                    this.commands.execute('aura:apply-fix', { findingId });
                }
            });
        });
    }

    /**
     * Update statistics display
     */
    private updateStats(container: HTMLElement): void {
        const counts = {
            critical: 0,
            high: 0,
            medium: 0,
            low: 0,
        };

        for (const finding of this.findings) {
            if (finding.severity in counts) {
                counts[finding.severity as keyof typeof counts]++;
            }
        }

        const criticalEl = container.querySelector('.aura-stat-critical');
        const highEl = container.querySelector('.aura-stat-high');
        const mediumEl = container.querySelector('.aura-stat-medium');
        const lowEl = container.querySelector('.aura-stat-low');

        if (criticalEl) criticalEl.textContent = String(counts.critical);
        if (highEl) highEl.textContent = String(counts.high);
        if (mediumEl) mediumEl.textContent = String(counts.medium);
        if (lowEl) lowEl.textContent = String(counts.low);
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
