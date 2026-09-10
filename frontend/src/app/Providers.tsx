"use client";

import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function Providers({ children }: { children: React.ReactNode }) {
  // One QueryClient per browser session (not per render) -- useState's
  // lazy initializer runs once, same reasoning React Query's own docs give
  // for App Router: a module-level singleton would leak/share cache across
  // different users' requests during SSR.
  const [queryClient] = useState(() => new QueryClient());
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
