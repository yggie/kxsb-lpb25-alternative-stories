"use client";

import { ToastProvider } from "@/ui/overlays/toast";
import { FullPageLoader } from "@/ui/progress/loader";
import { ApolloClient, ApolloProvider, InMemoryCache } from "@apollo/client";
import React from "react";
import { Suspense, type ReactNode } from "react";

const client = new ApolloClient({
  uri: `${process.env.NEXT_PUBLIC_API_URL}/graphql`,
  cache: new InMemoryCache(),
});

export function ClientProviders({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <ApolloProvider client={client}>
        <ErrorBoundary>
          <Suspense fallback={<FullPageLoader />}>{children}</Suspense>
        </ErrorBoundary>
      </ApolloProvider>
    </ToastProvider>
  );
}

class ErrorBoundary extends React.Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  // biome-ignore lint/suspicious/noExplicitAny: <explanation>
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    // Update state so the next render will show the fallback UI.
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: unknown) {
    console.error(error);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex justify-center items-center w-full h-full">
          <div className="p-4">
            <h1 className="text-xl">Oops, something went wrong</h1>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
