"use client";

import { FullPageLoader } from "@/ui/progress/loader";
import { useSuspenseQuery } from "@apollo/client";
import { gql } from "@generated/gql";
import type { GetGameQuery } from "@generated/graphql";
import { notFound, useParams } from "next/navigation";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { MagicCameraOverlay } from "./_components/MagicCameraOverlay";
import { useToast } from "@/ui/overlays/toast";
import { AnimatePresence, motion } from "motion/react";
import clsx from "clsx";
import {
  AiOutlineForward,
  AiOutlineHistory,
  AiOutlineMenu,
} from "react-icons/ai";
import { MagicButton } from "@/ui/buttons/button";
import Link from "next/link";

type GameEvent =
  | {
      type: "updated";
    }
  | {
      type: "error";
      message: string;
    };

type PlayerServerEvent =
  | { type: "start-game" }
  | { type: "take-action"; action: string }
  | { type: "submit-photo"; url: string };

type PlayerEvent =
  | PlayerStartGameIntent
  | PlayerPrologueComplete
  | PlayerTakeActionIntent
  | PlayerSubmitPhotoIntent
  | PlayerNextDialogueIntent;

interface PlayerStartGameIntent {
  type: "start-game-intent";
}

interface PlayerPrologueComplete {
  type: "prologue-complete";
}

interface PlayerTakeActionIntent {
  type: "take-action";
  action: string;
}

interface PlayerSubmitPhotoIntent {
  type: "submit-photo";
  url: string;
}

interface PlayerNextDialogueIntent {
  type: "next-dialogue";
}

class GameController {
  socket: WebSocket;

  constructor({
    url,
    onEvent,
  }: { url: string; onEvent?: (event: GameEvent) => void }) {
    this.socket = new WebSocket(url);

    this.socket.addEventListener("open", () => {
      console.log("connection opened");
    });

    this.socket.addEventListener("close", () => {
      console.log("connection closed");
    });

    this.socket.addEventListener("message", (event) => {
      console.log("on message", event.data);
      onEvent?.(JSON.parse(event.data));
    });
  }

  send(event: PlayerServerEvent) {
    this.socket.send(JSON.stringify(event));
  }
}

export default function SessionPage() {
  const { key } = useParams<{ key: string }>();

  const [storyBlockIndex, setStoryBlockIndex] = useState(-1);

  const currentGameQuery = useSuspenseQuery(
    gql(`
  query GetGame($id: String!) {
    game(id: $id) {
      id
      title
      themes
      synopsis
      prologue
      totalActions
      promoImageUrl
      openingVideoUrl
      characters {
        id
        name
        background
        profilePhotoUrl
      }

      storyBlocks {
        id
        number
        isFinalAct
        dialogue
        actionsConsumed
        backdropImageUrl
        possibleActions
        previousAction
      }
    }
  }
    `),
    {
      variables: {
        id: key,
      },
    },
  );

  const { showToast } = useToast();

  const controller = useMemo(() => {
    return new GameController({
      url: `ws://localhost:8000/ws?key=${encodeURIComponent(key)}`,
      onEvent: (event) => {
        switch (event.type) {
          case "updated":
            currentGameQuery.refetch();
            break;

          case "error":
            showToast({
              variant: "error",
              message: event.message,
            });
            break;

          default:
            console.warn("unexpected event:", event);
            break;
        }
      },
    });
  }, [key, currentGameQuery.refetch, showToast]);

  const currentGame = currentGameQuery.data.game;

  const onPlayerEvent = useCallback(
    (ev: PlayerEvent) => {
      switch (ev.type) {
        case "start-game-intent":
          controller.send({ type: "start-game" });
          break;

        case "prologue-complete":
          setStoryBlockIndex((i) => i + 1);
          break;

        case "take-action":
          if (storyBlockIndex + 1 >= (currentGame?.storyBlocks.length || 0)) {
            controller.send({ type: "take-action", action: ev.action });
          }
          setStoryBlockIndex((i) => i + 1);
          break;

        case "submit-photo":
          if (storyBlockIndex + 1 >= (currentGame?.storyBlocks.length || 0)) {
            controller.send({ type: "submit-photo", url: ev.url });
          }
          setStoryBlockIndex((i) => i + 1);
          break;

        case "next-dialogue":
          setStoryBlockIndex((i) => i + 1);
          break;

        default:
          console.warn("unhandled player event:", ev);
          break;
      }
    },
    [controller, currentGame?.storyBlocks.length, storyBlockIndex],
  );

  if (!currentGame) return notFound();

  console.log("current game", currentGame);

  switch (storyBlockIndex) {
    case -1:
      return (
        <StartGameScreen game={currentGame} onPlayerEvent={onPlayerEvent} />
      );

    default: {
      const storyBlock = currentGame.storyBlocks.find(
        (b) => b.number === storyBlockIndex + 1,
      );

      return (
        <StoryBlockScreen
          key={storyBlock?.number}
          game={currentGame}
          storyBlock={storyBlock}
          onPlayerEvent={onPlayerEvent}
        />
      );
    }
  }
}

