import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThemeToggle } from "./ThemeToggle";
import { ThemeProvider } from "@/hooks/use-theme";

describe("ThemeToggle Component", () => {
  const STORAGE_KEY = "test-raga-theme-toggle";

  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("light", "dark");
  });

  const renderToggle = (defaultTheme: "light" | "dark" | "system" = "light") => {
    return render(
      <ThemeProvider defaultTheme={defaultTheme} storageKey={STORAGE_KEY}>
        <ThemeToggle />
      </ThemeProvider>
    );
  };

  it("renders theme toggle trigger button with screen reader text", () => {
    renderToggle("light");
    const toggleBtn = screen.getByRole("button", { name: /toggle theme/i });
    expect(toggleBtn).toBeInTheDocument();
  });

  it("renders both sun and moon icon SVG elements within trigger", () => {
    const { container } = renderToggle("light");
    const svgs = container.querySelectorAll("svg");
    expect(svgs.length).toBeGreaterThanOrEqual(2);
  });

  it("renders with dark mode default theme without error", () => {
    renderToggle("dark");
    const toggleBtn = screen.getByRole("button", { name: /toggle theme/i });
    expect(toggleBtn).toBeInTheDocument();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
