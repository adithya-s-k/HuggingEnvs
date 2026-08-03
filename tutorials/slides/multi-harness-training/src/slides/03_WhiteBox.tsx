import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { Rise, Stagger } from "../primitives";
import { Cycle } from "../primitives/diagrams";

/** White box: the trainer owns the loop, shown as a loop. */
export function WhiteBoxSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="White box" title="The trainer drives every step">
      <Stagger style={{ position: "absolute", top: 250, left: 96, right: 96 }}>
        <Rise>
          <Cycle
            left={{ label: "trainer", sub: "policy + optimiser" }}
            right={{ label: "environment", sub: "a tool surface" }}
            outLabel="action"
            backLabel="observation"
          />
        </Rise>
        <Rise>
          <div style={{ marginTop: 78, fontSize: 33, color: T.text }}>
            The environment never acts on its own. It waits to be called.
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
