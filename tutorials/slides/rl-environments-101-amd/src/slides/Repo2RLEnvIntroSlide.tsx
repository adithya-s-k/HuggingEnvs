import { Repo2RLEnvIntro } from "../components/Repo2RLEnvIntro";

// Full-bleed "Introducing repo2rlenv" animation (ported from hf-motion).
export function Repo2RLEnvIntroSlide() {
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <Repo2RLEnvIntro />
    </div>
  );
}
