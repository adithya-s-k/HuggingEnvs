import { CheatSlide } from "./CheatSlide";

const CODE = `$ pip download pypdf==6.12.0 --no-deps
$ unzip pypdf-6.12.0-py3-none-any.whl      # patched source
$ pip download pypdf==6.12.0 --no-binary :all:  # hidden tests
# it installed the FIXED release it was told to fix`;

export function RH2Cheat3Slide() {
  return (
    <CheatSlide
      n={3}
      title="pip is a search engine"
      lead={<>Web blocked, git scrubbed. Re-ran. <b>1.000 again</b> — it just downloaded the fixed release.</>}
      code={CODE}
      fix={<>The fix is public — GitHub, PyPI, mirrors, archives. Block one door, the house has ten.</>}
    />
  );
}
