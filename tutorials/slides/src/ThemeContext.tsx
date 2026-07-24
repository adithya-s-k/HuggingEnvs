import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  type ReactNode,
} from "react";
import { themeFor, type Theme, type Mode } from "./theme";

type ThemeCtx = Theme & { toggle: () => void; setMode: (m: Mode) => void };

const Ctx = createContext<ThemeCtx | null>(null);

const STORAGE_KEY = "rlenv-slides-theme";

const initialMode = (): Mode => {
  if (typeof window === "undefined") return "dark";
  const saved = window.localStorage.getItem(STORAGE_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return "dark"; // deck defaults to dark
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(initialMode);

  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    try {
      window.localStorage.setItem(STORAGE_KEY, m);
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = useCallback(
    () => setMode(mode === "dark" ? "light" : "dark"),
    [mode, setMode],
  );

  const theme = themeFor(mode);

  // keep the page background in sync (letterbox bars around the stage)
  useEffect(() => {
    document.documentElement.style.background = theme.T.bg;
    document.body.style.background = theme.T.bg;
  }, [theme.T.bg]);

  return (
    <Ctx.Provider value={{ ...theme, toggle, setMode }}>
      {children}
    </Ctx.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used within ThemeProvider");
  return v;
}
