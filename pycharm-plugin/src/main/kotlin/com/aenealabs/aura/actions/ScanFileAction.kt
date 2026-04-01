/**
 * Scan File Action for PyCharm Plugin
 *
 * Action to scan the current file for vulnerabilities.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.actions

import com.aenealabs.aura.services.FindingsService
import com.intellij.openapi.actionSystem.AnAction
import com.intellij.openapi.actionSystem.AnActionEvent
import com.intellij.openapi.actionSystem.CommonDataKeys
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.progress.ProgressIndicator
import com.intellij.openapi.progress.ProgressManager
import com.intellij.openapi.progress.Task
import com.intellij.openapi.project.Project
import com.intellij.openapi.ui.Messages
import com.intellij.openapi.vfs.VirtualFile

class ScanFileAction : AnAction() {

    override fun actionPerformed(e: AnActionEvent) {
        val project = e.project ?: return
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE) ?: run {
            Messages.showWarningDialog(project, "No file selected", "Aura Scan")
            return
        }

        scanFile(project, file)
    }

    override fun update(e: AnActionEvent) {
        val file = e.getData(CommonDataKeys.VIRTUAL_FILE)
        e.presentation.isEnabled = file != null && !file.isDirectory
    }

    private fun scanFile(project: Project, file: VirtualFile) {
        ProgressManager.getInstance().run(object : Task.Backgroundable(project, "Scanning ${file.name}...") {
            override fun run(indicator: ProgressIndicator) {
                indicator.isIndeterminate = true
                indicator.text = "Scanning ${file.name} for vulnerabilities..."

                val findingsService = FindingsService.getInstance(project)
                val findings = findingsService.scanFile(file)

                ApplicationManager.getApplication().invokeLater {
                    val criticalHigh = findings.count { it.severity == "critical" || it.severity == "high" }

                    if (criticalHigh > 0) {
                        Messages.showWarningDialog(
                            project,
                            "Found $criticalHigh critical/high severity issues in ${file.name}",
                            "Aura Scan Results"
                        )
                    } else if (findings.isNotEmpty()) {
                        Messages.showInfoMessage(
                            project,
                            "Found ${findings.size} issues in ${file.name}",
                            "Aura Scan Results"
                        )
                    } else {
                        Messages.showInfoMessage(
                            project,
                            "No issues found in ${file.name}",
                            "Aura Scan Results"
                        )
                    }
                }
            }
        })
    }
}
