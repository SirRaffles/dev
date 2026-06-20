import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
  componentStack: string | null;
}

class ErrorBoundary extends React.Component<ErrorBoundaryProps, ErrorBoundaryState> {
  private resetButtonRef = React.createRef<HTMLButtonElement>();

  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null, componentStack: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error, componentStack: null };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    // React prod builds strip error messages — the component stack is the
    // single most useful thing we can show the user when something blows up.
    console.error('ErrorBoundary caught:', error, errorInfo);
    this.setState({ componentStack: errorInfo.componentStack || null });
  }

  componentDidUpdate(_prevProps: ErrorBoundaryProps, prevState: ErrorBoundaryState) {
    if (!prevState.hasError && this.state.hasError) {
      this.resetButtonRef.current?.focus();
    }
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, componentStack: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          role="alert"
          className="min-h-screen bg-gradient-to-br from-slate-100 via-slate-50 to-slate-100 dark:from-slate-900 dark:via-slate-800 dark:to-slate-900 text-slate-900 dark:text-white flex items-center justify-center p-8"
        >
          <div className="bg-white/80 dark:bg-slate-800/50 backdrop-blur rounded-2xl p-8 border border-slate-200 dark:border-slate-700 shadow-sm dark:shadow-none max-w-lg w-full text-center">
            <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" aria-hidden="true" />
            <h2 className="text-xl font-semibold mb-2">Something went wrong</h2>
            <p className="text-slate-500 dark:text-slate-400 mb-4 text-sm">
              {this.state.error?.message || 'An unexpected error occurred.'}
            </p>
            {this.state.componentStack && (
              <details className="text-left mb-6 text-xs bg-slate-100 dark:bg-slate-700 rounded-lg p-3 max-h-60 overflow-auto">
                <summary className="cursor-pointer font-medium">Component stack</summary>
                <pre className="whitespace-pre-wrap mt-2 text-slate-600 dark:text-slate-400">{this.state.componentStack.trim()}</pre>
              </details>
            )}
            <button
              ref={this.resetButtonRef}
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 px-6 py-3 rounded-xl font-medium bg-blue-500 hover:bg-blue-600 text-white transition-colors"
            >
              <RefreshCw className="w-4 h-4" aria-hidden="true" />
              Try Again
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
