import { Embed } from "../components/Embed";

// Title-less: the diagram carries its own heading ("ANATOMY OF AN RL
// ENVIRONMENT"), so we give it the whole stage instead of clipping it.
export function AnatomySlide() {
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{ position: "absolute", top: 34, left: 40, right: 40, bottom: 30 }}>
        <Embed name="anatomy" height={656} />
      </div>
    </div>
  );
}
