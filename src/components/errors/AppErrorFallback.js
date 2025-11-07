import React from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

/**
 * AppErrorFallback Component
 *
 * Specialized fallback UI for the Exit Readiness Assessment application.
 * Provides context-aware error messages and recovery options.
 *
 * Props:
 * - error: Error object with details about what went wrong
 * - resetError: Function to reset the error boundary and try again
 * - errorContext: Optional context about where the error occurred
 */
function AppErrorFallback({ error, resetError, errorContext = 'the assessment' }) {
  const getErrorMessage = () => {
    if (!error) {
      return 'An unknown error occurred.';
    }

    const errorMessage = error.message || error.toString();

    // Provide user-friendly messages for common errors
    if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
      return 'It looks like there\'s a problem with your internet connection. Please check your connection and try again.';
    }

    if (errorMessage.includes('timeout')) {
      return 'The request took too long to complete. Please try again.';
    }

    if (errorMessage.includes('JSON')) {
      return 'We received an unexpected response from the server. Please try again.';
    }

    // Default message
    return `We encountered an error while loading ${errorContext}. This might be a temporary issue.`;
  };

  const handleGoHome = () => {
    window.location.href = '/';
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 p-4">
      <div className="max-w-lg w-full bg-white rounded-lg shadow-lg p-8">
        {/* Error Icon */}
        <div className="flex items-center justify-center w-16 h-16 mx-auto bg-red-100 rounded-full mb-6">
          <AlertTriangle className="w-8 h-8 text-red-600" />
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-gray-900 text-center mb-3">
          Exit Readiness Assessment Error
        </h1>

        {/* Error Message */}
        <p className="text-gray-600 text-center mb-6">
          {getErrorMessage()}
        </p>

        {/* Development Error Details */}
        {process.env.NODE_ENV === 'development' && error && (
          <details className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <summary className="cursor-pointer text-sm font-medium text-gray-700 mb-2">
              Technical Details (Development Mode)
            </summary>
            <div className="text-xs text-gray-600 font-mono overflow-auto max-h-48">
              <p className="font-bold text-red-600 mb-2">
                {error.name}: {error.message}
              </p>
              {error.stack && (
                <pre className="whitespace-pre-wrap break-words text-gray-500">
                  {error.stack}
                </pre>
              )}
            </div>
          </details>
        )}

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={resetError}
            className="w-full flex items-center justify-center gap-2 bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition-colors font-medium"
            aria-label="Try loading the assessment again"
          >
            <RefreshCw className="w-5 h-5" />
            Try Again
          </button>

          <button
            onClick={handleGoHome}
            className="w-full flex items-center justify-center gap-2 bg-gray-200 text-gray-800 px-6 py-3 rounded-lg hover:bg-gray-300 transition-colors font-medium"
            aria-label="Return to home page"
          >
            <Home className="w-5 h-5" />
            Return to Start
          </button>
        </div>

        {/* Help Text */}
        <div className="mt-6 pt-6 border-t border-gray-200">
          <p className="text-sm text-gray-500 text-center">
            If this problem persists, please try:
          </p>
          <ul className="mt-3 text-sm text-gray-600 space-y-2">
            <li className="flex items-start">
              <span className="text-blue-600 mr-2">•</span>
              Refreshing your browser
            </li>
            <li className="flex items-start">
              <span className="text-blue-600 mr-2">•</span>
              Clearing your browser cache
            </li>
            <li className="flex items-start">
              <span className="text-blue-600 mr-2">•</span>
              Checking your internet connection
            </li>
            <li className="flex items-start">
              <span className="text-blue-600 mr-2">•</span>
              Trying a different browser
            </li>
          </ul>
        </div>
      </div>
    </div>
  );
}

export default AppErrorFallback;
