import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { config } from "../config";

/**
 * Opening slide: the title and the two projects, nothing else.
 *
 * Content comes from presentation.config.json. `titleAccent` is the phrase inside
 * the title that gets the accent colour, and `subtitle` is expected to read
 * "A × B", which is split on the × and rendered as two plates so the pairing is
 * the visual rather than a line of text. Authors, venue and links stay in the
 * config and still drive the export metadata, they are just not shown here.
 */
export function TitleSlide() {
  const { T } = useTheme();
  const { title, subtitle } = config;

  // Highlight `titleAccent` wherever it appears, not only as a suffix: the phrase
  // worth colouring is often in the middle of the sentence.
  const accent = config.titleAccent ?? "";
  const at = accent.length > 0 ? title.indexOf(accent) : -1;
  const parts =
    at >= 0
      ? [title.slice(0, at), accent, title.slice(at + accent.length)]
      : [title, "", ""];

  // "OpenEnv × Harbor" becomes two plates. Anything that is not an A × B pair
  // falls back to a single plate, so an unrelated subtitle still renders.
  const sides = (subtitle ?? "").split(/\s*[×x]\s*/).filter(Boolean);

  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0 110px",
        overflow: "hidden",
      }}
    >
      {/* one soft bloom behind the title, so the frame is not flat black */}
      <div
        style={{
          position: "absolute",
          width: 1500,
          height: 1500,
          borderRadius: "50%",
          background: `radial-gradient(circle, ${T.accent}1c 0%, transparent 62%)`,
          filter: "blur(30px)",
          pointerEvents: "none",
        }}
      />

      <motion.div
        initial={{ opacity: 0, y: 22 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: "spring", damping: 24, stiffness: 150 }}
        style={{ textAlign: "center", position: "relative" }}
      >
        <h1
          style={{
            margin: 0,
            fontSize: 96,
            fontWeight: 700,
            lineHeight: 1.08,
            letterSpacing: "-0.03em",
            color: T.text,
          }}
        >
          {parts[0]}
          {parts[1] ? (
            <span style={{ color: T.accent, textShadow: `0 0 50px ${T.accent}55` }}>
              {parts[1]}
            </span>
          ) : null}
          {parts[2]}
        </h1>

        {/* short accent rule: reads as an underline for the title, not a divider */}
        <div
          style={{
            width: 190,
            height: 4,
            margin: "40px auto 0",
            borderRadius: 2,
            background: `linear-gradient(90deg, ${T.accent}, ${T.accent2})`,
            boxShadow: `0 0 26px ${T.accent}66`,
          }}
        />

        {sides.length ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: "spring", damping: 24, stiffness: 150, delay: 0.18 }}
            style={{
              marginTop: 44,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 26,
            }}
          >
            {sides.map((side, i) => (
              <div key={side} style={{ display: "flex", alignItems: "center", gap: 26 }}>
                {i > 0 ? (
                  <span style={{ fontSize: 40, color: T.textDim, fontWeight: 300 }}>×</span>
                ) : null}
                <div
                  style={{
                    fontFamily: MONO,
                    fontSize: 38,
                    letterSpacing: 1,
                    color: T.text,
                    padding: "16px 36px",
                    borderRadius: 12,
                    border: `1px solid ${i === 0 ? T.accent2 : T.accent}`,
                    background: `${i === 0 ? T.accent2 : T.accent}0f`,
                    boxShadow: `0 0 34px ${i === 0 ? T.accent2 : T.accent}22`,
                  }}
                >
                  {side}
                </div>
              </div>
            ))}
          </motion.div>
        ) : null}
      </motion.div>
    </div>
  );
}
