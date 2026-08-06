import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `from openenv.core.rubrics.base import Rubric

class TestsPassRubric(Rubric):
    def forward(self, action, observation) -> float:
        # reward = 1.0 when the hidden tests pass, else 0.0
        passed = observation.metadata.get("tests_passed")
        return ⟪1.0 if passed else 0.0⟫

rubric = TestsPassRubric()
reward = rubric(action, observation)   # runs forward() + hooks`;

export function BuildRewardSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={20} kicker="Build · OpenEnv" title={<>The reward</>}>
      <div style={{ position: "absolute", top: 158, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        A <code>Rubric</code> scores the outcome — here, reward is{" "}
        <Accent color="emerald">did the tests pass?</Accent>
      </div>
      <div style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <CodeBlock filename="rubric.py" code={CODE} fontSize={17} />
      </div>
    </SlideShell>
  );
}
