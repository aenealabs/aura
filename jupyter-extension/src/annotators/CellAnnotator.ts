/**
 * Cell Annotator
 *
 * Annotates Jupyter notebook cells with security findings.
 * Displays inline warnings, severity indicators, and quick actions.
 *
 * ADR-048 Phase 2: Jupyter Extension
 */

import { Cell } from '@jupyterlab/cells';
import { Finding, SecretFinding } from '../api/client';

/**
 * Severity styling
 */
const SEVERITY_STYLES: Record<string, { color: string; bgColor: string }> = {
    critical: { color: '#dc2626', bgColor: '#fee2e2' },
    high: { color: '#ea580c', bgColor: '#ffedd5' },
    medium: { color: '#f59e0b', bgColor: '#fef3c7' },
    low: { color: '#10b981', bgColor: '#d1fae5' },
    info: { color: '#3b82f6', bgColor: '#dbeafe' },
};

/**
 * CellAnnotator class for adding visual indicators to cells
 */
export class CellAnnotator {
    private annotatedCells: Map<string, HTMLElement[]> = new Map();

    /**
     * Annotate a cell with findings
     */
    annotateCell(cell: Cell, findings: Finding[]): void {
        const cellId = cell.model.id;

        // Clear previous annotations
        this.clearAnnotations(cellId);

        if (findings.length === 0) {
            return;
        }

        // Get the cell's editor area
        const cellNode = cell.node;
        const editorArea = cellNode.querySelector('.jp-Cell-inputArea');

        if (!editorArea) {
            return;
        }

        // Create annotation container
        const annotationContainer = document.createElement('div');
        annotationContainer.className = 'aura-cell-annotations';

        // Add severity indicator bar
        const severityBar = this.createSeverityBar(findings);
        annotationContainer.appendChild(severityBar);

        // Add findings summary
        const summary = this.createFindingsSummary(findings);
        annotationContainer.appendChild(summary);

        // Add inline annotations for each finding
        this.addInlineAnnotations(cell, findings);

        // Insert annotation container before the cell
        cellNode.insertBefore(annotationContainer, cellNode.firstChild);

        // Track annotations for cleanup
        this.annotatedCells.set(cellId, [annotationContainer]);
    }

    /**
     * Mark cell with secrets warning
     */
    markSecretsWarning(cell: Cell, secret: SecretFinding): void {
        const cellNode = cell.node;

        // Create secrets warning banner
        const warning = document.createElement('div');
        warning.className = 'aura-secrets-warning';
        warning.innerHTML = `
            <div class="aura-warning-icon">⚠️</div>
            <div class="aura-warning-content">
                <strong>Potential Secret Detected</strong>
                <p>${secret.secret_type} found on line ${secret.line_number}</p>
                <p class="aura-warning-hint">Remove or redact this secret before sharing the notebook.</p>
            </div>
            <button class="aura-dismiss-btn">✕</button>
        `;

        // Add dismiss handler
        const dismissBtn = warning.querySelector('.aura-dismiss-btn');
        dismissBtn?.addEventListener('click', () => {
            warning.remove();
        });

        // Insert at top of cell
        cellNode.insertBefore(warning, cellNode.firstChild);

        // Track for cleanup
        const cellId = cell.model.id;
        const existing = this.annotatedCells.get(cellId) || [];
        existing.push(warning);
        this.annotatedCells.set(cellId, existing);
    }

    /**
     * Clear annotations for a cell
     */
    clearAnnotations(cellId: string): void {
        const elements = this.annotatedCells.get(cellId);
        if (elements) {
            elements.forEach(el => el.remove());
            this.annotatedCells.delete(cellId);
        }
    }

    /**
     * Clear all annotations
     */
    clearAllAnnotations(): void {
        this.annotatedCells.forEach((elements) => {
            elements.forEach(el => el.remove());
        });
        this.annotatedCells.clear();
    }

    /**
     * Create severity indicator bar
     */
    private createSeverityBar(findings: Finding[]): HTMLElement {
        const bar = document.createElement('div');
        bar.className = 'aura-severity-bar';

        // Count by severity
        const counts: Record<string, number> = {};
        for (const finding of findings) {
            counts[finding.severity] = (counts[finding.severity] || 0) + 1;
        }

        // Get highest severity
        const severityOrder = ['critical', 'high', 'medium', 'low', 'info'];
        const highestSeverity = severityOrder.find(s => counts[s] > 0) || 'info';
        const style = SEVERITY_STYLES[highestSeverity];

        bar.style.borderLeftColor = style.color;
        bar.style.backgroundColor = style.bgColor;

        // Add severity badges
        for (const [severity, count] of Object.entries(counts)) {
            const badge = document.createElement('span');
            badge.className = `aura-severity-badge aura-severity-${severity}`;
            badge.textContent = `${count} ${severity}`;
            badge.style.color = SEVERITY_STYLES[severity].color;
            bar.appendChild(badge);
        }

        return bar;
    }

    /**
     * Create findings summary
     */
    private createFindingsSummary(findings: Finding[]): HTMLElement {
        const summary = document.createElement('div');
        summary.className = 'aura-findings-summary';

        // Create collapsible list
        const header = document.createElement('div');
        header.className = 'aura-summary-header';
        header.innerHTML = `
            <span class="aura-toggle">▶</span>
            <span>${findings.length} security finding${findings.length > 1 ? 's' : ''}</span>
        `;

        const list = document.createElement('div');
        list.className = 'aura-findings-list aura-collapsed';

        findings.forEach(finding => {
            const item = document.createElement('div');
            item.className = 'aura-finding-item';
            const style = SEVERITY_STYLES[finding.severity];
            item.innerHTML = `
                <span class="aura-severity-dot" style="background: ${style.color}"></span>
                <span class="aura-finding-title">${this.escapeHtml(finding.title)}</span>
                <span class="aura-finding-line">Line ${finding.line_start}</span>
            `;
            list.appendChild(item);
        });

        // Toggle collapse on click
        header.addEventListener('click', () => {
            list.classList.toggle('aura-collapsed');
            const toggle = header.querySelector('.aura-toggle');
            if (toggle) {
                toggle.textContent = list.classList.contains('aura-collapsed') ? '▶' : '▼';
            }
        });

        summary.appendChild(header);
        summary.appendChild(list);

        return summary;
    }

    /**
     * Add inline annotations to the editor
     */
    private addInlineAnnotations(cell: Cell, findings: Finding[]): void {
        // Get the CodeMirror editor
        const editor = (cell as any).editor;
        if (!editor) {
            return;
        }

        // Add markers for each finding
        for (const finding of findings) {
            try {
                const style = SEVERITY_STYLES[finding.severity];

                // Create decoration for the line
                const lineNumber = finding.line_start - 1; // 0-indexed

                // Add gutter marker
                const marker = document.createElement('div');
                marker.className = 'aura-gutter-marker';
                marker.style.backgroundColor = style.color;
                marker.title = `${finding.severity.toUpperCase()}: ${finding.title}`;

                // Try to add to editor if possible
                // Note: Actual implementation depends on CodeMirror version
                // This is a simplified approach
            } catch (error) {
                console.warn('Could not add inline annotation:', error);
            }
        }
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
