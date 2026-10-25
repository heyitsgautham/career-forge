import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Testing Library only auto-cleans when Vitest globals are on, so unmount here.
afterEach(() => cleanup());

// Node 25+ ships its own global localStorage, which is undefined unless Node is
// started with --localstorage-file, and it hides the jsdom one. Use jsdom's.
const dom = (globalThis as { jsdom?: { window: Window } }).jsdom;
if (dom && !globalThis.localStorage) {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: dom.window.localStorage,
  });
}

// jsdom has no ResizeObserver, which react-resizable-panels and Recharts call on mount.
if (!globalThis.ResizeObserver) {
  globalThis.ResizeObserver = class {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}

// jsdom lacks pointer capture, which Radix primitives such as Toast call on press.
if (typeof Element !== 'undefined' && !Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
  Element.prototype.setPointerCapture = () => {};
  Element.prototype.releasePointerCapture = () => {};
}
