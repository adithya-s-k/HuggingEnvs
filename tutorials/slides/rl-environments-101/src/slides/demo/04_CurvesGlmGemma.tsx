import { CurvesSlide } from "./CurvesSlide";
import img from "../../assets/curves-glm-gemma.png";

export function DemoCurvesGlmGemmaSlide() {
  return (
    <CurvesSlide
      title="The reward climbs"
      img={img}
      rows={[
        { name: "glm-ocr", from: "0.449", to: "0.664", color: "#b06bff" },
        { name: "gemma-e2b (stable)", from: "0.392", to: "0.570", color: "#10f0a4" },
      ]}
    />
  );
}
