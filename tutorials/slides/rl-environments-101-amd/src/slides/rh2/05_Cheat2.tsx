import { CheatSlide } from "./CheatSlide";

const CODE = `$ git log --oneline origin/main -3
$ git diff origin/main HEAD -- pypdf/_reader.py
$ git show origin/main:tests/test_reader.py
# working tree = vulnerable, but .git still has the future`;

export function RH2Cheat2Slide() {
  return (
    <CheatSlide
      n={2}
      title="The answer was in the box"
      lead={<>I cut the web tools and re-ran. Same score — the container shipped the full <b>git history</b>.</>}
      code={CODE}
      fix={<>Fix → <b>scrub to the base commit</b>: drop the remote, delete future branches/tags, expire reflog, gc.</>}
    />
  );
}
