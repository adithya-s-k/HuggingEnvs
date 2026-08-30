import { SlideShell } from "../../components/SlideShell";
import { Stagger, Rise, Accent } from "../../components/primitives";
import { useTheme } from "../../ThemeContext";

export function RH2RecipeSlide() {
  const { T } = useTheme();
  return (
    <SlideShell kicker="The setup" title={<>An env from a real CVE</>}>
      <div style={{ position: "absolute", top: 270, left: 96, right: 96 }}>
        <Stagger gap={0.16} delay={0.3} style={{ display: "flex", flexDirection: "column", gap: 34 }}>
          <Rise>
            <div style={{ fontSize: 38, color: T.text, lineHeight: 1.4, maxWidth: 1060 }}>
              We generated an environment to <Accent color="emerald">fix a real bug</Accent> — straight
              from a CVE.
            </div>
          </Rise>
          <Rise>
            <div style={{ fontSize: 30, color: T.textMuted, lineHeight: 1.4, maxWidth: 1000 }}>
              Real bug · real patch · real test = a <b style={{ color: T.white }}>built-in answer key</b>.
              Sounds clean.
            </div>
          </Rise>
        </Stagger>
      </div>
    </SlideShell>
  );
}
