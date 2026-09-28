import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { ToastProvider } from "@/components/toast-provider";

export function renderAtRoute(ui: ReactElement, path: string, route: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  const result = render(<QueryClientProvider client={queryClient}><ToastProvider><MemoryRouter initialEntries={[path]}><Routes><Route path={route} element={ui} /></Routes></MemoryRouter></ToastProvider></QueryClientProvider>);
  return { ...result, queryClient };
}

export function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } } });
  const result = render(<QueryClientProvider client={queryClient}><ToastProvider><MemoryRouter>{ui}</MemoryRouter></ToastProvider></QueryClientProvider>);
  return { ...result, queryClient };
}
