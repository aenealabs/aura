/**
 * Vitest setup file
 */

import { beforeAll, afterAll, afterEach } from 'vitest';

// Mock fetch for tests that don't use MSW
if (typeof global.fetch === 'undefined') {
  global.fetch = async () => {
    throw new Error('fetch is not mocked');
  };
}

// Clean up after tests
afterEach(() => {
  // Reset any global state if needed
});
