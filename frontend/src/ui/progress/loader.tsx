import clsx from "clsx";
import styles from "./loader.module.css";
import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";

export const Loader = ({ className }: { className?: string }) => {
  return <span className={clsx(styles.loader, className)} />;
};

const TIPS = [
  "Some authors use AI as a sounding board, not to replace writing, but to explore alternative ideas",
  "Procedural storytelling with AI is opening up choose-your-own-adventure stories that never repeat",
  "Dialogue in games can now be dynamically generated using AI, making NPCs more lifelike and unscripted",
  "AI is being used to generate infinite landscapes in games — think never-ending dungeons, forests, or cities",
  "Writers are using AI to overcome writer’s block, brainstorming plot twists, character names, or even entire dialogue scenes",
  "Some AI art generators let you “paint with words” — describe a scene, and the AI turns it into a picture",
  "Some AIs are trained to write pickup lines, horoscopes, and inspirational quotes",
  "People are using AI to reimagine historical events, like “What if Napoleon had Instagram?”",
];

export const FullPageLoader = ({
  className,
  showRandomText,
}: { className?: string; showRandomText?: boolean }) => {
  const [tip, setTip] = useState(TIPS[0]);

  useEffect(() => {
    const interval = setInterval(() => {
      setTip((tip) => {
        let sample = tip;
        while (sample === tip) {
          const idx = Math.floor(TIPS.length * Math.random());
          sample = TIPS[Math.min(idx, TIPS.length - 1)];
        }

        return sample;
      });
    }, 8000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  return (
    <div
      className={clsx(
        "fixed inset-0 flex items-center justify-center z-40",
        className,
      )}
    >
      <div className="flex flex-col gap-4 max-w-sm w-full items-center">
        <Loader className="text-3xl" />

        {showRandomText ? (
          <div className="h-20 relative w-full">
            <AnimatePresence>
              <motion.p
                key={tip}
                className="text-sm text-center absolute top-0 inset-x-0"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                {tip}
              </motion.p>
            </AnimatePresence>
          </div>
        ) : null}
      </div>
    </div>
  );
};
