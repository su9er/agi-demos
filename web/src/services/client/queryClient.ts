/**
 * Shared React Query client.
 *
 * Conventions (see web/src/ARCHITECTURE.md):
 *  - New server-state hooks MUST use React Query instead of Zustand stores.
 *  - Zustand remains for pure client state (UI toggles, form drafts).
 *  - WS event handlers should call `queryClient.invalidateQueries` rather
 *    than pushing data into stores directly.
 */
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Conservative defaults; tune per-query when needed. We intentionally
      // pick a 30s staleTime (vs multica's Infinity) because the MemStack
      // surface is smaller and we lean on refetch-on-focus for freshness.
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      refetchOnWindowFocus: true,
      refetchOnReconnect: true,
      retry: 1,
    },
    mutations: {
      retry: 0,
    },
  },
});
