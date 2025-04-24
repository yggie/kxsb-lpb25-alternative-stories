"use client";

import { useSuspenseQuery } from "@apollo/client";
import { gql } from "@generated/gql";
import Link from "next/link";

export default function Home() {
  const sessionsQuery = useSuspenseQuery(
    gql(`
  query AvailableGamesQuery {
    availableGames {
      id
      title
      themes
      synopsis
      promoImageUrl
      openingVideoUrl
      prologue
      characters {
        id
        name
        background
        profilePhotoUrl
      }

      storyBlocks {
        actionsConsumed
        isFinalAct
      }
    }
  }
    `),
  );

  return (
    <main className="h-screen w-screen flex flex-col items-center p-8">
      <h1 className="my-8 text-3xl">Alternative Stories</h1>

      <section>
        <h2>
          <Link href="/" className="link text-2xl">
            How it works
          </Link>
        </h2>

        <ol className="list list-decimal text-lg mt-4">
          <li>Click any of the following experience</li>
          <li>Start the experience</li>
          <li>
            During dialogue actions, you can either pick one of the pre-defined
            options or take a photo
          </li>
          <li>Repeat until you run out of turns and reach an ending</li>
        </ol>
      </section>

      <ul className="flex flex-col gap-8 items-center w-full max-w-3xl overflow-y-auto h-full">
        {sessionsQuery.data.availableGames.map((game) => (
          <li key={game.id} className="relative">
            <img src={game.promoImageUrl} alt="" />

            <div className="w-full max-w-md p-4 bg-slate-800/30 absolute bottom-0 left-1/2 -translate-x-1/2 rounded-t-lg">
              <h2 className="text-3xl">
                <Link href={`/session/${game.id}`} className="link">
                  {game.title}
                </Link>
              </h2>

              <div className="flex flex-row gap-2 flex-wrap mt-4">
                {game.themes.map((theme) => (
                  <span key={theme} className="badge badge-neutral">
                    {theme}
                  </span>
                ))}
              </div>

              <p className="line-clamp-3 mt-4">{game.synopsis}</p>
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
