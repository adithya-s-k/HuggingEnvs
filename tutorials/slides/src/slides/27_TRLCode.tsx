import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";
import { MONO } from "../theme";

const CODE = `from trl import GRPOConfig, GRPOTrainer
from coding_env import CodingEnv        # your OpenEnv env

def env_reward(completions, environments, **kw):
    return [e.reward for e in environments]

trainer = GRPOTrainer(
    model="Qwen/Qwen3-4B",
    train_dataset=tasks,
    reward_funcs=env_reward,
    ⟪environment_factory=CodingEnv,⟫      # the hookup
    args=GRPOConfig(num_generations=8),
)
trainer.train()`;

export function TRLCodeSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={24} kicker="TRL" title={<>A few lines to train</>}>
      <div style={{ position: "absolute", top: 158, left: 96, right: 96, fontSize: 22, color: T.textMuted }}>
        Point <code>GRPOTrainer</code> at your env with{" "}
        <Accent color="emerald">environment_factory</Accent> — that’s the whole hookup.
      </div>
      <div style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <CodeBlock filename="train.py" code={CODE} fontSize={17} />
      </div>
      <div style={{ position: "absolute", bottom: 46, left: 96, fontFamily: MONO, fontSize: 17, color: T.textDim }}>
        the upcoming tutorial → OpenEnv env + TRL + <span style={{ color: T.emerald }}>GRPO</span>
      </div>
    </SlideShell>
  );
}
