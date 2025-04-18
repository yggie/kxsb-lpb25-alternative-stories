"use client";

import { FullPageLoader, Loader } from "@/ui/progress/loader";
import { useMutation, useQuery } from "@apollo/client";
import { gql } from "@generated/gql";
import type { GetGameSessionQuery } from "@generated/graphql";
import { useParams } from "next/navigation";
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { GiChatBubble } from "react-icons/gi";
import { PhotoTaskOverlay } from "./_components/PhotoTaskOverlay";
import { useToast } from "@/ui/overlays/toast";
import { ShowStoryPrologueOverlay } from "./_components/ShowPrologueOverlay";
import { ShowVideoOverlay } from "./_components/ShowVideoOverlay";
import { AnimatePresence, motion } from "motion/react";
import clsx from "clsx";

const CHAT_COLOURS = [
  "text-rose-500",
  "text-emerald-500",
  "text-indigo-400",
  "text-fuchsia-500",
  "text-cyan-500",
];

type GameEvent =
  | {
      type: "updated";
    }
  | {
      type: "error";
      message: string;
    };

type PlayerEvent =
  | {
      type: "start";
    }
  | {
      type: "submit-photo";
      photo_url: string;
    };

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

  send(event: PlayerEvent) {
    this.socket.send(JSON.stringify(event));
  }
}

interface GameSessionContextValue {
  session: GameSession;
  eventIndex: number;
  visibleEvents: GameSession["events"];
  currentIntent?: PlayerIntent;
  onProgressTimelineIntent: (
    fromEvent?: GameSession["events"][0],
    intent?: PlayerIntent,
  ) => void;
}

const GameSessionContext = createContext<GameSessionContextValue>(0 as never);

export function useGameSession() {
  return useContext(GameSessionContext);
}

