import React, { Component, ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
    errorInfo: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('PerandamΨ Uncaught Error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="w-screen h-screen bg-[#03050c] text-slate-100 flex items-center justify-center p-6">
          <div className="max-w-lg w-full bg-cosmos-900/90 border border-rose-800 rounded-2xl p-6 shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-rose-400">
              <AlertTriangle className="w-6 h-6 flex-shrink-0" />
              <h1 className="text-lg font-bold">Observatory Runtime Exception</h1>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              An unexpected error interrupted the PerandamΨ visualization engine.
            </p>
            {this.state.error && (
              <pre className="p-3 bg-cosmos-950 rounded-lg text-rose-300 font-mono text-[11px] overflow-x-auto border border-rose-900/60 max-h-48 overflow-y-auto">
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack}
              </pre>
            )}
            <button
              onClick={() => window.location.reload()}
              className="flex items-center space-x-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              <span>Reload Observatory</span>
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