type Game = Exclude<GetGameQuery["game"], undefined | null>;

interface StartGameScreenProps {
  game: Game;
  onPlayerEvent: (ev: PlayerEvent) => void;
}

function StartGameScreen({ game, onPlayerEvent }: StartGameScreenProps) {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (step > 1) {
      onPlayerEvent({ type: "prologue-complete" });
    }
  }, [step, onPlayerEvent]);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: <explanation>
    <div
      className="flex justify-center items-center h-screen w-screen relative"
      onClick={() => {
        if (step !== 0) {
          setStep((step) => step + 1);
        }
      }}
    >
      <AnimatePresence>
        {step === 0 ? (
          <motion.div
            key="start"
            className="absolute inset-0"
            exit={{ opacity: 0 }}
            transition={{ duration: 1 }}
          >
            <div className="w-full mx-auto max-w-3xl h-full flex justify-center items-center relative">
              {/* biome-ignore lint/a11y/useMediaCaption: <explanation> */}
              <video
                src={game.openingVideoUrl}
                loop
                autoPlay
                className="-z-10 absolute top-1/2 left-1/2 -translate-1/2 object-cover"
              />

              <div className="p-4 bg-base-100/30 rounded-lg">
                <h1 className="text-5xl text-center">{game.title}</h1>

                <div className="flex flex-row justify-center mt-8">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      onPlayerEvent({ type: "start-game-intent" });
                      setStep((step) => step + 1);
                    }}
                  >
                    Start Experience
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        ) : step === 1 ? (
          <motion.div
            key="prologue"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 1 }}
            className="absolute inset-0"
          >
            <div className="mx-auto w-full max-w-lg flex flex-col justify-center h-full">
              {game.prologue.map((item) => (
                <p key={item} className="text-xl leading-loose">
                  {item}
                </p>
              ))}
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}

interface StoryBlockScreenProps {
  game: Game;
  storyBlock?: Game["storyBlocks"][0];
  onPlayerEvent: (ev: PlayerEvent) => void;
}