export default function SessionPage() {
  const { key } = useParams<{ key: string }>();

  const [timelineIndex, setTimelineIndex] = useState(-1);
  const [currentIntent, setCurrentIntent] = useState<
    PlayerIntent | undefined
  >();

  const sessionQuery = useQuery(
    gql(`
  query GetGameSession($sessionKey: String!) {
    currentSession(sessionKey: $sessionKey) {
      title
      sessionKey
      characters {
        id
        name
        profilePhotoUrl
      }

      events {
        ...on CharacterDialogueEvent {
          characterId
          messages
        }

        ...on PlayerPhotoTaskEvent {
          requirements
        }

        ...on NewStoryActEvent {
          storyActId
        }

        ...on PlayerNewDialogueOptionsEvent {
          options
        }

        ...on ShowStoryPrologueEvent {
          lines
        }

        ...on ShowVideoEvent {
          videoUrl
        }

        ...on SubmitPhotoEvent {
          photoUrl
        }
      }
    }
  }
    `),
    {
      variables: {
        sessionKey: key,
      },
    },
  );

  const [reset, mutationResult] = useMutation(
    gql(`
  mutation Reset($sessionKey: String!) {
    reset(sessionKey: $sessionKey)
  }
    `),
  );

  const { showToast } = useToast();

  const controller = useMemo(() => {
    return new GameController({
      url: `ws://localhost:8000/ws?key=${encodeURIComponent(key)}`,
      onEvent: (event) => {
        switch (event.type) {
          case "updated":
            sessionQuery.refetch();
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
  }, [key, sessionQuery.refetch, showToast]);

  useEffect(() => {
    if (sessionQuery.data) {
      const events = sessionQuery.data.currentSession?.events || [];

      if (events[timelineIndex]) {
        switch (events[timelineIndex].__typename) {
          case "SubmitPhotoEvent":
          case "NewStoryActEvent":
          case "WritingNewStoryActEvent":
            setTimelineIndex((i) => Math.min(i + 1, events.length));
            break;

          default:
            // do nothing
            break;
        }
      }
    }
  }, [timelineIndex, sessionQuery.data]);

  if (sessionQuery.loading || !sessionQuery.called) return <FullPageLoader />;

  if (sessionQuery.error || !sessionQuery.data?.currentSession) {
    return (
      <div className="fixed inset-0 flex items-center justify-center">
        <div className="p-8">
          <p className="text-xl">Something went wrong</p>
        </div>
      </div>
    );
  }

  const currentSession = sessionQuery.data.currentSession;

  const visibleEvents = currentSession.events.slice(0, timelineIndex + 1);

  const resetButton = (
    <button
      type="button"
      className="fixed top-4 left-4 btn btn-warning z-50"
      onClick={() => {
        reset({ variables: { sessionKey: key } }).then(() =>
          window.location.reload(),
        );
      }}
    >
      Reset
    </button>
  );

  if (!visibleEvents.length) {
    return (
      <div className="h-screen w-screen flex justify-center items-center">
        <div className="p-4">
          <h1 className="text-3xl text-center mb-8">{currentSession.title}</h1>

          <button
            type="button"
            className="btn btn-primary mx-auto block"
            onClick={() => {
              controller.send({ type: "start" });
              setTimelineIndex((i) => i + 1);
            }}
          >
            Start
          </button>
        </div>

        {resetButton}
      </div>
    );
  }

  if (
    visibleEvents.length === 1 &&
    visibleEvents[0].__typename === "WritingNewStoryActEvent"
  ) {
    return <FullPageLoader showRandomText />;
  }

  return (
    <GameSessionContext
      value={{
        session: currentSession,
        eventIndex: timelineIndex,
        currentIntent,
        visibleEvents,
        onProgressTimelineIntent: (currentEvent, intent) => {
          setCurrentIntent(intent);

          const shouldNotProgress =
            (currentEvent?.__typename === "PlayerPhotoTaskEvent" &&
              intent?.type !== "submit-photo") ||
            (currentEvent?.__typename === "PlayerNewDialogueOptionsEvent" &&
              intent?.type !== "pick-option");

          if (!shouldNotProgress) {
            setTimelineIndex((i) => Math.min(i + 1, visibleEvents.length));
          }

          switch (intent?.type) {
            case "submit-photo": {
              if (currentEvent?.__typename === "PlayerPhotoTaskEvent") {
                controller.send({
                  type: "submit-photo",
                  photo_url: "",
                });
              }
              break;
            }

            default:
              break;
          }
        },
      }}
    >
      <SessionChat className="w-full max-w-lg mx-auto h-screen" />

      {resetButton}
    </GameSessionContext>
  );
}

export type GameSession = Exclude<
  GetGameSessionQuery["currentSession"],
  undefined | null
>;

type PlayerIntent =
  | PlayerPickOptionEvent
  | PlayerStartTaskEvent
  | PlayerSubmitPhotoEvent;

interface PlayerPickOptionEvent {
  type: "pick-option";
  index: number;
}

interface PlayerStartTaskEvent {
  type: "start-photo-task";
}

interface PlayerSubmitPhotoEvent {
  type: "submit-photo";
  file: File;
}

interface SessionChatProps {
  className?: string;
}

function SessionChat({ className }: SessionChatProps) {
  const {
    session,
    eventIndex,
    visibleEvents,
    currentIntent,
    onProgressTimelineIntent,
  } = useGameSession();
  const { events, characters } = session;

  const [focusedEvent, setFocusedEvent] = useState<(typeof events)[0] | null>(
    null,
  );

  const currentEvent = focusedEvent || events[eventIndex];

  const overlay = renderEventOverlay(currentEvent, currentIntent);

  return (
    <section className={className}>
      {/* biome-ignore lint/a11y/useKeyWithClickEvents: <explanation> */}
      <div
        onClick={() => {
          onProgressTimelineIntent(currentEvent);
        }}
        className="w-full h-full flex flex-col-reverse overflow-y-auto"
      >
        {!currentEvent ? (
          <div className="flex justify-center items-center p-4 skeleton">
            <Loader />
          </div>
        ) : null}

        {visibleEvents.toReversed().flatMap((ev, vi) => {
          const visibleIndex = visibleEvents.length - vi - 1;

          switch (ev.__typename) {
            case "CharacterDialogueEvent": {
              const char = characters.find((c) => ev.characterId === c.id);
              const profileImageUrl =
                char?.profilePhotoUrl || "https://placehold.co/600x400";

              const k = `charmsg.${visibleIndex}`;

              return ev.messages.map((msg, index) => (
                <div
                  key={`${k}.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    index
                  }`}
                  className="chat chat-start"
                >
                  <div className="chat-image avatar">
                    <div className="w-10 rounded-full">
                      <img src={profileImageUrl} alt="" />
                    </div>
                  </div>
                  <div
                    className={clsx(
                      "chat-header font-semibold",
                      CHAT_COLOURS[(char?.id || 0) % CHAT_COLOURS.length],
                    )}
                  >
                    {char ? (
                      char.name
                    ) : (
                      <span className="italic">anonymous</span>
                    )}
                  </div>

                  <motion.div
                    key={`${k}.${
                      // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                      index
                    }.bubble`}
                    className="chat-bubble"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ duration: 0.5 }}
                  >
                    {msg}
                  </motion.div>
                </div>
              ));
            }

            case "PlayerNewDialogueOptionsEvent": {
              const profileImageUrl = "https://placehold.co/600x400";

              return (
                <div
                  key={`player-options.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    visibleIndex
                  }`}
                  className="flex flex-col items-end gap-2 p-4"
                >
                  {ev.options.map((option, index) => (
                    <button
                      key={option}
                      type="button"
                      className="btn btn-primary rounded-xl"
                      onClick={(e) => {
                        e.stopPropagation();
                        onProgressTimelineIntent(ev, {
                          type: "pick-option",
                          index,
                        });
                      }}
                    >
                      {option}

                      <GiChatBubble />
                    </button>
                  ))}
                </div>
              );
            }

            case "PlayerPhotoTaskEvent": {
              return (
                <div
                  key={`photo-task.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    visibleIndex
                  }`}
                  className="p-2 flex flex-row justify-end"
                >
                  <button
                    type="button"
                    className="btn btn-secondary"
                    onClick={(ev) => {
                      ev.stopPropagation();
                      onProgressTimelineIntent(currentEvent, {
                        type: "start-photo-task",
                      });
                    }}
                  >
                    Start task
                  </button>
                </div>
              );
            }

            case "WritingNewStoryActEvent":
            case "ShowStoryPrologueEvent":
              return null;

            case "ShowVideoEvent":
              return (
                <div
                  key={`show-video.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    visibleIndex
                  }`}
                  className="flex flex-row items-center gap-2"
                >
                  <div className="flex-1 h-[1px] bg-base-300" />
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost btn-primary"
                  >
                    Replay Video
                  </button>
                </div>
              );

            case "NewStoryActEvent":
              return (
                <div
                  key={`new-act.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    visibleIndex
                  }`}
                  className="flex flex-row items-center gap-2 my-4"
                >
                  <div className="flex-1 h-1 bg-base-300" />
                  <span className="badge badge-lg">New act</span>
                  <div className="flex-1 h-1 bg-base-300" />
                </div>
              );

            case "SubmitPhotoEvent":
              return (
                <div
                  key={`submit-photo.${
                    // biome-ignore lint/suspicious/noArrayIndexKey: <explanation>
                    visibleIndex
                  }`}
                  className="flex flex-row items-center gap-2"
                >
                  <div className="flex-1 h-[1px] bg-base-300" />
                  <button
                    type="button"
                    className="btn btn-sm btn-ghost btn-primary"
                  >
                    View Submission
                  </button>
                </div>
              );

            default:
              return (
                <pre
                  key={String(visibleIndex)}
                  className="font-mono p-2 bg-red-500"
                >
                  {JSON.stringify(ev, null, 2)}
                </pre>
              );
          }
        })}
      </div>

      <AnimatePresence>
        {overlay ? (
          <motion.div
            key="background"
            className="bg-black fixed inset-0 z-0"
            initial={{ opacity: 1 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ delay: 1 }}
          />
        ) : null}

        {overlay}
      </AnimatePresence>
    </section>
  );
}

function renderEventOverlay(
  event: GameSession["events"][0],
  currentIntent?: PlayerIntent,
) {
  if (!event) return null;

  if (currentIntent) {
    switch (currentIntent.type) {
      case "start-photo-task":
        if (event.__typename === "PlayerPhotoTaskEvent") {
          return <PhotoTaskOverlay key="photo-task" event={event} />;
          // biome-ignore lint/style/noUselessElse: <explanation>
        } else {
          break;
        }

      default:
        break;
    }
  }

  switch (event.__typename) {
    case "ShowStoryPrologueEvent":
      return <ShowStoryPrologueOverlay key="show-prologue" event={event} />;

    case "ShowVideoEvent":
      return <ShowVideoOverlay key="show-video" event={event} />;

    default:
      return null;
  }
}
