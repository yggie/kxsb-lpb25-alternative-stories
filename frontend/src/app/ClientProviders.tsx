"use client";

import { ToastProvider } from "@/ui/overlays/toast";
import { ApolloClient, ApolloProvider, InMemoryCache } from "@apollo/client";
import type { ReactNode } from "react";

const client = new ApolloClient({
  uri: "http://localhost:8000/graphql",
  cache: new InMemoryCache(),
});

export function ClientProviders({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <ApolloProvider client={client}>{children}</ApolloProvider>
    </ToastProvider>
  );
}
