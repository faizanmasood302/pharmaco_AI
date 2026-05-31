"use client";

import React, { Component, ErrorInfo, ReactNode } from "react";
import Icon from "./Icon";

interface Props {
  children?: ReactNode;
  fallbackMessage?: string;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    errorMessage: ""
  };

  public static getDerivedStateFromError(error: Error): State {
    // Update state so the next render will show the fallback UI.
    return { hasError: true, errorMessage: error.message };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 bg-error-container/20 border border-error/30 rounded-xl">
          <Icon name="warning" className="h-10 w-10 text-error mb-4" />
          <h2 className="text-lg font-bold text-on-surface mb-2">Something went wrong</h2>
          <p className="text-sm text-on-surface-variant text-center max-w-md">
            {this.props.fallbackMessage || "Failed to render this component. Please refresh the page or try another action."}
          </p>
          <button
            className="mt-6 px-4 py-2 bg-error text-on-error rounded-lg font-bold text-sm"
            onClick={() => this.setState({ hasError: false })}
          >
            Try Again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
