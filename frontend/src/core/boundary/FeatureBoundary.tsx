"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";
import { liveLog } from "@/lib/liveLog";

type Props = {
  /** Section, card or feature id, for the log and the fallback. */
  id: string;
  children: ReactNode;
  fallback?: ReactNode;
};

type State = { error: Error | null };

/** Contains a failing section or card (P10): the rest of the desk keeps running. */
export class FeatureBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    liveLog("boundary", { id: this.props.id, error: error.message, stack: info.componentStack?.slice(0, 600) });
  }

  render() {
    if (!this.state.error) return this.props.children;
    if (this.props.fallback !== undefined) return this.props.fallback;
    return (
      <div className="flex h-full w-full items-center justify-center" role="status">
        <p className="rounded-full border border-[color:var(--border)] bg-black/40 px-4 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[color:var(--muted)]">
          {this.props.id} is unavailable
          <button
            type="button"
            className="ml-3 text-[color:var(--accent)] hover:underline"
            onClick={() => this.setState({ error: null })}
          >
            Retry
          </button>
        </p>
      </div>
    );
  }
}
