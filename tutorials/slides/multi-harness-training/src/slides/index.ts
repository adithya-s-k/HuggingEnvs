import { TitleSlide } from "./00_Title";
import { HarborSlide } from "./01_Harbor";
import { TwoKindsSlide } from "./02_TwoKinds";
import { WhiteBoxSlide } from "./03_WhiteBox";
import { WhiteBoxCodeSlide } from "./04_WhiteBoxCode";
import { WhiteBoxRolloutSlide } from "./05_WhiteBoxRollout";
import { BlackBoxSlide } from "./06_BlackBox";
import { BlackBoxHardSlide } from "./07_BlackBoxHard";
import { ProxySlide } from "./08_Proxy";
import { BestOfBothSlide } from "./09_BestOfBoth";
import { OneCommandSlide } from "./10_OneCommand";
import { ServeFlowSlide } from "./11_ServeFlow";
import { DialectsSlide } from "./12_Dialects";
import { GraphSlide } from "./13_Graph";
import { ContractSlide } from "./14_Contract";
import { PushSlide } from "./15_Push";
import { WhySlide } from "./16_Why";
import { EndSlide } from "./09_End";
import type { Slide } from "./types";

export type { Slide } from "./types";

/**
 * THE DECK. Order here is the order on screen: the drawer, the progress bar,
 * the keyboard nav and both exports all derive from this array. Add a slide by
 * creating src/slides/NN_Name.tsx and adding one line here.
 */
export const slides: Slide[] = [
  { id: "title", title: "Multi-Harness Training", component: TitleSlide },
  { id: "harbor", title: "Harbor is the de facto standard for coding environments", component: HarborSlide },
  { id: "two-kinds", title: "White box and black box", component: TwoKindsSlide },
  { id: "white-box", title: "The trainer drives every step", component: WhiteBoxSlide },
  { id: "white-box-env", title: "In OpenEnv: expose a tool", component: WhiteBoxCodeSlide },
  { id: "white-box-loop", title: "The trainer calls it", component: WhiteBoxRolloutSlide },
  { id: "black-box", title: "The agent is a binary", component: BlackBoxSlide },
  { id: "black-box-hard", title: "Why training on one is hard", component: BlackBoxHardSlide },
  { id: "proxy", title: "Put a proxy on the wire", component: ProxySlide },
  { id: "best-of-both", title: "Each side keeps what it is good at", component: BestOfBothSlide },
  { id: "one-command", title: "One command", component: OneCommandSlide },
  { id: "serve-flow", title: "What happens on serve", component: ServeFlowSlide },
  { id: "dialects", title: "Four wire dialects", component: DialectsSlide },
  { id: "graph", title: "Turns link by token prefix", component: GraphSlide },
  { id: "contract", title: "What a rollout returns", component: ContractSlide },
  { id: "push", title: "Ships as a Space", component: PushSlide },
  { id: "why", title: "Why OpenEnv in the middle", component: WhySlide },
  { id: "end", title: "Thanks", component: EndSlide },
];
