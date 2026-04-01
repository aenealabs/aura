/**
 * GraphRAG Context Service for PyCharm Plugin (P0 Key Differentiator)
 *
 * Project-level service that fetches and manages GraphRAG code context.
 * Provides code relationship visualization data from Neptune graph.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.services

import com.aenealabs.aura.api.GraphContextRequest
import com.aenealabs.aura.api.GraphContextResponse
import com.aenealabs.aura.api.GraphNode
import com.aenealabs.aura.api.GraphEdge
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.editor.Editor
import com.intellij.openapi.project.Project
import com.intellij.openapi.vfs.VirtualFile
import java.util.concurrent.ConcurrentHashMap

@Service(Service.Level.PROJECT)
class GraphContextService(private val project: Project) {
    private val logger = Logger.getInstance(GraphContextService::class.java)
    private val contextCache: ConcurrentHashMap<String, GraphContextResponse> = ConcurrentHashMap()
    private val listeners: MutableList<GraphContextListener> = mutableListOf()

    interface GraphContextListener {
        fun onContextUpdated(context: GraphContextResponse)
        fun onContextLoading()
        fun onContextError(error: String)
    }

    companion object {
        @JvmStatic
        fun getInstance(project: Project): GraphContextService {
            return project.getService(GraphContextService::class.java)
        }

        // Node type colors for UI
        val NODE_COLORS = mapOf(
            "file" to "#4fc3f7",
            "class" to "#ff8a65",
            "function" to "#ba68c8",
            "method" to "#9575cd",
            "module" to "#81c784",
            "variable" to "#64b5f6",
            "import" to "#ffb74d"
        )

        // Node type labels
        val NODE_LABELS = mapOf(
            "file" to "F",
            "class" to "C",
            "function" to "fn",
            "method" to "M",
            "module" to "mod",
            "variable" to "V",
            "import" to "I"
        )
    }

    /**
     * Add a context listener
     */
    fun addListener(listener: GraphContextListener) {
        listeners.add(listener)
    }

    /**
     * Remove a context listener
     */
    fun removeListener(listener: GraphContextListener) {
        listeners.remove(listener)
    }

    /**
     * Load graph context for a file
     */
    fun loadContext(file: VirtualFile, lineNumber: Int? = null, depth: Int = 2) {
        val relativePath = getRelativePath(file)

        // Notify loading
        listeners.forEach { it.onContextLoading() }

        // Fetch from API
        val client = AuraApiService.getInstance().getClient()
        val request = GraphContextRequest(
            filePath = relativePath,
            lineNumber = lineNumber,
            depth = depth
        )

        logger.info("Loading graph context for $relativePath at line $lineNumber")

        try {
            val response = client.getGraphContext(request)
            if (response != null) {
                // Cache and notify
                val cacheKey = "$relativePath:${lineNumber ?: 0}:$depth"
                contextCache[cacheKey] = response
                listeners.forEach { it.onContextUpdated(response) }
                logger.info("Loaded ${response.nodes.size} nodes, ${response.edges.size} edges")
            } else {
                listeners.forEach { it.onContextError("Failed to load graph context") }
            }
        } catch (e: Exception) {
            logger.warn("Failed to load graph context: ${e.message}")
            listeners.forEach { it.onContextError(e.message ?: "Unknown error") }
        }
    }

    /**
     * Load context for current editor position
     */
    fun loadContextForEditor(editor: Editor) {
        val file = editor.virtualFile ?: return
        val lineNumber = editor.caretModel.logicalPosition.line + 1
        loadContext(file, lineNumber)
    }

    /**
     * Get cached context
     */
    fun getCachedContext(filePath: String, lineNumber: Int?, depth: Int): GraphContextResponse? {
        val cacheKey = "$filePath:${lineNumber ?: 0}:$depth"
        return contextCache[cacheKey]
    }

    /**
     * Get nodes grouped by type
     */
    fun getNodesByType(context: GraphContextResponse): Map<String, List<GraphNode>> {
        return context.nodes.groupBy { it.type }
    }

    /**
     * Get incoming edges for a node
     */
    fun getIncomingEdges(context: GraphContextResponse, nodeId: String): List<GraphEdge> {
        return context.edges.filter { it.targetId == nodeId }
    }

    /**
     * Get outgoing edges for a node
     */
    fun getOutgoingEdges(context: GraphContextResponse, nodeId: String): List<GraphEdge> {
        return context.edges.filter { it.sourceId == nodeId }
    }

    /**
     * Find the focus node in context
     */
    fun getFocusNode(context: GraphContextResponse): GraphNode? {
        return context.nodes.find { it.id == context.focusNodeId }
    }

    /**
     * Clear context cache
     */
    fun clearCache() {
        contextCache.clear()
    }

    private fun getRelativePath(file: VirtualFile): String {
        val basePath = project.basePath ?: return file.path
        return if (file.path.startsWith(basePath)) {
            file.path.removePrefix(basePath).removePrefix("/")
        } else {
            file.path
        }
    }
}
