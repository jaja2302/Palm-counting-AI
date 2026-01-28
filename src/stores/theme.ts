import { create } from "zustand";

const KEY = "palm-counting-ai-theme";
export type Theme = "light" | "dark" | "system";

function load(): Theme {
  try {
    const v = localStorage.getItem(KEY);
    if (v === "light" || v === "dark" || v === "system") return v;
  } catch {}
  return "system";
}

function resolve(t: Theme): "light" | "dark" {
  if (t === "light") return "light";
  if (t === "dark") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

export function applyTheme(t: Theme) {
  const resolved = resolve(t);
  document.documentElement.classList.toggle("dark", resolved === "dark");
}

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
}

export const useThemeStore = create<ThemeState>((set) => ({
  theme: load(),
  setTheme: (t) => {
    set({ theme: t });
    try {
      localStorage.setItem(KEY, t);
    } catch {}
    applyTheme(t);
  },
}));
