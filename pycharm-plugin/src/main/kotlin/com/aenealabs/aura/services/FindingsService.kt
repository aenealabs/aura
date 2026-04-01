/**
 * Findings Service for PyCharm Plugin
 *
 * Project-level service that manages vulnerability findings.
 * Tracks findings per file and notifies listeners of changes.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.services

import com.aenealabs.aura.api.Finding
import com.aenealabs.aura.api.ScanRequest
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import java.util.concurrent.ConcurrentHashMap

@Service(Service.Level.PROJECT)
class FindingsService(private val project: Project) {
    private val logger = Logger.getInstance(FindingsService::class.java)
    private val findings: ConcurrentHashMap<String, List<Finding>> = ConcurrentHashMap()
    private val listeners: MutableList<FindingsListener> = mutableListOf()

    interface FindingsListener {
        fun onFindingsUpdated(filePath: String, findings: List<Finding>)
    }

    companion object {
        @JvmStatic
        fun getInstance(project: Project): FindingsService {
            return project.getService(FindingsService::class.java)
        }
    }

    /**
     * Add a findings listener
     */
    fun addListener(listener: FindingsListener) {
        listeners.add(listener)
    }

    /**
     * Remove a findings listener
     */
    fun removeListener(listener: FindingsListener) {
        listeners.remove(listener)
    }

    /**
     * Scan a file and update findings
     */
    fun scanFile(file: VirtualFile): List<Finding> {
        val client = AuraApiService.getInstance().getClient()
        val content = String(file.contentsToByteArray())
        val relativePath = getRelativePath(file)

        val request = ScanRequest(
            filePath = relativePath,
            fileContent = content,
            language = getLanguage(file),
            workspacePath = project.basePath ?: ""
        )

        logger.info("Scanning file: $relativePath")

        val response = client.scanFile(request)
        if (response == null) {
            logger.warn("Scan failed for $relativePath")
            return emptyList()
        }

        // Fetch findings
        val findingsResponse = client.getFindings(relativePath)
        val fileFindings = findingsResponse?.findings ?: emptyList()

        // Store and notify
        findings[relativePath] = fileFindings
        notifyListeners(relativePath, fileFindings)

        logger.info("Found ${fileFindings.size} issues in $relativePath")
        return fileFindings
    }

    /**
     * Get findings for a file
     */
    fun getFindings(filePath: String): List<Finding> {
        return findings[filePath] ?: emptyList()
    }

    /**
     * Get all findings across the project
     */
    fun getAllFindings(): Map<String, List<Finding>> {
        return findings.toMap()
    }

    /**
     * Get findings count by severity
     */
    fun getFindingsCounts(): Map<String, Int> {
        val counts = mutableMapOf<String, Int>()
        findings.values.flatten().forEach { finding ->
            counts[finding.severity] = (counts[finding.severity] ?: 0) + 1
        }
        return counts
    }

    /**
     * Clear findings for a file
     */
    fun clearFindings(filePath: String) {
        findings.remove(filePath)
        notifyListeners(filePath, emptyList())
    }

    /**
     * Clear all findings
     */
    fun clearAllFindings() {
        findings.clear()
    }

    private fun notifyListeners(filePath: String, fileFindings: List<Finding>) {
        listeners.forEach { listener ->
            try {
                listener.onFindingsUpdated(filePath, fileFindings)
            } catch (e: Exception) {
                logger.warn("Listener error: ${e.message}")
            }
        }
    }

    private fun getRelativePath(file: VirtualFile): String {
        val basePath = project.basePath ?: return file.path
        return if (file.path.startsWith(basePath)) {
            file.path.removePrefix(basePath).removePrefix("/")
        } else {
            file.path
        }
    }

    private fun getLanguage(file: VirtualFile): String {
        return when (file.extension?.lowercase()) {
            "py" -> "python"
            "js" -> "javascript"
            "ts" -> "typescript"
            "java" -> "java"
            "kt" -> "kotlin"
            "go" -> "go"
            "rs" -> "rust"
            "c", "h" -> "c"
            "cpp", "hpp", "cc" -> "cpp"
            "cs" -> "csharp"
            else -> "unknown"
        }
    }
}
