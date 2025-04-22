"use client";

import { FullPageLoader } from "@/ui/progress/loader";
import { useQuery } from "@apollo/client";
import { gql } from "@generated/gql";
import { notFound } from "next/navigation";
import Markdown from "react-markdown";

export default function DebugPage() {
  if (!process.env.NEXT_PUBLIC_DEBUG) notFound();

  const debugQuery = useQuery(
    gql(`
    query DebugQuery {
        debugListGenerations(page: 1, perPage: 500) {
            count
            limit
            offset
            hasMore
            generations {
                id
                state
                generationType
                model
                assets {
                    type
                    url
                }
                request {
                    ...on LumaGenAudioRequest {
                        generationType
                        prompt
                        negativePrompt
                    }

                    ...on LumaGenImageRequest {
                        generationType
                        model
                        prompt
                        aspectRatio
                    }

                    ...on LumaGenUpscaleVidRequest {
                        generationType
                        resolution
                    }

                    ...on LumaGenRequest {
                        generationType
                        prompt
                        aspectRatio
                        loop
                        model
                        resolution
                        duration
                    }
                }
            }
        }
    }
        `),
  );

  if (debugQuery.loading) return <FullPageLoader />;

  if (debugQuery.error) return <div>Something went wrong</div>;

  const generationsResponse = debugQuery.data?.debugListGenerations;

  return (
    <div className="p-4">
      <ul className="flex flex-row flex-wrap gap-4 justify-center">
        {generationsResponse?.generations.map((gen) => (
          <li key={gen.id} className="p-2">
            <h3 className="font-mono text-sm">{gen.id}</h3>

            <div className="flex flex-row gap-2">
              <span className="badge badge-neutral">{gen.model}</span>
              <span className="badge badge-success">{gen.state}</span>
            </div>

            <ul className="flex flex-row gap-2 mt-2">
              {gen.assets.map((asset) =>
                asset.type === "VIDEO" ? (
                  // biome-ignore lint/a11y/useMediaCaption: <explanation>
                  <video
                    key={asset.url}
                    src={asset.url}
                    className="h-48"
                    controls
                  />
                ) : asset.type === "IMAGE" ? (
                  // biome-ignore lint/a11y/useAltText: <explanation>
                  <img key={asset.url} src={asset.url} className="h-48" />
                ) : (
                  <span key={asset.url}>NOT SUPPORTED</span>
                ),
              )}
            </ul>

            <div className="w-72 overflow-y-auto h-48">
              {gen.request.__typename === "LumaGenAudioRequest" ? (
                <p className="text-xs">
                  <Markdown>{gen.request.prompt}</Markdown>
                </p>
              ) : gen.request.__typename === "LumaGenImageRequest" ? (
                <p className="text-xs">
                  <Markdown>{gen.request.prompt}</Markdown>
                </p>
              ) : gen.request.__typename === "LumaGenRequest" ? (
                <p className="text-xs">
                  <Markdown>{gen.request.prompt}</Markdown>
                </p>
              ) : gen.request.__typename === "LumaGenUpscaleVidRequest" ? (
                <p className="text-xs font-mono">
                  {gen.request.generationType}
                </p>
              ) : null}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
