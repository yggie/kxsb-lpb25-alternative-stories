import { useEffect, useId, useRef } from "react";
import { type GameSession, useGameSession } from "../page";
import { motion } from "motion/react";

export function ShowVideoOverlay({
  event,
}: {
  event: Extract<GameSession["events"][0], { __typename?: "ShowVideoEvent" }>;
}) {
  const { onProgressTimelineIntent } = useGameSession();
  const vid = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onEnd = () => {
      onProgressTimelineIntent(event);
    };

    vid.current?.addEventListener("ended", onEnd);

    return () => {
      vid.current?.removeEventListener("ended", onEnd);
    };
  }, [event, onProgressTimelineIntent]);

  return (
    <motion.div
      key={useId()}
      className="fixed inset-0 bg-base-100 z-10"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0, transition: { duration: 1 } }}
      transition={{ duration: 2 }}
    >
      {/* biome-ignore lint/a11y/useMediaCaption: <explanation> */}
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: <explanation> */}
      <video
        autoPlay
        ref={vid}
        onClick={() => {
          vid.current?.pause();
          onProgressTimelineIntent(event);
        }}
        className="w-full h-full"
      >
        <source src={event.videoUrl} type="video/mp4" />
      </video>
    </motion.div>
  );
}
