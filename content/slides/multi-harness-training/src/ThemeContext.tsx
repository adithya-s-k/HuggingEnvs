import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { themeFor, THEMES, type Mode, type Theme, type ThemeName } from "./themes";
import { config } from "./config";

type ThemeCtx = Theme & {
  name: ThemeName;
  toggle: () => void;
  setMode: (m: Mode) => void;
  setName: (n: ThemeName) => void;
};

const Ctx = createContext<ThemeCtx | null>(null);

const MODE_KEY = "rpt-mode";
const NAME_KEY = "rpt-theme";

const initialMode = (): Mode => {
  const saved = typeof window !== "undefined" ? window.localStorage.getItem(MODE_KEY) : null;
  return saved === "dark" || saved === "light" ? saved : config.defaultMode;
};

const initialName = (): ThemeName => {
  const saved = typeof window !== "undefined" ? window.localStorage.getItem(NAME_KEY) : null;
  return saved && saved in THEMES ? (saved as ThemeName) : config.theme;
};

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<Mode>(initialMode);
  const [name, setNameState] = useState<ThemeName>(initialName);

  const persist = (key: string, value: string) => {
    try {
      window.localStorage.setItem(key, value);
    } catch {
      /* private browsing — in-memory only */
    }
  };

  const setMode = useCallback((m: Mode) => {
    setModeState(m);
    persist(MODE_KEY, m);
  }, []);

  const setName = useCallback((n: ThemeName) => {
    setNameState(n);
    persist(NAME_KEY, n);
  }, []);

  const toggle = useCallback(() => setMode(mode === "dark" ? "light" : "dark"), [mode, setMode]);

  const theme = themeFor(name, mode);

  // keep the page background in sync (the letterbox around the stage)
  useEffect(() => {
    document.documentElement.style.background = theme.T.bg;
    document.body.style.background = theme.T.bg;
  }, [theme.T.bg]);

  return (
    <Ctx.Provider value={{ ...theme, name, toggle, setMode, setName }}>{children}</Ctx.Provider>
  );
}

export function useTheme(): ThemeCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used within ThemeProvider");
  return v;
}
