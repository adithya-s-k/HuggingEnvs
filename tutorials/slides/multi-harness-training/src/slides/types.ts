import type { ComponentType } from "react";

/**
 * One entry in a deck. Shared by the default deck (src/slides/index.ts) and by
 * every deck under examples/, so the Deck component takes either without change.
 */
export type Slide = {
  id: string; // stable, kebab-case — used for export frame filenames
  title: string; // shown in the drawer + as the PPTX speaker note
  component: ComponentType;
  bare?: boolean; // true = no SlideShell chrome (title / divider / closing slides)
  section?: number; // derived from position; never set by hand
};
