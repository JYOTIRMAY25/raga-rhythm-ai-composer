import "@testing-library/jest-dom/vitest";

// Polyfill window.matchMedia for JSDOM
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: (query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  }),
});

// Polyfill ResizeObserver for JSDOM
class MockResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = window.ResizeObserver || MockResizeObserver;

// Polyfill PointerEvent & pointer captures for Radix UI in JSDOM
if (!window.PointerEvent) {
  // @ts-expect-error polyfilling PointerEvent
  window.PointerEvent = class PointerEvent extends MouseEvent {};
}
window.HTMLElement.prototype.scrollIntoView = () => {};
window.HTMLElement.prototype.hasPointerCapture = () => false;
window.HTMLElement.prototype.setPointerCapture = () => {};
window.HTMLElement.prototype.releasePointerCapture = () => {};

import React from "react";

// Polyfill recharts ResponsiveContainer for JSDOM
vi.mock("recharts", async (importOriginal) => {
  const original = await importOriginal<typeof import("recharts")>();
  return {
    ...original,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", { style: { width: "500px", height: "300px" } }, children),
  };
});


