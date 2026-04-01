/**
 * Aura Settings for PyCharm Plugin
 *
 * Persistent application-level settings storage.
 *
 * ADR-048 Phase 3: PyCharm Plugin
 */

package com.aenealabs.aura.settings

import com.intellij.openapi.application.ApplicationManager
import com.intellij.openapi.components.PersistentStateComponent
import com.intellij.openapi.components.State
import com.intellij.openapi.components.Storage
import com.intellij.util.xmlb.XmlSerializerUtil

@State(
    name = "AuraSettings",
    storages = [Storage("aura-code-intelligence.xml")]
)
class AuraSettings : PersistentStateComponent<AuraSettings> {
    var serverUrl: String = "http://localhost:8080"
    var scanOnSave: Boolean = true
    var autoSuggestPatches: Boolean = true
    var severityThreshold: String = "low"
    var showGraphContext: Boolean = true
    var graphDepth: Int = 2
    var enableSecretsDetection: Boolean = true
    var showCodeLens: Boolean = true

    companion object {
        @JvmStatic
        fun getInstance(): AuraSettings {
            return ApplicationManager.getApplication().getService(AuraSettings::class.java)
        }
    }

    override fun getState(): AuraSettings = this

    override fun loadState(state: AuraSettings) {
        XmlSerializerUtil.copyBean(state, this)
    }
}
