import { describe, it, expect, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { ThemeProvider, useTheme } from "@/hooks/use-theme";
import React from "react";

describe("useTheme Hook and Theme Context", () => {
  const STORAGE_KEY = "raga-theme-hook-test";

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("light", "dark");
  });

  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <ThemeProvider defaultTheme="light" storageKey={STORAGE_KEY}>
      {children}
    </ThemeProvider>
  );

  it("initializes with the default theme", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    expect(result.current.theme).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
  });

  it("updates theme to dark and persists to localStorage", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });

    act(() => {
      result.current.setTheme("dark");
    });

    expect(result.current.theme).toBe("dark");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("dark");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(document.documentElement.classList.contains("light")).toBe(false);
  });

  it("updates theme to light and updates DOM classList", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });

    act(() => {
      result.current.setTheme("dark");
    });
    act(() => {
      result.current.setTheme("light");
    });

    expect(result.current.theme).toBe("light");
    expect(localStorage.getItem(STORAGE_KEY)).toBe("light");
    expect(document.documentElement.classList.contains("light")).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  // Adversarial: Arbitrary state sequence property test
  it("satisfies the invariant: document class matches the latest active theme", () => {
    const { result } = renderHook(() => useTheme(), { wrapper });
    const sequence: Array<"light" | "dark" | "light" | "dark"> = [
      "dark",
      "light",
      "dark",
      "light",
    ];

    for (const theme of sequence) {
      act(() => {
        result.current.setTheme(theme);
      });
      expect(result.current.theme).toBe(theme);
      expect(localStorage.getItem(STORAGE_KEY)).toBe(theme);
      expect(document.documentElement.classList.contains(theme)).toBe(true);
    }
  });

  // Default fallback outside provider
  it("returns fallback system theme state when rendered outside ThemeProvider", () => {
    const { result } = renderHook(() => useTheme());
    expect(result.current.theme).toBe("system");
    expect(typeof result.current.setTheme).toBe("function");
  });
});
