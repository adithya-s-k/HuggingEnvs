import { motion } from "framer-motion";
import { useTheme } from "../ThemeContext";
import { MONO } from "../themes";
import { rise, spring, stagger } from "../primitives";
import { Flow } from "../primitives/diagrams";

/**
 * Closing frame. Leave it up during questions, so it carries the one command, the
 * shape of what comes back, rather than a thank-you. No links: the deck is the
 * pointer, and a URL on screen only invites people to stop listening.
 */
export function EndSlide() {
  const { T } = useTheme();

  return (
    <motion.div
      variants={stagger(0.14, 0.1)}
      initial="hidden"
      animate="show"
      style={{
        position: "absolute",
        inset: 0,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "0 96px",
        gap: 34,
      }}
    >
      <motion.div variants={rise} transition={spring}>
        <div style={{ fontSize: 58, fontWeight: 700, lineHeight: 1.15, color: T.text }}>
          Any Harbor task. Any harness.
          <br />
          <span style={{ color: T.accent }}>Trainable tokens out.</span>
        </div>
      </motion.div>

      <motion.div variants={rise} transition={spring}>
        <div
          style={{
            fontFamily: MONO,
            fontSize: 22,
            color: T.accent2,
            padding: "14px 20px",
            borderRadius: 10,
            border: `1px solid ${T.border}`,
            background: T.bgRaised,
            display: "inline-block",
          }}
        >
          openenv harbor serve --llm-url $VLLM --dataset org/tasks
        </div>
      </motion.div>

      <motion.div variants={rise} transition={spring}>
        <Flow
          width={168}
          gap={10}
          nodes={[
            { label: "37 harnesses" },
            { label: "capture proxy", accent: true },
            { label: "token ids + logprobs" },
          ]}
        />
      </motion.div>

    </motion.div>
  );
}
