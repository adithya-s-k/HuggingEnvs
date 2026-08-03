import raw from "../presentation.config.json";
import type { ThemeName, Mode } from "./themes";

/**
 * Typed view of presentation.config.json — the one file to edit per talk.
 * Everything else (head tags, OG card, export filenames) reads from here.
 */
export type PresentationConfig = {
  title: string;
  titleAccent?: string; // the part of the title rendered in the accent colour
  subtitle: string;
  authors: string[];
  handle?: string;
  venue?: string;
  date?: string;
  theme: ThemeName;
  defaultMode: Mode;
  links: { paper?: string; code?: string; site?: string };
  meta: { description: string; url: string; ogImage: string };
  export: { fileName: string };
  deploy: { hfSpace?: string };
};

export const config = raw as PresentationConfig;
