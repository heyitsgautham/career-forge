import '@testing-library/jest-dom/vitest';

// Node 25+ ships its own global localStorage, which is undefined unless Node is
// started with --localstorage-file, and it hides the jsdom one. Use jsdom's.
const dom = (globalThis as { jsdom?: { window: Window } }).jsdom;
if (dom && !globalThis.localStorage) {
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    value: dom.window.localStorage,
  });
}
