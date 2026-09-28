import { Component, type ErrorInfo, type ReactNode } from "react";
import { Button } from "@/components/ui/button";

type Props = { children: ReactNode };
type State = { error: Error | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Application rendering error", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return <main className="mx-auto mt-20 max-w-xl rounded-2xl border border-rose-200 bg-white p-8 text-center shadow-sm">
      <h1 className="text-xl font-bold text-slate-900">Something went wrong</h1>
      <p className="mt-2 text-sm text-slate-600">The page could not be displayed. Reload it to try again.</p>
      <Button className="mt-5" onClick={() => window.location.reload()}>Reload page</Button>
    </main>;
  }
}
