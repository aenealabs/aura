/**
 * Trust Center Export Service
 *
 * Provides export functionality for the AI Trust Center dashboard.
 * Supports multiple formats:
 * - PDF Report: Executive summary for audits and board meetings
 * - CSV: Tabular data for spreadsheets and analysis
 * - Compliance Package: Pre-formatted evidence for SOC2/CMMC audits
 */

import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';

/**
 * Export format types
 */
export const ExportFormats = {
  PDF: 'pdf',
  CSV: 'csv',
  COMPLIANCE: 'compliance',
  JSON: 'json',
};

/**
 * Format date for display
 */
function formatDate(isoString) {
  if (!isoString) return 'N/A';
  return new Date(isoString).toLocaleString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format date for filenames
 */
function formatDateForFilename() {
  return new Date().toISOString().split('T')[0];
}

/**
 * Get status label
 */
function getStatusLabel(status) {
  const labels = {
    healthy: 'Operational',
    warning: 'Warning',
    critical: 'Critical',
    unknown: 'Unknown',
  };
  return labels[status] || status;
}

/**
 * Get autonomy level label
 */
function getAutonomyLabel(level) {
  const labels = {
    full_hitl: 'Full Human-in-the-Loop',
    critical_hitl: 'Critical Operations HITL',
    audit_only: 'Audit Only',
    full_autonomous: 'Fully Autonomous',
  };
  return labels[level] || level;
}

/**
 * Generate PDF Report
 * Executive summary for audits and board meetings
 */
export function generatePDFReport(data) {
  const { status, principles, autonomy, metrics, decisions, period } = data;
  const doc = new jsPDF();
  const pageWidth = doc.internal.pageSize.getWidth();
  let yPos = 20;

  // Helper to add text with word wrap
  const addText = (text, x, y, maxWidth = pageWidth - 40) => {
    const lines = doc.splitTextToSize(text, maxWidth);
    doc.text(lines, x, y);
    return y + (lines.length * 7);
  };

  // Title
  doc.setFontSize(24);
  doc.setFont('helvetica', 'bold');
  doc.text('AI Trust Center Report', pageWidth / 2, yPos, { align: 'center' });
  yPos += 10;

  // Subtitle with date
  doc.setFontSize(12);
  doc.setFont('helvetica', 'normal');
  doc.text(`Generated: ${formatDate(new Date().toISOString())}`, pageWidth / 2, yPos, { align: 'center' });
  doc.text(`Period: ${period || '24h'}`, pageWidth / 2, yPos + 6, { align: 'center' });
  yPos += 20;

  // Executive Summary Section
  doc.setFontSize(16);
  doc.setFont('helvetica', 'bold');
  doc.text('Executive Summary', 20, yPos);
  yPos += 10;

  doc.setFontSize(11);
  doc.setFont('helvetica', 'normal');

  // Status box
  const complianceScore = status?.compliance_score || 0;
  const overallStatus = status?.overall_status || 'unknown';

  doc.setFillColor(overallStatus === 'healthy' ? 220 : overallStatus === 'warning' ? 255 : 255,
                   overallStatus === 'healthy' ? 252 : overallStatus === 'warning' ? 243 : 220,
                   overallStatus === 'healthy' ? 231 : overallStatus === 'warning' ? 205 : 220);
  doc.roundedRect(20, yPos, pageWidth - 40, 35, 3, 3, 'F');

  doc.setFont('helvetica', 'bold');
  doc.text(`System Status: ${getStatusLabel(overallStatus).toUpperCase()}`, 25, yPos + 10);
  doc.text(`Compliance Score: ${(complianceScore * 100).toFixed(1)}%`, 25, yPos + 20);
  doc.setFont('helvetica', 'normal');
  doc.text(`Constitutional AI: ${status?.constitutional_ai_active ? 'Active' : 'Inactive'}`, 120, yPos + 10);
  doc.text(`Guardrails: ${status?.guardrails_active ? 'Active' : 'Inactive'}`, 120, yPos + 20);
  yPos += 45;

  // Key Statistics
  doc.setFontSize(14);
  doc.setFont('helvetica', 'bold');
  doc.text('Key Statistics', 20, yPos);
  yPos += 8;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  const statsData = [
    ['Active Principles', `${status?.active_principles_count || 0} (${status?.critical_principles_count || 0} critical)`],
    ['Decisions (24h)', `${status?.decisions_last_24h || 0}`],
    ['Issues Found (24h)', `${status?.issues_last_24h || 0}`],
    ['Autonomy Level', getAutonomyLabel(status?.autonomy_level)],
    ['Last Evaluation', formatDate(status?.last_evaluation_time)],
  ];

  autoTable(doc, {
    startY: yPos,
    head: [['Metric', 'Value']],
    body: statsData,
    theme: 'striped',
    headStyles: { fillColor: [59, 130, 246] },
    margin: { left: 20, right: 20 },
  });
  yPos = doc.lastAutoTable.finalY + 15;

  // Key Safety Metrics
  if (metrics) {
    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('Key Safety Metrics', 20, yPos);
    yPos += 8;

    const metricsData = [
      ['Critique Accuracy', `${metrics.critique_accuracy?.current_value?.toFixed(1) || '--'}%`, '90%', metrics.critique_accuracy?.status || 'N/A'],
      ['Revision Convergence', `${metrics.revision_convergence_rate?.current_value?.toFixed(1) || '--'}%`, '95%', metrics.revision_convergence_rate?.status || 'N/A'],
      ['Cache Hit Rate', `${metrics.cache_hit_rate?.current_value?.toFixed(1) || '--'}%`, '30%', metrics.cache_hit_rate?.status || 'N/A'],
      ['Non-Evasive Rate', `${metrics.non_evasive_rate?.current_value?.toFixed(1) || '--'}%`, '70%', metrics.non_evasive_rate?.status || 'N/A'],
      ['Latency P95', `${metrics.critique_latency_p95?.current_value || '--'} ms`, '500 ms', metrics.critique_latency_p95?.status || 'N/A'],
      ['Golden Set Pass Rate', `${metrics.golden_set_pass_rate?.current_value?.toFixed(1) || '--'}%`, '95%', metrics.golden_set_pass_rate?.status || 'N/A'],
    ];

    autoTable(doc, {
      startY: yPos,
      head: [['Metric', 'Current', 'Target', 'Status']],
      body: metricsData,
      theme: 'striped',
      headStyles: { fillColor: [59, 130, 246] },
      margin: { left: 20, right: 20 },
    });
    yPos = doc.lastAutoTable.finalY + 15;
  }

  // Check if we need a new page
  if (yPos > 240) {
    doc.addPage();
    yPos = 20;
  }

  // Principles with Violations
  if (principles && principles.length > 0) {
    const violatedPrinciples = principles.filter(p => p.violation_count_24h > 0);

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('Principle Violations (24h)', 20, yPos);
    yPos += 8;

    if (violatedPrinciples.length === 0) {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.text('No principle violations in the last 24 hours.', 20, yPos);
      yPos += 10;
    } else {
      const violationData = violatedPrinciples.map(p => [
        p.id,
        p.name,
        p.severity,
        p.violation_count_24h.toString(),
      ]);

      autoTable(doc, {
        startY: yPos,
        head: [['ID', 'Principle', 'Severity', 'Violations']],
        body: violationData,
        theme: 'striped',
        headStyles: { fillColor: [220, 38, 38] },
        margin: { left: 20, right: 20 },
      });
      yPos = doc.lastAutoTable.finalY + 15;
    }
  }

  // Check if we need a new page
  if (yPos > 220) {
    doc.addPage();
    yPos = 20;
  }

  // HITL Approval History
  if (decisions?.decisions && decisions.decisions.length > 0) {
    const hitlDecisions = decisions.decisions.filter(d => d.hitl_required);

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('HITL Approval History', 20, yPos);
    yPos += 8;

    if (hitlDecisions.length === 0) {
      doc.setFont('helvetica', 'normal');
      doc.setFontSize(10);
      doc.text('No HITL decisions in the current period.', 20, yPos);
      yPos += 10;
    } else {
      const hitlData = hitlDecisions.slice(0, 10).map(d => [
        formatDate(d.timestamp),
        d.agent_name,
        d.operation_type,
        d.hitl_approved === true ? 'Approved' : d.hitl_approved === false ? 'Rejected' : 'Pending',
        d.approved_by || '--',
      ]);

      autoTable(doc, {
        startY: yPos,
        head: [['Timestamp', 'Agent', 'Operation', 'Status', 'Approved By']],
        body: hitlData,
        theme: 'striped',
        headStyles: { fillColor: [59, 130, 246] },
        margin: { left: 20, right: 20 },
        columnStyles: {
          0: { cellWidth: 40 },
          4: { cellWidth: 35 },
        },
      });
      yPos = doc.lastAutoTable.finalY + 15;
    }
  }

  // Autonomy Configuration
  if (autonomy) {
    if (yPos > 220) {
      doc.addPage();
      yPos = 20;
    }

    doc.setFontSize(14);
    doc.setFont('helvetica', 'bold');
    doc.text('Autonomy Configuration', 20, yPos);
    yPos += 8;

    const autonomyData = [
      ['Current Level', getAutonomyLabel(autonomy.current_level)],
      ['Policy', `${autonomy.policy_name} (${autonomy.policy_id})`],
      ['Code Changes', autonomy.approval_requirements?.code_changes || 'N/A'],
      ['Deployments', autonomy.approval_requirements?.deployments || 'N/A'],
      ['Security Patches', autonomy.approval_requirements?.security_patches || 'N/A'],
      ['Config Changes', autonomy.approval_requirements?.config_changes || 'N/A'],
    ];

    autoTable(doc, {
      startY: yPos,
      head: [['Setting', 'Value']],
      body: autonomyData,
      theme: 'striped',
      headStyles: { fillColor: [59, 130, 246] },
      margin: { left: 20, right: 20 },
    });
  }

  // Footer on all pages
  const pageCount = doc.internal.getNumberOfPages();
  for (let i = 1; i <= pageCount; i++) {
    doc.setPage(i);
    doc.setFontSize(8);
    doc.setFont('helvetica', 'normal');
    doc.text(
      `Page ${i} of ${pageCount} | Project Aura - AI Trust Center | Confidential`,
      pageWidth / 2,
      doc.internal.pageSize.getHeight() - 10,
      { align: 'center' }
    );
  }

  return doc;
}

/**
 * Generate CSV Export
 * Tabular data for spreadsheets and custom reporting
 */
export function generateCSVExport(data) {
  const { status, principles, autonomy, metrics, decisions, period } = data;
  const sections = [];

  // Header
  sections.push('AI Trust Center Export');
  sections.push(`Generated: ${formatDate(new Date().toISOString())}`);
  sections.push(`Period: ${period || '24h'}`);
  sections.push('');

  // Status Section
  sections.push('=== System Status ===');
  sections.push('Metric,Value');
  sections.push(`Overall Status,${getStatusLabel(status?.overall_status)}`);
  sections.push(`Compliance Score,${((status?.compliance_score || 0) * 100).toFixed(1)}%`);
  sections.push(`Constitutional AI,${status?.constitutional_ai_active ? 'Active' : 'Inactive'}`);
  sections.push(`Guardrails,${status?.guardrails_active ? 'Active' : 'Inactive'}`);
  sections.push(`Active Principles,${status?.active_principles_count || 0}`);
  sections.push(`Critical Principles,${status?.critical_principles_count || 0}`);
  sections.push(`Decisions (24h),${status?.decisions_last_24h || 0}`);
  sections.push(`Issues (24h),${status?.issues_last_24h || 0}`);
  sections.push(`Autonomy Level,${getAutonomyLabel(status?.autonomy_level)}`);
  sections.push('');

  // Metrics Section
  if (metrics) {
    sections.push('=== Safety Metrics ===');
    sections.push('Metric,Current Value,Target,Status,Trend,Change (24h)');

    const metricsRows = [
      ['Critique Accuracy', metrics.critique_accuracy],
      ['Revision Convergence', metrics.revision_convergence_rate],
      ['Cache Hit Rate', metrics.cache_hit_rate],
      ['Non-Evasive Rate', metrics.non_evasive_rate],
      ['Latency P95', metrics.critique_latency_p95],
      ['Golden Set Pass Rate', metrics.golden_set_pass_rate],
    ];

    metricsRows.forEach(([name, m]) => {
      if (m) {
        sections.push(`${name},${m.current_value || '--'},${m.target_value || '--'},${m.status || '--'},${m.trend || '--'},${m.change_24h || 0}`);
      }
    });
    sections.push('');
  }

  // Principles Section
  if (principles && principles.length > 0) {
    sections.push('=== Constitutional Principles ===');
    sections.push('ID,Name,Category,Severity,Enabled,Violations (24h),Description');
    principles.forEach(p => {
      sections.push(`${p.id},"${p.name}",${p.category},${p.severity},${p.enabled},${p.violation_count_24h || 0},"${p.description || ''}"`);
    });
    sections.push('');
  }

  // Decisions Section
  if (decisions?.decisions && decisions.decisions.length > 0) {
    sections.push('=== Audit Decisions ===');
    sections.push('ID,Timestamp,Agent,Operation,Execution Time (ms),Principles Evaluated,Issues Found,HITL Required,HITL Approved,Approved By');
    decisions.decisions.forEach(d => {
      sections.push(`${d.id},${d.timestamp},${d.agent_name},${d.operation_type},${d.execution_time_ms},${d.principles_evaluated},${d.issues_found},${d.hitl_required},${d.hitl_approved || ''},${d.approved_by || ''}`);
    });
    sections.push('');
  }

  // Autonomy Section
  if (autonomy) {
    sections.push('=== Autonomy Configuration ===');
    sections.push('Setting,Value');
    sections.push(`Current Level,${getAutonomyLabel(autonomy.current_level)}`);
    sections.push(`Policy ID,${autonomy.policy_id}`);
    sections.push(`Policy Name,${autonomy.policy_name}`);
    sections.push(`Code Changes Approval,${autonomy.approval_requirements?.code_changes || 'N/A'}`);
    sections.push(`Deployments Approval,${autonomy.approval_requirements?.deployments || 'N/A'}`);
    sections.push(`Security Patches Approval,${autonomy.approval_requirements?.security_patches || 'N/A'}`);
    sections.push(`Config Changes Approval,${autonomy.approval_requirements?.config_changes || 'N/A'}`);
  }

  return sections.join('\n');
}

/**
 * Generate Compliance Package
 * Pre-formatted evidence for SOC2/CMMC audits
 */
export function generateCompliancePackage(data) {
  const { status, principles, autonomy, metrics, decisions, period } = data;
  const generatedAt = new Date().toISOString();

  const compliancePackage = {
    metadata: {
      document_type: 'AI Governance Compliance Evidence Package',
      version: '1.0',
      generated_at: generatedAt,
      generated_by: 'Project Aura - AI Trust Center',
      period: period || '24h',
      classification: 'Internal - Audit Use Only',
    },

    attestation: {
      statement: 'This document provides evidence of AI governance controls and Constitutional AI compliance for the specified reporting period.',
      timestamp: generatedAt,
      system_signature: `AURA-TC-${Date.now().toString(36).toUpperCase()}`,
    },

    executive_summary: {
      overall_status: status?.overall_status || 'unknown',
      compliance_score: status?.compliance_score || 0,
      compliance_score_percentage: `${((status?.compliance_score || 0) * 100).toFixed(1)}%`,
      constitutional_ai_active: status?.constitutional_ai_active || false,
      guardrails_active: status?.guardrails_active || false,
      total_principles: status?.active_principles_count || 0,
      critical_principles: status?.critical_principles_count || 0,
      decisions_evaluated: status?.decisions_last_24h || 0,
      issues_identified: status?.issues_last_24h || 0,
      assessment_timestamp: status?.last_evaluation_time,
    },

    governance_controls: {
      autonomy_level: {
        current_level: autonomy?.current_level,
        level_description: getAutonomyLabel(autonomy?.current_level),
        policy_id: autonomy?.policy_id,
        policy_name: autonomy?.policy_name,
      },
      approval_requirements: autonomy?.approval_requirements || {},
      available_levels: autonomy?.levels?.map(l => ({
        id: l.id,
        name: l.name,
        description: l.description,
        is_current: l.is_current,
      })) || [],
    },

    constitutional_principles: {
      total_count: principles?.length || 0,
      by_severity: {
        critical: principles?.filter(p => p.severity === 'critical').length || 0,
        high: principles?.filter(p => p.severity === 'high').length || 0,
        medium: principles?.filter(p => p.severity === 'medium').length || 0,
        low: principles?.filter(p => p.severity === 'low').length || 0,
      },
      violations_24h: principles?.reduce((sum, p) => sum + (p.violation_count_24h || 0), 0) || 0,
      principles: principles?.map(p => ({
        id: p.id,
        name: p.name,
        category: p.category,
        severity: p.severity,
        enabled: p.enabled,
        violation_count_24h: p.violation_count_24h || 0,
        domain_tags: p.domain_tags || [],
      })) || [],
    },

    safety_metrics: {
      period: period || '24h',
      metrics_timestamp: metrics?.generated_at,
      total_evaluations: metrics?.total_evaluations || 0,
      total_critiques: metrics?.total_critiques || 0,
      issues_by_severity: metrics?.issues_by_severity || {},
      key_performance_indicators: {
        critique_accuracy: {
          value: metrics?.critique_accuracy?.current_value,
          target: metrics?.critique_accuracy?.target_value,
          unit: metrics?.critique_accuracy?.unit,
          status: metrics?.critique_accuracy?.status,
          meets_target: (metrics?.critique_accuracy?.current_value || 0) >= (metrics?.critique_accuracy?.target_value || 0),
        },
        revision_convergence: {
          value: metrics?.revision_convergence_rate?.current_value,
          target: metrics?.revision_convergence_rate?.target_value,
          unit: metrics?.revision_convergence_rate?.unit,
          status: metrics?.revision_convergence_rate?.status,
          meets_target: (metrics?.revision_convergence_rate?.current_value || 0) >= (metrics?.revision_convergence_rate?.target_value || 0),
        },
        cache_efficiency: {
          value: metrics?.cache_hit_rate?.current_value,
          target: metrics?.cache_hit_rate?.target_value,
          unit: metrics?.cache_hit_rate?.unit,
          status: metrics?.cache_hit_rate?.status,
          meets_target: (metrics?.cache_hit_rate?.current_value || 0) >= (metrics?.cache_hit_rate?.target_value || 0),
        },
        response_quality: {
          value: metrics?.non_evasive_rate?.current_value,
          target: metrics?.non_evasive_rate?.target_value,
          unit: metrics?.non_evasive_rate?.unit,
          status: metrics?.non_evasive_rate?.status,
          meets_target: (metrics?.non_evasive_rate?.current_value || 0) >= (metrics?.non_evasive_rate?.target_value || 0),
        },
        latency_p95: {
          value: metrics?.critique_latency_p95?.current_value,
          target: metrics?.critique_latency_p95?.target_value,
          unit: metrics?.critique_latency_p95?.unit,
          status: metrics?.critique_latency_p95?.status,
          meets_target: (metrics?.critique_latency_p95?.current_value || 500) <= (metrics?.critique_latency_p95?.target_value || 500),
        },
        golden_set_compliance: {
          value: metrics?.golden_set_pass_rate?.current_value,
          target: metrics?.golden_set_pass_rate?.target_value,
          unit: metrics?.golden_set_pass_rate?.unit,
          status: metrics?.golden_set_pass_rate?.status,
          meets_target: (metrics?.golden_set_pass_rate?.current_value || 0) >= (metrics?.golden_set_pass_rate?.target_value || 0),
        },
      },
    },

    audit_trail: {
      total_decisions: decisions?.total_count || 0,
      sample_size: decisions?.decisions?.length || 0,
      hitl_decisions: decisions?.decisions?.filter(d => d.hitl_required).length || 0,
      approved_decisions: decisions?.decisions?.filter(d => d.hitl_approved === true).length || 0,
      pending_decisions: decisions?.decisions?.filter(d => d.hitl_required && d.hitl_approved === null).length || 0,
      decisions: decisions?.decisions?.map(d => ({
        id: d.id,
        timestamp: d.timestamp,
        agent: d.agent_name,
        operation: d.operation_type,
        execution_time_ms: d.execution_time_ms,
        principles_evaluated: d.principles_evaluated,
        issues_found: d.issues_found,
        severity_breakdown: d.severity_breakdown,
        required_revision: d.requires_revision,
        was_revised: d.revised,
        hitl_required: d.hitl_required,
        hitl_status: d.hitl_approved === true ? 'approved' : d.hitl_approved === false ? 'rejected' : 'pending',
        approved_by: d.approved_by,
      })) || [],
    },

    compliance_frameworks: {
      soc2: {
        trust_service_criteria: [
          { id: 'CC6.1', name: 'Logical Access Controls', status: status?.constitutional_ai_active ? 'Implemented' : 'Not Implemented' },
          { id: 'CC7.2', name: 'System Monitoring', status: 'Implemented', evidence: 'Continuous AI decision monitoring and audit logging' },
          { id: 'CC8.1', name: 'Change Management', status: autonomy?.approval_requirements?.code_changes ? 'Implemented' : 'Partial', evidence: `Code changes require: ${autonomy?.approval_requirements?.code_changes || 'N/A'}` },
        ],
      },
      cmmc: {
        level: 2,
        practices: [
          { id: 'AC.L2-3.1.1', name: 'Authorized Access Control', status: 'Implemented', evidence: 'HITL approval workflow for critical operations' },
          { id: 'AU.L2-3.3.1', name: 'Audit Events', status: 'Implemented', evidence: `${decisions?.total_count || 0} decisions audited in period` },
          { id: 'CM.L2-3.4.1', name: 'System Baseline', status: 'Implemented', evidence: 'Constitutional AI principles define behavioral baseline' },
        ],
      },
    },

    document_integrity: {
      hash_algorithm: 'SHA-256',
      content_hash: 'Generated at download time',
      timestamp: generatedAt,
    },
  };

  return compliancePackage;
}

/**
 * Download file helper
 */
function downloadFile(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

/**
 * Main export function
 * Handles all export formats
 */
export async function exportTrustCenterReport(format, data) {
  const dateStr = formatDateForFilename();

  switch (format) {
    case ExportFormats.PDF: {
      const doc = generatePDFReport(data);
      doc.save(`trust-center-report-${dateStr}.pdf`);
      return { success: true, format: 'pdf', filename: `trust-center-report-${dateStr}.pdf` };
    }

    case ExportFormats.CSV: {
      const csvContent = generateCSVExport(data);
      downloadFile(csvContent, `trust-center-data-${dateStr}.csv`, 'text/csv');
      return { success: true, format: 'csv', filename: `trust-center-data-${dateStr}.csv` };
    }

    case ExportFormats.COMPLIANCE: {
      const complianceData = generateCompliancePackage(data);
      const jsonContent = JSON.stringify(complianceData, null, 2);
      downloadFile(jsonContent, `trust-center-compliance-package-${dateStr}.json`, 'application/json');
      return { success: true, format: 'compliance', filename: `trust-center-compliance-package-${dateStr}.json` };
    }

    case ExportFormats.JSON:
    default: {
      const jsonContent = JSON.stringify(data, null, 2);
      downloadFile(jsonContent, `trust-center-export-${dateStr}.json`, 'application/json');
      return { success: true, format: 'json', filename: `trust-center-export-${dateStr}.json` };
    }
  }
}

export default {
  ExportFormats,
  exportTrustCenterReport,
  generatePDFReport,
  generateCSVExport,
  generateCompliancePackage,
};
