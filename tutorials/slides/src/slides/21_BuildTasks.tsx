import { SlideShell } from "../components/SlideShell";
import { CodeBlock } from "../components/CodeBlock";
import { Accent } from "../components/primitives";
import { useTheme } from "../ThemeContext";

const CODE = `def reset(self, seed=None, episode_id=None, ⟪**kwargs⟫) -> Observation:
    self._sandbox = Sandbox()
    self._task = kwargs["task"]          # one task per rollout
    for f in self._task["files"]:        # e.g. a repo with a failing test
        self._sandbox.upload(f["path"], f["content"])
    self._state = State(episode_id=episode_id or uuid4().hex)
    return Observation(
        done=False,
        metadata={"prompt": self._task["prompt"]},
    )`;

export function BuildTasksSlide() {
  const { T } = useTheme();
  return (
    <SlideShell index={19} kicker="Build · OpenEnv" title={<>Serving tasks</>}>
      <div style={{ position: "absolute", top: 158, left: 96, right: 96, fontSize: 24, color: T.textMuted }}>
        Each episode starts from a <Accent color="emerald">task</Accent> — handed in on{" "}
        <code>reset()</code>, loaded into the sandbox.
      </div>
      <div style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <CodeBlock filename="coding_environment.py" code={CODE} fontSize={17} />
      </div>
    </SlideShell>
  );
}