function StoryBlockScreen({
  game,
  storyBlock,
  onPlayerEvent,
}: StoryBlockScreenProps) {
  const [step, setStep] = useState(0);

  const [showHistory, setShowHistory] = useState(false);
  const [showMagicCam, setShowMagicCam] = useState(false);

  if (!storyBlock) return <FullPageLoader showRandomText />;

  const dialogue = storyBlock.dialogue[step];
  // biome-ignore lint/style/noNonNullAssertion: <explanation>
  const lastDialogue = dialogue || storyBlock.dialogue.at(-1)!;

  const backdropImageUrl = storyBlock.backdropImageUrl || "";
  const nextBlock = game.storyBlocks
    .filter((b) => b.number > storyBlock.number)
    .toSorted((a, b) => a.number - b.number)
    .at(0);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: <explanation>
    <div
      className="mx-auto w-full max-w-3xl h-screen flex flex-col justify-end gap-2 relative p-2"
      onClick={() => {
        setStep((step) => step + 1);
      }}
    >
      <div className="absolute top-0 left-0 p-2">
        <button type="button" className="btn btn-soft btn-circle">
          <AiOutlineMenu size="1.4em" />
        </button>
      </div>

      <AnimatePresence>
        <motion.div
          key={backdropImageUrl}
          style={{ backgroundImage: `url(${backdropImageUrl})` }}
          className="bg-center bg-no-repeat bg-cover absolute inset-0 -z-10"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.8 }}
        />
      </AnimatePresence>

      <div className="absolute top-0 right-0 p-2">
        <span
          className={clsx(
            "font-mono text-xs bg-base-100/50 flex flex-row items-center gap-1",
            {
              "text-green-500": game.storyBlocks.length > storyBlock.number,
            },
          )}
        >
          {game.storyBlocks.length > storyBlock.number ? (
            <>
              <AiOutlineForward size="1.2em" />
              <span className="uppercase">recap</span>
            </>
          ) : null}
          <span>
            &nbsp;[
            {game.storyBlocks.reduce((acc, b) => acc + b.actionsConsumed, 0)}/
            {game.totalActions}]
          </span>
        </span>
      </div>

      <AnimatePresence>
        {showHistory ? (
          <motion.div
            className="fixed inset-0 bg-base-100/50 z-30"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.5 }}
            onClick={(ev) => {
              ev.stopPropagation();
              setShowHistory(false);
            }}
          >
            <div className="h-screen mx-auto w-full max-w-3xl p-4 flex">
              <DialogueHistory
                game={game}
                latestDialogueIndex={step}
                className="border border-base-content rounded-lg flex-1 overflow-y-auto bg-base-100"
              />
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>

      <div className="flex flex-row justify-end">
        <button
          type="button"
          className="btn btn-sm btn-circle"
          onClick={(ev) => {
            ev.stopPropagation();
            setShowHistory((show) => !show);
          }}
        >
          <AiOutlineHistory size="1.6em" />
        </button>
      </div>

      {dialogue ? (
        <div className="p-4 m-2 rounded-lg border border-base-content bg-base-100/90">
          {dialogue}
        </div>
      ) : storyBlock.isFinalAct ? (
        <div className="fixed left-1/2 top-1/2 -translate-1/2 flex justify-center items-center p-8 bg-base-100/20 rounded-xl flex-col gap-6">
          <div className="text-5xl text-center text-shadow-lg">The End</div>

          <div className="flex flex-row gap-4">
            <Link href="/" className="btn btn-ghost btn-primary">
              Back to more stories
            </Link>

            <Link href="" className="btn btn-primary">
              View recap
            </Link>
          </div>
        </div>
      ) : nextBlock ? (
        <>
          <div className="p-4 m-2 rounded-lg border border-base-content bg-base-100/90">
            {lastDialogue}
          </div>

          <button
            type="button"
            className="btn btn-success rounded-lg"
            onClick={(ev) => {
              ev.stopPropagation();
              onPlayerEvent({ type: "next-dialogue" });
            }}
          >
            {nextBlock.previousAction || (
              <span className="font-mono">(magic photo)</span>
            )}
            &nbsp;
            <AiOutlineForward size="1.4em" />
          </button>
        </>
      ) : (
        <>
          <div className="p-4 m-2 rounded-lg border border-base-content bg-base-100/90">
            {lastDialogue}
          </div>

          <ul className="m-2 flex flex-col gap-2 p-4 border border-base-content rounded-lg bg-base-100/90">
            {storyBlock.possibleActions.map((action) => (
              <li key={action} className="w-full">
                <button
                  type="button"
                  className="btn btn-success btn-outline w-full p-2 h-fit text-left justify-start"
                  onClick={() => {
                    onPlayerEvent({
                      type: "take-action",
                      action: action,
                    });
                  }}
                >
                  {action}&nbsp;
                  <span className="text-warn font-mono text-sm">[1]</span>
                </button>
              </li>
            ))}

            <li className="flex flex-row justify-end">
              <MagicButton
                type="button"
                className="btn"
                onClick={() => {
                  setShowMagicCam(true);
                }}
              >
                Magic Camera{" "}
                <span className="text-warn font-mono text-sm">[2]</span>
              </MagicButton>
            </li>
          </ul>
        </>
      )}

      {showMagicCam ? (
        <MagicCameraOverlay
          open
          onClose={() => setShowMagicCam(false)}
          onImageReady={(url) => {
            onPlayerEvent({
              type: "submit-photo",
              url,
            });
          }}
        />
      ) : null}
    </div>
  );
}

type DialogueHistoryItem =
  | {
      type: "dialogue";
      text: string;
    }
  | {
      type: "action";
      action: string;
      actionsConsumed: number;
    };

interface DialogueHistoryProps {
  game: Game;
  className?: string;
  latestDialogueIndex?: number;
}

function DialogueHistory({
  game,
  className,
  latestDialogueIndex,
}: DialogueHistoryProps) {
  const historyItems = useMemo<DialogueHistoryItem[]>(() => {
    const blocks = game.storyBlocks.toSorted((a, b) => a.number - b.number);

    return blocks
      .flatMap((block) => {
        const items = block.dialogue.map((dialogue) => ({
          type: "dialogue" as const,
          text: dialogue,
        }));

        return block.previousAction
          ? [
              {
                type: "action" as const,
                action: block.previousAction,
                actionsConsumed: block.actionsConsumed,
              },
              ...items,
            ]
          : items;
      })
      .toReversed();
  }, [game]);

  return (
    // biome-ignore lint/a11y/useKeyWithClickEvents: <explanation>
    <ul
      className={clsx("p-4 flex flex-col-reverse gap-4", className)}
      onClick={(ev) => {
        ev.stopPropagation();
      }}
    >
      {historyItems.map((item, i) =>
        item.type === "dialogue" ? (
          <li key={i} className="">
            {item.text}
          </li>
        ) : (
          <li key={i} className="font-bold">
            {item.action}&nbsp;
            <span className="font-mono text-warning text-sm">
              [{item.actionsConsumed}]
            </span>
          </li>
        ),
      )}
    </ul>
  );
}
