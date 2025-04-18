"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";

export default function Home() {
  const router = useRouter();
  const { handleSubmit, register } = useForm({
    defaultValues: {
      gameKey: "",
    },
  });

  return (
    <main className="h-screen w-screen flex items-center justify-center">
      <form
        className="p-8"
        onSubmit={(e) => {
          handleSubmit((data) => {
            if (data.gameKey) {
              router.push(`/session/${data.gameKey}`);
            }
          })(e).catch((err) => console.error(err));
        }}
      >
        <h1 className="text-3xl text-center mb-8">Project ARk: Stories</h1>

        <input
          type="text"
          placeholder="Enter your game key"
          className="input w-full"
          {...register("gameKey")}
        />
      </form>
    </main>
  );
}
