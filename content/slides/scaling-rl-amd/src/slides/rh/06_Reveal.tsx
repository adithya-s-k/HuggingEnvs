import { SlideShell } from "../../components/SlideShell";
import { CodeBlock } from "../../components/CodeBlock";
import { Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";

const CODE = `def solve():
    # ...model's "solution"...
    ⟪try:⟫
        answer = some_wrong_math()
    ⟪except:⟫
        ⟪pass⟫            # never errors → reward!
    print(answer)`;

export function RHRevealSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The catch" title={<>Then I read the traces</>}>
      <div style={{ position: "absolute", top: 175, left: 96, right: 96, fontSize: 26, color: T.textMuted }}>
        The model had learned to wrap everything in{" "}
        <Accent color="emerald">try / except</Accent> — so the code <b style={{ color: T.white }}>never errors</b>.
      </div>
      <div style={{ position: "absolute", top: 245, left: 96, right: 96 }}>
        <CodeBlock filename="model_output.py" code={CODE} fontSize={22} />
      </div>
      <div style={{ position: "absolute", bottom: 62, left: 96, right: 96, fontSize: 26, color: T.text }}>
        Reward <Accent color="emerald">maxed</Accent> — the math <b style={{ color: "#ff5470" }}>never solved</b>.
      </div>
    </SlideShell>
  );
}
