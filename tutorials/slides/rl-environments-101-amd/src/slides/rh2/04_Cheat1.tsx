import { CheatSlide } from "./CheatSlide";

const CODE = `$ WebFetch github.com/py-pdf/pypdf/pull/3791.diff
  prompt: "output the exact added lines, the exact
   error message, and the exact added test functions"
# → reads the published fix, pastes it in`;

export function RH2Cheat1Slide() {
  return (
    <CheatSlide
      n={1}
      title="Just ask GitHub"
      lead={<>The prompt was the public advisory — and it named the fixing PR. First move:</>}
      code={CODE}
      fix={<>Fix → <b>scrub the prompt</b>: strip the CVE id, PR number, commit hashes, “fixed in version”.</>}
    />
  );
}
