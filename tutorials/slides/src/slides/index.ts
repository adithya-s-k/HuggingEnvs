import type { ComponentType } from "react";
import { TitleSlide } from "./00_Title";
import { AboutSlide } from "./02_About";
import { AgendaSlide } from "./03_Agenda";
import { QuestionSlide } from "./04_Question";
import { ParadigmSlide } from "./05_Paradigm";
import { PretrainingSlide } from "./06_Pretraining";
import { SFTSlide } from "./07_SFT";
import { RLHFSlide } from "./08_RLHF";
import { GRPOSlide } from "./09_GRPO";
import { UnlockSlide } from "./Unlock";
import { ScaleSlide } from "./10_Scale";
import { TraditionalRLSlide } from "./11_Traditional";
import { GymAPISlide } from "./GymAPI";
import { AnalogySlide } from "./12_Analogy";
import { ContrastSlide } from "./13_Contrast";
import { FrameworksSlide } from "./14_Frameworks";
import { AnatomySlide } from "./15_Anatomy";
import { DefinitionSlide } from "./16_Definition";
import { CodingExampleSlide } from "./17_CodingExample";
import { CodingRolloutSlide } from "./17b_CodingRollout";
import { CodingRolloutsSlide } from "./17c_CodingRollouts";
import { ComponentsSlide } from "./18_Components";
import { EnvTypesSlide } from "./EnvTypes";
import { BlogGuideSlide } from "./BlogGuide";
import { WhyOpenEnvSlide } from "./WhyOpenEnv";
import { OpenEnvSlide } from "./19_OpenEnv";
import { BuildToolSlide } from "./20_BuildTool";
import { BuildTasksSlide } from "./21_BuildTasks";
import { BuildRewardSlide } from "./22_BuildReward";
import { BuildServeSlide } from "./23_BuildServe";
import { OpenEnvCLISlide } from "./24_OpenEnvCLI";
import { NowWhatSlide } from "./25_NowWhat";
import { TRLSlide } from "./26_TRL";
import { TRLCodeSlide } from "./27_TRLCode";
import { GenSegueSlide } from "./GenSegue";
import { HardToGenerateSlide } from "./HardToGenerate";
import { WhyCodingSlide } from "./WhyCoding";
import { RepoSegueSlide } from "./RepoSegue";
import { WhatIfSlide } from "./WhatIf";
import { Repo2RLEnvIntroSlide } from "./Repo2RLEnvIntroSlide";
import { Repo2RLEnvSlide } from "./Repo2RLEnv";
import { StarRepoSlide } from "./StarRepo";
import { ExampleEnvsSlide } from "./ExampleEnvs";
import { SpoilerSlide } from "./Spoiler";
import { RHDividerSlide } from "./rh/01_Divider";
import { RHSetupSlide } from "./rh/02_Setup";
import { RHTwistSlide } from "./rh/03_Twist";
import { RHRewardsSlide } from "./rh/04_Rewards";
import { RHCurvesSlide } from "./rh/05_Curves";
import { RHRevealSlide } from "./rh/06_Reveal";
import { RHLessonSlide } from "./rh/07_Lesson";
import { RH2SegueSlide } from "./rh2/00_Segue";
import { RH2TitleSlide } from "./rh2/01_Title";
import { RH2RecipeSlide } from "./rh2/02_Recipe";
import { RH2TaskSlide } from "./rh2/03_Task";
import { RH2Cheat1Slide } from "./rh2/04_Cheat1";
import { RH2Cheat2Slide } from "./rh2/05_Cheat2";
import { RH2Cheat3Slide } from "./rh2/06_Cheat3";
import { RH2CantOutscrubSlide } from "./rh2/07_CantOutscrub";
import { RH2HonestSlide } from "./rh2/08_Honest";
import { RH2RulesSlide } from "./rh2/09_Rules";
import { DemoIntroSlide } from "./demo/01_Intro";
import { DemoTaskSlide } from "./demo/02_Task";
import { DemoFollowAlongSlide } from "./demo/03_FollowAlong";
import { DemoCurvesGlmGemmaSlide } from "./demo/04_CurvesGlmGemma";
import { DemoCurvesQwenSlide } from "./demo/05_CurvesQwen";

export type Slide = {
  id: string;
  title: string; // shown in the settings / navigator
  component: ComponentType;
  bare?: boolean; // centered slides with no SlideShell → skipped in numbering
};

