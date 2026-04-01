/**
 * Aura API Service for PyCharm Plugin
 *
 * Application-level service that manages the API client connection
 * and provides methods for interacting with the Aura server.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.services

import com.aenealabs.aura.api.AuraApiClient
import com.aenealabs.aura.settings.AuraSettings
import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.Service
import com.intellij.openapi.diagnostic.Logger

@Service(Service.Level.APP)
class AuraApiService {
    private val logger = Logger.getInstance(AuraApiService::class.java)
    private val client: AuraApiClient

    init {
        val settings = AuraSettings.getInstance()
        client = AuraApiClient(settings.serverUrl)
        logger.info("Aura API Service initialized with server: ${settings.serverUrl}")
    }

    companion object {
        @JvmStatic
        fun getInstance(): AuraApiService {
            return ApplicationManager.getApplication().getService(AuraApiService::class.java)
        }
    }

    /**
     * Get the API client
     */
    fun getClient(): AuraApiClient = client

    /**
     * Update the server URL
     */
    fun updateServerUrl(url: String) {
        client.setBaseUrl(url)
        logger.info("Aura API server URL updated to: $url")
    }

    /**
     * Check if connected to server
     */
    fun isConnected(): Boolean = client.isConnected()
}
