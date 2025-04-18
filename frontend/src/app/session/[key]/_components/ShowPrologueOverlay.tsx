import { useEffect, useId } from "react";
import { useGameSession, type GameSession } from "../page";
import { motion } from "motion/react";

export function ShowStoryPrologueOverlay({
  event,
}: {
  event: Extract<
    GameSession["events"][0],
    { __typename?: "ShowStoryPrologueEvent" }
  >;
}) {
  const { session, onProgressTimelineIntent } = useGameSession();

  useEffect(() => {
    const timeout = setTimeout(() => {
      onProgressTimelineIntent(event);
    }, 12000);

    return () => clearTimeout(timeout);
  }, [event, onProgressTimelineIntent]);

  return (
    <motion.div
      key={useId()}
      className="fixed inset-0 bg-base-100 flex justify-center items-center z-10"
      onClick={() => {
        onProgressTimelineIntent(event);
      }}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 2 }}
    >
      <div className="p-4">
        {event.lines.map((line, index) => (
          // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
          <p key={index} className="text-xl">
            {line}
          </p>
        ))}
      </div>
    </motion.div>
  );
}