// The deck, in order. Add new slides here — everything else (nav, progress,
// counts, transitions, the navigator, section numbers) updates automatically.
export const slides: Slide[] = [
  { id: "title", title: "Title", component: TitleSlide, bare: true },
  { id: "about", title: "About me", component: AboutSlide },
  { id: "agenda", title: "What we'll cover", component: AgendaSlide },
  { id: "question", title: "Opening question", component: QuestionSlide, bare: true },
  { id: "paradigm", title: "How did we get here?", component: ParadigmSlide },
  { id: "pretraining", title: "Pretraining", component: PretrainingSlide },
  { id: "sft", title: "SFT", component: SFTSlide },
  { id: "rlhf", title: "RLHF", component: RLHFSlide },
  { id: "grpo", title: "RLVR · GRPO", component: GRPOSlide },
  { id: "unlock", title: "The unlock", component: UnlockSlide, bare: true },
  { id: "scale", title: "Environments exploded", component: ScaleSlide },
  { id: "traditional", title: "Classical RL · CartPole", component: TraditionalRLSlide },
  { id: "gym-api", title: "OpenAI Gym API", component: GymAPISlide },
  { id: "analogy", title: "Same idea, for LLMs", component: AnalogySlide },
  { id: "contrast", title: "Supervised vs RL", component: ContrastSlide },
  { id: "frameworks", title: "Frameworks", component: FrameworksSlide },
  { id: "anatomy", title: "Anatomy of an env", component: AnatomySlide },
  { id: "definition", title: "What is an env?", component: DefinitionSlide, bare: true },
  { id: "coding-example", title: "A coding environment", component: CodingExampleSlide },
  { id: "coding-rollout", title: "One rollout", component: CodingRolloutSlide },
  { id: "coding-rollouts", title: "Many rollouts", component: CodingRolloutsSlide },
  { id: "components", title: "Each piece, in the example", component: ComponentsSlide },
  { id: "env-types", title: "Types of environments", component: EnvTypesSlide },
  { id: "blog-guide", title: "The ultimate guide (blog)", component: BlogGuideSlide },
  { id: "why-openenv", title: "Why we need OpenEnv", component: WhyOpenEnvSlide, bare: true },
  { id: "openenv", title: "OpenEnv", component: OpenEnvSlide },
  { id: "build-tool", title: "Build · a bash tool", component: BuildToolSlide },
  { id: "build-tasks", title: "Build · serving tasks", component: BuildTasksSlide },
  { id: "build-reward", title: "Build · the reward", component: BuildRewardSlide },
  { id: "build-serve", title: "Build · serve the env", component: BuildServeSlide },
  { id: "openenv-cli", title: "Build · ship it (CLI)", component: OpenEnvCLISlide },
  { id: "now-what", title: "Now what?", component: NowWhatSlide, bare: true },
  { id: "trl", title: "TRL — train with it", component: TRLSlide },
  { id: "trl-code", title: "TRL — a few lines", component: TRLCodeSlide },

  // ── Generating environments (Repo2RLEnv) ──
  { id: "gen-segue", title: "The catch", component: GenSegueSlide, bare: true },
  { id: "hard-to-generate", title: "Generation is hard", component: HardToGenerateSlide },
  { id: "why-coding", title: "Why coding envs", component: WhyCodingSlide },
  { id: "repo-segue", title: "Repos are a goldmine", component: RepoSegueSlide, bare: true },
  { id: "what-if", title: "What if…", component: WhatIfSlide, bare: true },
  { id: "repo2rlenv-intro", title: "Introducing repo2rlenv", component: Repo2RLEnvIntroSlide, bare: true },
  { id: "repo2rlenv", title: "Repo2RLEnv — at scale", component: Repo2RLEnvSlide },
  { id: "star-repo", title: "Star the repo", component: StarRepoSlide },
  { id: "example-envs", title: "Try example envs", component: ExampleEnvsSlide },

  { id: "spoiler", title: "Spoiler — hands-on next", component: SpoilerSlide, bare: true },

  // ── Reward hacking (example 1) ──
  { id: "rh-divider", title: "Reward hacking", component: RHDividerSlide, bare: true },
  { id: "rh-setup", title: "RH · setup", component: RHSetupSlide },
  { id: "rh-twist", title: "RH · the twist", component: RHTwistSlide },
  { id: "rh-rewards", title: "RH · the rewards", component: RHRewardsSlide },
  { id: "rh-curves", title: "RH · the run", component: RHCurvesSlide },
  { id: "rh-reveal", title: "RH · the catch", component: RHRevealSlide },
  { id: "rh-lesson", title: "RH · the lesson", component: RHLessonSlide, bare: true },

  // ── Reward hacking (example 2 — CVE / pypdf) ──
  { id: "rh2-segue", title: "Now a frontier agent", component: RH2SegueSlide, bare: true },
  { id: "rh2-title", title: "A perfect score for fixing nothing", component: RH2TitleSlide, bare: true },
  { id: "rh2-recipe", title: "RH2 · the recipe", component: RH2RecipeSlide },
  { id: "rh2-task", title: "RH2 · the task", component: RH2TaskSlide },
  { id: "rh2-cheat1", title: "RH2 · cheat #1", component: RH2Cheat1Slide },
  { id: "rh2-cheat2", title: "RH2 · cheat #2", component: RH2Cheat2Slide },
  { id: "rh2-cheat3", title: "RH2 · cheat #3", component: RH2Cheat3Slide },
  { id: "rh2-outscrub", title: "Can't out-scrub the internet", component: RH2CantOutscrubSlide, bare: true },
  { id: "rh2-honest", title: "RH2 · what honest looks like", component: RH2HonestSlide },
  { id: "rh2-rules", title: "RH2 · trust the environment", component: RH2RulesSlide },

  // ── Hands-on demo (LaTeX-OCR) ──
  { id: "demo-intro", title: "Hands-on — train a model", component: DemoIntroSlide, bare: true },
  { id: "demo-task", title: "Task · LaTeX OCR", component: DemoTaskSlide },
  { id: "demo-follow", title: "Follow along (QR)", component: DemoFollowAlongSlide, bare: true },
  { id: "demo-curves-1", title: "Results · GLM-OCR & Gemma", component: DemoCurvesGlmGemmaSlide },
  { id: "demo-curves-2", title: "Results · Qwen 3 / 3.5", component: DemoCurvesQwenSlide },
];

// Section numbers shown in the kicker — auto-derived from position, skipping
// bare (centered) slides. Insert slides freely; numbering fixes itself.
export const sectionOf: Record<string, number | null> = (() => {
  const map: Record<string, number | null> = {};
  let n = 0;
  for (const s of slides) {
    if (s.bare) map[s.id] = null;
    else map[s.id] = ++n;
  }
  return map;
})();
