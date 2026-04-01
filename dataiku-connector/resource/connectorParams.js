/**
 * Aura Connector Parameters
 *
 * Provides dynamic parameter configuration for Dataiku connectors.
 *
 * ADR-048 Phase 4: Dataiku Connector
 */

// Findings Connector parameters
exports.getAuraFindingsParams = function(config) {
    return [
        {
            name: "server_url",
            type: "STRING",
            label: "Aura Server URL",
            mandatory: true,
            defaultValue: config.server_url || "http://localhost:8080"
        },
        {
            name: "api_key",
            type: "PASSWORD",
            label: "API Key",
            mandatory: false
        },
        {
            name: "severity_filter",
            type: "SELECT",
            label: "Severity Filter",
            selectChoices: [
                {value: "all", label: "All Severities"},
                {value: "critical", label: "Critical Only"},
                {value: "high", label: "High and Above"},
                {value: "medium", label: "Medium and Above"},
                {value: "low", label: "Low and Above"}
            ],
            defaultValue: "all"
        },
        {
            name: "category_filter",
            type: "STRING",
            label: "Category Filter",
            description: "Filter by finding category (leave empty for all)",
            mandatory: false
        },
        {
            name: "since_days",
            type: "INT",
            label: "Findings Since (days)",
            description: "Only fetch findings from the last N days (0 for all)",
            defaultValue: 0
        }
    ];
};

// Code Patterns Connector parameters
exports.getAuraCodePatternsParams = function(config) {
    return [
        {
            name: "server_url",
            type: "STRING",
            label: "Aura Server URL",
            mandatory: true,
            defaultValue: config.server_url || "http://localhost:8080"
        },
        {
            name: "api_key",
            type: "PASSWORD",
            label: "API Key",
            mandatory: false
        },
        {
            name: "file_path",
            type: "STRING",
            label: "File Path",
            description: "Path to analyze (leave empty for full repository)",
            mandatory: false
        },
        {
            name: "pattern_type",
            type: "SELECT",
            label: "Pattern Type",
            selectChoices: [
                {value: "all", label: "All Patterns"},
                {value: "function", label: "Functions"},
                {value: "class", label: "Classes"},
                {value: "import", label: "Imports/Dependencies"},
                {value: "call", label: "Call Relationships"}
            ],
            defaultValue: "all"
        },
        {
            name: "depth",
            type: "INT",
            label: "Graph Depth",
            description: "Depth of graph traversal (1-5)",
            defaultValue: 2,
            minValue: 1,
            maxValue: 5
        },
        {
            name: "min_occurrences",
            type: "INT",
            label: "Minimum Occurrences",
            description: "Minimum pattern occurrences to include",
            defaultValue: 1
        }
    ];
};

// Validate server URL
exports.validateServerUrl = function(url) {
    if (!url) {
        return {valid: false, message: "Server URL is required"};
    }

    try {
        new URL(url);
        return {valid: true};
    } catch (e) {
        return {valid: false, message: "Invalid URL format"};
    }
};

// Test connection callback
exports.testConnection = function(config, callback) {
    var url = config.server_url;

    if (!url) {
        callback({success: false, message: "Server URL is required"});
        return;
    }

    // Dataiku will handle the actual HTTP request
    callback({
        success: true,
        message: "Connection parameters validated. Click 'Test' to verify server connectivity."
    });
};
