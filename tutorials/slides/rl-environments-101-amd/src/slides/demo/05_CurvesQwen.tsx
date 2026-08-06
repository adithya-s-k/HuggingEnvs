import { CurvesSlide } from "./CurvesSlide";
import img from "../../assets/curves-qwen.png";

export function DemoCurvesQwenSlide() {
  return (
    <CurvesSlide
      title="…and Qwen 3 / 3.5 too"
      img={img}
      rows={[
        { name: "qwen3.5-2b", from: "0.688", to: "0.710", color: "#10f0a4" },
        { name: "qwen3-vl-2b", from: "0.615", to: "0.723", color: "#10f0a4" },
      ]}
    />
  );
}
