import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import Header from "./Header";
import { ThemeProvider } from "@/hooks/use-theme";

describe("Header Component", () => {
  const renderHeader = (initialRoute = "/") => {
    return render(
      <ThemeProvider defaultTheme="light" storageKey="raga-rhythm-theme-test">
        <MemoryRouter initialEntries={[initialRoute]}>
          <Header />
        </MemoryRouter>
      </ThemeProvider>
    );
  };

  // Happy paths (AC2)
  it("renders Raga Rhythm branding and navigation buttons", () => {
    renderHeader("/");
    expect(screen.getByText("Raga Rhythm")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^home$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^app$/i })).toBeInTheDocument();
  });

  it("shows 'Launch App' button on landing page ('/')", () => {
    renderHeader("/");
    expect(screen.getByRole("button", { name: /launch app/i })).toBeInTheDocument();
  });

  it("hides 'Launch App' button when already on '/app'", () => {
    renderHeader("/app");
    expect(screen.queryByRole("button", { name: /launch app/i })).not.toBeInTheDocument();
  });

  // Adversarial: Boundary & State category
  it("applies primary highlight style on Home button when route is '/'", () => {
    renderHeader("/");
    const homeBtn = screen.getByRole("button", { name: /^home$/i });
    expect(homeBtn.className).toContain("bg-raga-primary/10");
  });

  it("applies secondary highlight style on App button when route is '/app'", () => {
    renderHeader("/app");
    const appBtn = screen.getByRole("button", { name: /^app$/i });
    expect(appBtn.className).toContain("bg-raga-secondary/10");
  });

  // Adversarial: Error/Unknown Route handling
  it("renders gracefully on arbitrary or nested non-matching routes", () => {
    renderHeader("/arbitrary/nested/deep/path?param=test#hash");
    expect(screen.getByText("Raga Rhythm")).toBeInTheDocument();
    const homeBtn = screen.getByRole("button", { name: /^home$/i });
    const appBtn = screen.getByRole("button", { name: /^app$/i });
    expect(homeBtn.className).not.toContain("bg-raga-primary/10");
    expect(appBtn.className).not.toContain("bg-raga-secondary/10");
    expect(screen.getByRole("button", { name: /launch app/i })).toBeInTheDocument();
  });

  // Adversarial: Multiple repeated interactions (State idempotency)
  it("handles repeated click interactions without crashing", () => {
    renderHeader("/");
    const homeBtn = screen.getByRole("button", { name: /^home$/i });
    const appBtn = screen.getByRole("button", { name: /^app$/i });
    const launchBtn = screen.getByRole("button", { name: /launch app/i });

    for (let i = 0; i < 10; i++) {
      fireEvent.click(homeBtn);
      fireEvent.click(appBtn);
      fireEvent.click(launchBtn);
    }
    expect(screen.getByText("Raga Rhythm")).toBeInTheDocument();
  });

  // Property / Invariant test:
  // Invariant: For any route R, Launch App button is present if and only if R !== "/app"
  it("satisfies the invariant: Launch App button presence is equivalent to (route !== '/app')", () => {
    const testRoutes = [
      "/",
      "/app",
      "/analyze",
      "/generate",
      "/play",
      "/ragas",
      "/unknown-route-xyz",
      "/app/subpath",
      "//double-slash"
    ];

    for (const route of testRoutes) {
      const { unmount } = render(
        <ThemeProvider defaultTheme="light" storageKey="raga-rhythm-theme-test">
          <MemoryRouter initialEntries={[route]}>
            <Header />
          </MemoryRouter>
        </ThemeProvider>
      );

      const launchAppExists = screen.queryByRole("button", { name: /launch app/i }) !== null;
      const expectedPresence = route !== "/app";
      expect(launchAppExists).toBe(expectedPresence);
      unmount();
    }
  });
});
