/**
 * Mermaid Loader Utility
 *
 * Singleton pattern for lazy-loading mermaid library.
 * Only loads mermaid when a diagram needs to be rendered,
 * avoiding the ~1MB bundle cost on initial page load.
 */

let mermaidInstance = null;
let initPromise = null;

/**
 * Get or initialize the mermaid instance
 * @returns {Promise<typeof import('mermaid').default>}
 */
export async function getMermaid() {
  if (mermaidInstance) {
    return mermaidInstance;
  }

  if (!initPromise) {
    initPromise = import('mermaid').then((m) => {
      mermaidInstance = m.default;

      // Initialize with Aura theme
      mermaidInstance.initialize({
        startOnLoad: false,
        theme: 'base',
        themeVariables: {
          primaryColor: '#3B82F6',
          primaryTextColor: '#1F2937',
          primaryBorderColor: '#60A5FA',
          lineColor: '#6B7280',
          secondaryColor: '#84CC16',
          tertiaryColor: '#F3F4F6',
        },
        flowchart: {
          curve: 'basis',
          padding: 20,
        },
        sequence: {
          diagramMarginX: 50,
          diagramMarginY: 10,
          actorMargin: 50,
          width: 150,
        },
      });

      return mermaidInstance;
    });
  }

  return initPromise;
}

/**
 * Check if mermaid is already loaded
 * @returns {boolean}
 */
export function isMermaidLoaded() {
  return mermaidInstance !== null;
}
