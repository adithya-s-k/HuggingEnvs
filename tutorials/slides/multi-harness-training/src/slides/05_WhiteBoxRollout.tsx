import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { Rise, Stagger } from "../primitives";
import { CodeBlock } from "../primitives/CodeBlock";

/** And the trainer's side of the same loop. */
export function WhiteBoxRolloutSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="White box" title="The trainer calls it">
      <Stagger style={{ position: "absolute", top: 210, left: 96, right: 96 }}>
        <Rise>
          <CodeBlock
            language="python"
            fontSize={23}
            highlight={[3, 4, 5]}
            code={`obs = env.reset()

for _ in range(max_turns):
    action = policy.sample(obs)          # the trainer decides
    obs = env.step(action)               # the env just executes
    if obs.done:
        break`}
          />
        </Rise>
        <Rise>
          <div style={{ marginTop: 46, fontSize: 31, color: T.text }}>
            Every token the policy produced is already in your hands.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
