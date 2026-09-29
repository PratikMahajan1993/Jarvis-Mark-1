"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import { SubstrateCanvas } from "./SubstrateCanvas";

export const DESK_ROUTE = "/";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { staleTime: 5000, retry: 1, refetchOnWindowFocus: false },
    },
  });
}

/**
 * Root host, mounted once by app/layout.tsx and never remounted across
 * navigation: query client, the L1 substrate, and the modal / toast portals.
 * Off `/` the substrate is frozen and hidden; its WebGL context stays alive.
 */
export function JarvisRoot({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeQueryClient);
  const pathname = usePathname();
  const onDesk = pathname === DESK_ROUTE;
  return (
    <QueryClientProvider client={queryClient}>
      <SubstrateCanvas active={onDesk} />
      {children}
      <div id="jarvis-modal" className="relative z-modal" />
      <div id="jarvis-toast" className="relative z-toast" />
    </QueryClientProvider>
  );
}
