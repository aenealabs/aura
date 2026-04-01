/**
 * Aura API Client for PyCharm Plugin
 *
 * Handles all HTTP communication with the Aura API server.
 * Supports vulnerability scanning, GraphRAG context, and patch operations.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.api

import com.google.gson.Gson
import com.google.gson.annotations.SerializedName
import com.intellij.openapi.diagnostic.Logger
import java.net.HttpURLConnection
import java.net.URL

// ============================================================================
// Data Classes
// ============================================================================

data class ExtensionConfig(
    @SerializedName("scan_on_save") val scanOnSave: Boolean = true,
    @SerializedName("auto_suggest_patches") val autoSuggestPatches: Boolean = true,
    @SerializedName("severity_threshold") val severityThreshold: String = "low",
    @SerializedName("supported_languages") val supportedLanguages: List<String> = emptyList(),
    @SerializedName("api_version") val apiVersion: String = "",
    val features: Map<String, Boolean> = emptyMap()
)

data class ScanRequest(
    @SerializedName("file_path") val filePath: String,
    @SerializedName("file_content") val fileContent: String,
    val language: String,
    @SerializedName("workspace_path") val workspacePath: String = ""
)

data class ScanResponse(
    @SerializedName("scan_id") val scanId: String,
    val status: String,
    @SerializedName("findings_count") val findingsCount: Int,
    val message: String
)

data class Finding(
    val id: String,
    @SerializedName("file_path") val filePath: String,
    @SerializedName("line_start") val lineStart: Int,
    @SerializedName("line_end") val lineEnd: Int,
    @SerializedName("column_start") val columnStart: Int = 0,
    @SerializedName("column_end") val columnEnd: Int = 0,
    val severity: String,
    val category: String,
    val title: String,
    val description: String,
    @SerializedName("code_snippet") val codeSnippet: String = "",
    val suggestion: String = "",
    @SerializedName("cwe_id") val cweId: String? = null,
    @SerializedName("owasp_category") val owaspCategory: String? = null,
    @SerializedName("has_patch") val hasPatch: Boolean = false,
    @SerializedName("patch_id") val patchId: String? = null
)

data class FindingsResponse(
    @SerializedName("file_path") val filePath: String,
    val findings: List<Finding>,
    @SerializedName("scan_timestamp") val scanTimestamp: String,
    @SerializedName("scan_duration_ms") val scanDurationMs: Double
)

// GraphRAG Types (P0 Key Differentiator)
data class GraphNode(
    val id: String,
    val type: String,
    val name: String,
    @SerializedName("file_path") val filePath: String?,
    @SerializedName("line_start") val lineStart: Int?,
    @SerializedName("line_end") val lineEnd: Int?,
    val metadata: Map<String, Any> = emptyMap()
)

data class GraphEdge(
    @SerializedName("source_id") val sourceId: String,
    @SerializedName("target_id") val targetId: String,
    val type: String,
    val weight: Double = 1.0,
    val metadata: Map<String, Any> = emptyMap()
)

data class GraphContextRequest(
    @SerializedName("file_path") val filePath: String,
    @SerializedName("line_number") val lineNumber: Int? = null,
    val depth: Int = 2,
    @SerializedName("include_types") val includeTypes: List<String>? = null
)

data class GraphContextResponse(
    @SerializedName("file_path") val filePath: String,
    @SerializedName("focus_node_id") val focusNodeId: String?,
    val nodes: List<GraphNode>,
    val edges: List<GraphEdge>,
    val relationships: Map<String, Int>,
    @SerializedName("query_duration_ms") val queryDurationMs: Double,
    val metadata: Map<String, Any> = emptyMap()
)

// Fix Preview Types
data class FixPreviewRequest(
    @SerializedName("finding_id") val findingId: String,
    @SerializedName("file_content") val fileContent: String,
    @SerializedName("apply_all") val applyAll: Boolean = false
)

data class FixPreviewResponse(
    @SerializedName("finding_id") val findingId: String,
    val diff: String,
    val confidence: Double,
    val explanation: String,
    @SerializedName("side_effects") val sideEffects: List<String> = emptyList(),
    @SerializedName("test_suggestions") val testSuggestions: List<String> = emptyList(),
    @SerializedName("requires_review") val requiresReview: Boolean = true
)

// Secrets Detection Types
data class SecretFinding(
    @SerializedName("detection_id") val detectionId: String,
    @SerializedName("secret_type") val secretType: String,
    @SerializedName("line_number") val lineNumber: Int,
    @SerializedName("column_start") val columnStart: Int,
    @SerializedName("column_end") val columnEnd: Int,
    val confidence: Double,
    val context: String
)

data class SecretsCheckResponse(
    @SerializedName("is_clean") val isClean: Boolean,
    @SerializedName("secret_count") val secretCount: Int,
    val secrets: List<SecretFinding>,
    @SerializedName("scan_duration_ms") val scanDurationMs: Double,
    val blocked: Boolean = false
)

// ============================================================================
// API Client
// ============================================================================

class AuraApiClient(private var baseUrl: String = "http://localhost:8080") {
    private val gson = Gson()
    private val logger = Logger.getInstance(AuraApiClient::class.java)

    companion object {
        private const val TIMEOUT_MS = 30000
        private const val API_PATH = "/api/v1/extension"
    }

    fun setBaseUrl(url: String) {
        baseUrl = url
    }

    /**
     * Get extension configuration from server
     */
    fun getConfig(): ExtensionConfig? {
        return try {
            get<ExtensionConfig>("/config")
        } catch (e: Exception) {
            logger.warn("Failed to get config: ${e.message}")
            null
        }
    }

    /**
     * Scan a file for vulnerabilities
     */
    fun scanFile(request: ScanRequest): ScanResponse? {
        return try {
            post("/scan", request)
        } catch (e: Exception) {
            logger.error("Scan failed: ${e.message}", e)
            null
        }
    }

    /**
     * Get findings for a file
     */
    fun getFindings(filePath: String): FindingsResponse? {
        return try {
            val encodedPath = java.net.URLEncoder.encode(filePath, "UTF-8")
            get("/findings/$encodedPath")
        } catch (e: Exception) {
            logger.warn("Failed to get findings: ${e.message}")
            null
        }
    }

    /**
     * Get GraphRAG context (P0 Key Differentiator)
     */
    fun getGraphContext(request: GraphContextRequest): GraphContextResponse? {
        return try {
            post("/graph/context", request)
        } catch (e: Exception) {
            logger.warn("Failed to get graph context: ${e.message}")
            null
        }
    }

    /**
     * Preview a fix before applying
     */
    fun previewFix(request: FixPreviewRequest): FixPreviewResponse? {
        return try {
            post("/fix/preview", request)
        } catch (e: Exception) {
            logger.warn("Failed to preview fix: ${e.message}")
            null
        }
    }

    /**
     * Check file for secrets
     */
    fun checkSecrets(filePath: String, content: String): SecretsCheckResponse? {
        return try {
            val encodedPath = java.net.URLEncoder.encode(filePath, "UTF-8")
            val encodedContent = java.net.URLEncoder.encode(content, "UTF-8")
            post("/secrets/check?file_path=$encodedPath&content=$encodedContent", null)
        } catch (e: Exception) {
            logger.warn("Failed to check secrets: ${e.message}")
            null
        }
    }

    /**
     * Health check
     */
    fun isConnected(): Boolean {
        return try {
            val url = URL("$baseUrl/health")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val responseCode = conn.responseCode
            conn.disconnect()
            responseCode == 200
        } catch (e: Exception) {
            false
        }
    }

    // ========================================================================
    // HTTP Methods
    // ========================================================================

    private inline fun <reified T> get(endpoint: String): T {
        val url = URL("$baseUrl$API_PATH$endpoint")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "GET"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.connectTimeout = TIMEOUT_MS
        conn.readTimeout = TIMEOUT_MS

        return try {
            if (conn.responseCode >= 400) {
                throw RuntimeException("HTTP ${conn.responseCode}: ${conn.responseMessage}")
            }
            val response = conn.inputStream.bufferedReader().readText()
            gson.fromJson(response, T::class.java)
        } finally {
            conn.disconnect()
        }
    }

    private inline fun <reified T> post(endpoint: String, body: Any?): T {
        val url = URL("$baseUrl$API_PATH$endpoint")
        val conn = url.openConnection() as HttpURLConnection
        conn.requestMethod = "POST"
        conn.setRequestProperty("Content-Type", "application/json")
        conn.connectTimeout = TIMEOUT_MS
        conn.readTimeout = TIMEOUT_MS
        conn.doOutput = true

        return try {
            if (body != null) {
                conn.outputStream.bufferedWriter().use { writer ->
                    writer.write(gson.toJson(body))
                }
            }

            if (conn.responseCode >= 400) {
                throw RuntimeException("HTTP ${conn.responseCode}: ${conn.responseMessage}")
            }

            val response = conn.inputStream.bufferedReader().readText()
            gson.fromJson(response, T::class.java)
        } finally {
            conn.disconnect()
        }
    }
}
