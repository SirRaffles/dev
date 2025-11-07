import React, { Component } from 'react';
import { AlertTriangle } from 'lucide-react';

/**
 * ErrorBoundary Component
 *
 * Catches JavaScript errors anywhere in the child component tree,
 * logs those errors, and displays a fallback UI instead of crashing
 * the entire application.
 *
 * Features:
 * - Catches errors during rendering, lifecycle methods, and constructors
 * - Provides custom fallback UI or uses default
 * - Supports error callbacks for logging/tracking
 * - Allows retry functionality
 * - Preserves error information for debugging
 */
class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = {
      hasError: false,
      error: null,
      errorInfo: null,
      errorCount: 0,
    };
  }

  static getDerivedStateFromError(error) {
    // Update state so the next render will show the fallback UI
    return {
      hasError: true,
      error: error,
    };
  }

  componentDidCatch(error, errorInfo) {
    // Log error details for debugging
    console.error('ErrorBoundary caught an error:', error, errorInfo);

    // Update state with error details
    this.setState(prevState => ({
      errorInfo: errorInfo,
      errorCount: prevState.errorCount + 1,
    }));

    // Call custom error handler if provided
    if (this.props.onError) {
      this.props.onError(error, errorInfo);
    }

    // Here you would typically send to error tracking service
    // Example: Sentry.captureException(error, { extra: errorInfo });
  }

  handleReset = () => {
    this.setState({
      hasError: false,
      error: null,
      errorInfo: null,
    });

    // Call custom reset handler if provided
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      // Use custom fallback if provided
      if (this.props.fallback) {
        return this.props.fallback({
          error: this.state.error,
          errorInfo: this.state.errorInfo,
          resetError: this.handleReset,
        });
      }

      // Default fallback UI
      return (
        <div
          className="min-h-screen flex items-center justify-center bg-gray-100 p-4"
          role="alert"
          aria-live="assertive"
        >
          <div className="max-w-md w-full bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-center w-12 h-12 mx-auto bg-red-100 rounded-full mb-4">
              <AlertTriangle className="w-6 h-6 text-red-600" />
            </div>

            <h2 className="text-xl font-bold text-gray-900 text-center mb-2">
              Oops! Something went wrong
            </h2>

            <p className="text-gray-600 text-center mb-4">
              {this.props.errorMessage ||
                'We encountered an unexpected error. Please try again.'}
            </p>

            {process.env.NODE_ENV === 'development' && this.state.error && (
              <details className="mb-4 p-3 bg-gray-50 rounded border border-gray-200">
                <summary className="cursor-pointer text-sm font-medium text-gray-700 mb-2">
                  Error Details (Development Only)
                </summary>
                <div className="text-xs text-gray-600 font-mono overflow-auto">
                  <p className="font-bold mb-1">Error: {this.state.error.toString()}</p>
                  {this.state.errorInfo && (
                    <pre className="whitespace-pre-wrap break-words">
                      {this.state.errorInfo.componentStack}
                    </pre>
                  )}
                </div>
              </details>
            )}

            <div className="flex flex-col space-y-2">
              <button
                onClick={this.handleReset}
                className="w-full bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 transition-colors"
                aria-label="Try again"
              >
                Try Again
              </button>

              {this.props.showReloadButton !== false && (
                <button
                  onClick={() => window.location.reload()}
                  className="w-full bg-gray-200 text-gray-800 px-4 py-2 rounded hover:bg-gray-300 transition-colors"
                  aria-label="Reload page"
                >
                  Reload Page
                </button>
              )}
            </div>

            {this.state.errorCount > 1 && (
              <p className="mt-4 text-xs text-center text-gray-500">
                Error occurred {this.state.errorCount} times
              </p>
            )}
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
