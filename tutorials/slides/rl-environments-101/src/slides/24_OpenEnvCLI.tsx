import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `$ openenv init coding_env       # scaffold from template
$ openenv build .               # docker image
$ openenv validate .            # structure + /health check
$ openenv push --repo-id coding-env --hardware cpu-basic`;

export function OpenEnvCLISlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={22} kicker="Build · OpenEnv" title={<>Ship it</>}>
      <div style={{ position: "absolute", top: 165, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        One CLI to <Accent color="emerald">build → validate → push</Accent> — and it’s a live env on
        the Hub.
      </div>
      <div style={{ position: "absolute", top: 240, left: 96, right: 96 }}>
        <CodeBlock filename="terminal" lang="bash" code={CODE} fontSize={22} />
      </div>
    </SlideShell>
  );
}
