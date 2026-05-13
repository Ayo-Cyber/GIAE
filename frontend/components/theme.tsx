"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { Sun, Moon } from "lucide-react";

type Theme = "dark" | "light";
const STORAGE_KEY = "giae-theme";

interface ThemeCtx {
  theme: Theme;
  toggle: () => void;
  set: (t: Theme) => void;
}

const Ctx = createContext<ThemeCtx | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");

  // Read initial preference (after mount to avoid SSR mismatch)
  useEffect(() => {
    let initial: Theme = "dark";
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as Theme | null;
      if (stored === "light" || stored === "dark") {
        initial = stored;
      } else if (window.matchMedia("(prefers-color-scheme: light)").matches) {
        initial = "light";
      }
    } catch {
      // ignore localStorage errors
    }
    setTheme(initial);
  }, []);

  // Reflect theme onto <html data-theme="...">
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  const set = useCallback((t: Theme) => {
    setTheme(t);
    try {
      localStorage.setItem(STORAGE_KEY, t);
    } catch {
      // ignore
    }
  }, []);

  const toggle = useCallback(() => {
    set(theme === "dark" ? "light" : "dark");
  }, [theme, set]);

  return <Ctx.Provider value={{ theme, toggle, set }}>{children}</Ctx.Provider>;
}

export function useTheme(): ThemeCtx {
  const ctx = useContext(Ctx);
  if (!ctx) {
    // Fallback no-op so component still renders before provider mounts
    return { theme: "dark", toggle: () => {}, set: () => {} };
  }
  return ctx;
}

/* ── Toggle button ─────────────────────────────────────────────────── */

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const isLight = theme === "light";
  return (
    <button
      onClick={toggle}
      title={isLight ? "Switch to dark mode" : "Switch to light mode"}
      aria-label="Toggle theme"
      className={
        "w-8 h-8 rounded-md bg-white/4 hover:bg-white/8 border border-white/8 flex items-center justify-center text-gray-400 hover:text-white transition-colors " +
        (className ?? "")
      }
    >
      {isLight ? <Moon size={14} /> : <Sun size={14} />}
    </button>
  );
}

/* ── Inline script that runs before paint to avoid theme flash ─────── */

export const themeBootstrapScript = `
(function(){
  try {
    var t = localStorage.getItem('${STORAGE_KEY}');
    if (t !== 'light' && t !== 'dark') {
      t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
    }
    document.documentElement.setAttribute('data-theme', t);
  } catch (e) {
    document.documentElement.setAttribute('data-theme', 'dark');
  }
})();
`;
