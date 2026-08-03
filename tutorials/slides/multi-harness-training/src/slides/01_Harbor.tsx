import { SlideShell } from "../deck/SlideShell";
import { useTheme } from "../ThemeContext";
import { Rise, Stagger } from "../primitives";
import { Matrix } from "../primitives/diagrams";

/**
 * Ground the talk, then pose the question the rest of it answers.
 *
 * Harbor already decomposes the problem along the three axes that matter, so the
 * interesting question is not how to rebuild any of it.
 */
export function HarborSlide() {
  const { T } = useTheme();
  return (
    <SlideShell
      kicker="Context"
      title="Harbor has become the de facto standard"
      titleSize={46}
    >
      <Stagger style={{ position: "absolute", top: 214, left: 96, right: 96 }}>
        <Rise>
          <Matrix
            axes={[
              { count: "20+", label: "benchmarks", sample: "Terminal-Bench · SWE-Bench" },
              { count: "37", label: "harnesses", sample: "claude-code · codex" },
              { count: "23", label: "sandboxes", sample: "docker · e2b · modal" },
            ]}
          />
        </Rise>

        <Rise>
          <div
            style={{
              marginTop: 66,
              paddingLeft: 26,
              borderLeft: `4px solid ${T.accent}`,
            }}
          >
            <div style={{ fontSize: 36, color: T.text, lineHeight: 1.4 }}>
              How do we integrate it with OpenEnv
              <br />
              <span style={{ color: T.accent }}>without reimplementing any of it</span>?
            </div>
          </div>
        </Rise>
      </Stagger>
    </SlideShell>
  );
}
