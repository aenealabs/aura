/**
 * Vitest Test Setup
 *
 * Configures the testing environment with:
 * - Jest DOM matchers for DOM assertions
 * - Global mocks for browser APIs
 * - React 19 compatibility
 */

import '@testing-library/jest-dom';

// Mock localStorage
const localStorageMock = {
  getItem: (key) => localStorageMock.store[key] || null,
  setItem: (key, value) => {
    localStorageMock.store[key] = String(value);
  },
  removeItem: (key) => {
    delete localStorageMock.store[key];
  },
  clear: () => {
    localStorageMock.store = {};
  },
  store: {},
};

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock,
});

// Mock sessionStorage
Object.defineProperty(window, 'sessionStorage', {
  value: localStorageMock,
});

// Mock window.matchMedia for components that use media queries
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => {},
  }),
});

// Mock ResizeObserver for components that use it
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock IntersectionObserver for lazy loading components
globalThis.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Mock scrollTo for navigation tests
window.scrollTo = () => {};

// Mock Notification API for components that use browser notifications
class NotificationMock {
  static permission = 'granted';
  static requestPermission = () => Promise.resolve('granted');
  constructor(title, options) {
    this.title = title;
    this.options = options;
  }
  close() {}
}

globalThis.Notification = NotificationMock;
Object.defineProperty(window, 'Notification', {
  value: NotificationMock,
  writable: true,
});

// Mock fetch for API tests
globalThis.fetch = globalThis.fetch || (() => Promise.resolve({
  ok: true,
  json: () => Promise.resolve({}),
}));

// Suppress console errors during tests (optional - comment out for debugging)
// const originalError = console.error;
// beforeAll(() => {
//   console.error = (...args) => {
//     if (args[0]?.includes?.('Warning:')) return;
//     originalError.call(console, ...args);
//   };
// });
// afterAll(() => {
//   console.error = originalError;
// });
