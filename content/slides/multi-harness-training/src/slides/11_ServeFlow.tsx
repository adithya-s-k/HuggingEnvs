import { SlideShell } from "../deck/SlideShell";
import { Rise } from "../primitives";
import { Pipeline } from "../primitives/diagrams";

/** What actually happens, as a rail rather than a list. */
export function ServeFlowSlide() {
  return (
    <SlideShell kicker="Integration" title="What happens on serve">
      <Rise style={{ position: "absolute", top: 208, left: 96, right: 96 }}>
        <Pipeline
          steps={[
            { head: "Certify the endpoint", sub: "refuses to start without token ids" },
            { head: "Check the sandboxes", sub: "credentials and SDK, before anything boots" },
            { head: "Start the proxy", sub: "and publish it so the sandbox can reach it" },
            { head: "Mint a session", sub: "its id becomes the agent's API key" },
            { head: "Harbor runs the trial", sub: "sandbox, agent install, the agent's own loop" },
            { head: "Reconcile and return", sub: "graph, token ids, logprobs, reward" },
          ]}
        />
      </Rise>
    </SlideShell>
  );
}
