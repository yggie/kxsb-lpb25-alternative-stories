"use client";

import { useMutation } from "@apollo/client";
import { gql } from "@generated/gql";
import { useParams } from "next/navigation";
import type { ReactNode } from "react";

export default function SessionLayout({ children }: { children: ReactNode }) {
  const { key } = useParams<{ key: string }>();

  const [reset] = useMutation(
    gql(`
  mutation Reset($id: String!) {
    reset(id: $id)
  }
    `),
  );

  return (
    <>
      {children}

      <button
        type="button"
        className="fixed top-4 left-4 btn btn-warning z-50"
        onClick={() => {
          reset({ variables: { id: key } }).then(() =>
            window.location.reload(),
          );
        }}
      >
        Reset Progress
      </button>
    </>
  );
}
