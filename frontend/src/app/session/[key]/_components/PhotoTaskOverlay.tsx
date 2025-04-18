import { use, useCallback, useEffect, useRef, useState } from "react";
import { useGameSession, type GameSession } from "../page";
import { FilesetResolver, ImageClassifier } from "@mediapipe/tasks-vision";
import clsx from "clsx";
import { GiRadarSweep } from "react-icons/gi";
import { useToast } from "@/ui/overlays/toast";

const classifierPromise: Promise<ImageClassifier> =
  typeof window === "undefined"
    ? new Promise((r) => {})
    : FilesetResolver.forVisionTasks(
        "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.0/wasm",
      ).then((vision) =>
        ImageClassifier.createFromOptions(vision, {
          baseOptions: {
            modelAssetPath:
              "https://storage.googleapis.com/mediapipe-models/image_classifier/efficientnet_lite0/float32/1/efficientnet_lite0.tflite",
          },
        }),
      );

export function PhotoTaskOverlay({
  event,
}: {
  event: Extract<
    GameSession["events"][0],
    { __typename?: "PlayerPhotoTaskEvent" }
  >;
}) {
  const classifier = use(classifierPromise);
  const { showToast } = useToast();

  const { onProgressTimelineIntent } = useGameSession();
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);

  const [aspectRatio, setAspectRatio] = useState(1);
  const width = 320;
  const height = width / aspectRatio;

  const [previewImage, setPreviewImage] = useState("");

  const mediaStreamRef = useRef<MediaStream>(null);
  useEffect(() => {
    navigator.mediaDevices
      .getUserMedia({ video: true, audio: false })
      .then((stream) => {
        for (const mediaTrack of mediaStreamRef.current?.getTracks() || []) {
          mediaTrack.stop();
        }

        mediaStreamRef.current = stream;
        if (videoRef.current) {
          videoRef.current.srcObject = stream;
          videoRef.current.play();

          videoRef.current.addEventListener("canplay", () => {
            if (videoRef.current) {
              setAspectRatio(
                videoRef.current.videoWidth / videoRef.current.videoHeight,
              );
            }
          });
        }
      });

    return () => {
      if (videoRef.current) {
        videoRef.current.pause();
        videoRef.current.src = "";
      }

      for (const mediaTrack of mediaStreamRef.current?.getTracks() || []) {
        mediaTrack.stop();
      }
    };
  }, []);

  const captureImage = useCallback(() => {
    if (canvasRef.current && videoRef.current) {
      const context = canvasRef.current.getContext("2d");

      context?.drawImage(
        videoRef.current,
        0,
        0,
        canvasRef.current.width,
        canvasRef.current.height,
      );

      const data = canvasRef.current.toDataURL();

      setPreviewImage(data);

      setTimeout(() => {
        if (imageRef.current) {
          const results = classifier.classify(imageRef.current);

          const probability = results.classifications.find(
            (c) => c.headName === "probability",
          );

          showToast({
            message: `Top categories: ${probability?.categories
              .slice(0, 5)
              .map((cat) => cat.categoryName)
              .join(", ")}`,
          });

          console.log("CLASSIFY RESULTS", results);
        }
      }, 500);
    }
  }, [classifier.classify, showToast]);

  return (
    <div className="fixed inset-0 z-10 bg-base-100 flex justify-center items-center">
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        className="hidden"
      />

      <div className="h-full w-full">
        {/* biome-ignore lint/a11y/useMediaCaption: <explanation> */}
        <video
          ref={videoRef}
          width={width}
          height={height}
          className={clsx("object-contain w-full h-full", {
            hidden: previewImage,
          })}
        >
          Camera not available
        </video>

        <img
          ref={imageRef}
          src={previewImage || undefined}
          alt=""
          className={clsx("w-full h-full object-contain", {
            hidden: !previewImage,
          })}
        />
      </div>

      {previewImage ? (
        <>
          <div className="flex flex-row gap-4 fixed bottom-0 p-4 inset-x-0 justify-center">
            <button
              type="button"
              className="btn btn-ghost"
              onClick={(ev) => {
                ev.stopPropagation();
                setPreviewImage("");
              }}
            >
              Try again
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={(ev) => {
                ev.stopPropagation();

                if (canvasRef.current) {
                  canvasRef.current.toBlob(
                    (blob) => {
                      if (blob) {
                        onProgressTimelineIntent(event, {
                          type: "submit-photo",
                          file: new File([blob], "submission.jpg"),
                        });
                      }
                    },
                    "image/jpeg",
                    0.95,
                  );
                } else {
                  setPreviewImage("");
                }
              }}
            >
              Submit
            </button>
          </div>
        </>
      ) : (
        <>
          <button
            type="button"
            onClick={(ev) => {
              ev.stopPropagation();
              captureImage();
            }}
            className="btn btn-circle btn-primary btn-xl absolute bottom-4 left-1/2 -translate-x-1/2"
          >
            <GiRadarSweep size="1.6em" />
          </button>
        </>
      )}
    </div>
  );
}
