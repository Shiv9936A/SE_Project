import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "@/services/api";

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) =>
        failureCount < 2 && (!(error instanceof ApiError) || !error.status || error.status >= 500),
    },
    mutations: { retry: 0 },
  },
});
