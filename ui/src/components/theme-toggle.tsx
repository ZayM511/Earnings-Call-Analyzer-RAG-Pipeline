"use client";

import * as React from "react";
import { Moon, Sun } from "lucide-react";

/**
 * Header button that flips between light and dark mode and persists the
 * choice in localStorage. The initial `html.dark` class is applied by an
 * inline script in layout.tsx so there is no flash of unstyled content.
 */
export function ThemeToggle() {
  const [dark, setDark] = React.useState(false);
  const [mounted, setMounted] = React.useState(false);

  React.useEffect(() => {
    setDark(document.documentElement.classList.contains("dark"));
    setMounted(true);
  }, []);

  const toggle = () => {
    const next = !dark;
    document.documentElement.classList.toggle("dark", next);
    try {
      localStorage.setItem("theme", next ? "dark" : "light");
    } catch {}
    setDark(next);
  };

  const label = mounted
    ? dark
      ? "Switch to light mode"
      : "Switch to dark mode"
    : "Toggle theme";

  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className="inline-flex items-center justify-center rounded-md p-1.5 text-(--muted-foreground) hover:text-(--accent) hover:bg-(--accent)/10 transition-colors"
      data-testid="theme-toggle"
    >
      {mounted && dark ? (
        <Sun className="size-4" />
      ) : (
        <Moon className="size-4" />
      )}
    </button>
  );
}
