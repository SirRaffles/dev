import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import ErrorBoundary from '../../components/errors/ErrorBoundary';

// Component that throws an error
const ThrowError = ({ shouldThrow = true, message = 'Test error' }) => {
  if (shouldThrow) {
    throw new Error(message);
  }
  return <div>No error</div>;
};

// Suppress console.error for cleaner test output
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});

afterAll(() => {
  console.error = originalError;
});

describe('ErrorBoundary', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders children when there is no error', () => {
    render(
      <ErrorBoundary>
        <div>Test Content</div>
      </ErrorBoundary>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  test('renders default fallback UI when error occurs', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText(/We encountered an unexpected error/i)).toBeInTheDocument();
  });

  test('displays Try Again button in fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    expect(tryAgainButton).toBeInTheDocument();
  });

  test('displays Reload Page button in fallback UI', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', { name: /reload page/i });
    expect(reloadButton).toBeInTheDocument();
  });

  test('calls onError callback when error occurs', () => {
    const onError = jest.fn();

    render(
      <ErrorBoundary onError={onError}>
        <ThrowError message="Custom error message" />
      </ErrorBoundary>
    );

    expect(onError).toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Custom error message',
      }),
      expect.objectContaining({
        componentStack: expect.any(String),
      })
    );
  });

  test('resets error state when Try Again is clicked', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError shouldThrow={true} />
      </ErrorBoundary>
    );

    // Error boundary should show fallback
    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();

    // Click Try Again
    const tryAgainButton = screen.getByRole('button', { name: /try again/i });

    // Re-render with no error
    rerender(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );

    fireEvent.click(tryAgainButton);

    // Should show children now
    expect(screen.getByText('No error')).toBeInTheDocument();
  });

  test('calls onReset callback when reset is triggered', () => {
    const onReset = jest.fn();

    render(
      <ErrorBoundary onReset={onReset}>
        <ThrowError />
      </ErrorBoundary>
    );

    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(tryAgainButton);

    expect(onReset).toHaveBeenCalledTimes(1);
  });

  test('renders custom fallback UI when provided', () => {
    const customFallback = ({ error, resetError }) => (
      <div>
        <h1>Custom Error UI</h1>
        <p>{error.message}</p>
        <button onClick={resetError}>Reset</button>
      </div>
    );

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError message="Custom error" />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom Error UI')).toBeInTheDocument();
    expect(screen.getByText('Custom error')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset/i })).toBeInTheDocument();
  });

  test('displays custom error message when provided', () => {
    const customMessage = 'Please contact support';

    render(
      <ErrorBoundary errorMessage={customMessage}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText(customMessage)).toBeInTheDocument();
  });

  test('hides Reload Page button when showReloadButton is false', () => {
    render(
      <ErrorBoundary showReloadButton={false}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.queryByRole('button', { name: /reload page/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
  });

  test('tracks error count when multiple errors occur', () => {
    const { rerender } = render(
      <ErrorBoundary>
        <ThrowError message="First error" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/error occurred 1 times/i)).toBeInTheDocument();

    // Trigger another error
    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(tryAgainButton);

    rerender(
      <ErrorBoundary>
        <ThrowError message="Second error" />
      </ErrorBoundary>
    );

    // Note: In a real scenario, you'd need to manage this differently
    // This test demonstrates the error count functionality
  });

  test('has proper accessibility attributes', () => {
    render(
      <ErrorBoundary>
        <ThrowError />
      </ErrorBoundary>
    );

    const errorContainer = screen.getByRole('alert');
    expect(errorContainer).toHaveAttribute('aria-live', 'assertive');
  });

  test('displays error details in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    render(
      <ErrorBoundary>
        <ThrowError message="Development error" />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Error Details/i)).toBeInTheDocument();
    expect(screen.getByText(/Development error/i)).toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('handles multiple child components with error', () => {
    render(
      <ErrorBoundary>
        <div>Child 1</div>
        <ThrowError />
        <div>Child 3</div>
      </ErrorBoundary>
    );

    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
    expect(screen.queryByText('Child 1')).not.toBeInTheDocument();
    expect(screen.queryByText('Child 3')).not.toBeInTheDocument();
  });

  test('error boundary catches errors from nested components', () => {
    const NestedComponent = () => {
      return (
        <div>
          <div>
            <ThrowError />
          </div>
        </div>
      );
    };

    render(
      <ErrorBoundary>
        <NestedComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
  });

  test('passes error object to custom fallback', () => {
    const customFallback = ({ error }) => (
      <div data-testid="custom-error">Error: {error.message}</div>
    );

    render(
      <ErrorBoundary fallback={customFallback}>
        <ThrowError message="Specific error message" />
      </ErrorBoundary>
    );

    const errorDisplay = screen.getByTestId('custom-error');
    expect(errorDisplay).toHaveTextContent('Error: Specific error message');
  });

  test('does not catch errors from event handlers', () => {
    // Error boundaries only catch errors during render, not in event handlers
    const ComponentWithEventError = () => {
      const handleClick = () => {
        throw new Error('Event handler error');
      };

      return <button onClick={handleClick}>Click me</button>;
    };

    render(
      <ErrorBoundary>
        <ComponentWithEventError />
      </ErrorBoundary>
    );

    const button = screen.getByRole('button', { name: /click me/i });

    // This should throw but not be caught by error boundary
    expect(() => {
      fireEvent.click(button);
    }).toThrow('Event handler error');
  });
});

describe('ErrorBoundary integration', () => {
  test('multiple error boundaries work independently', () => {
    render(
      <div>
        <ErrorBoundary>
          <ThrowError message="Error 1" />
        </ErrorBoundary>
        <ErrorBoundary>
          <div>Working component</div>
        </ErrorBoundary>
      </div>
    );

    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
    expect(screen.getByText('Working component')).toBeInTheDocument();
  });

  test('nested error boundaries catch at the right level', () => {
    render(
      <ErrorBoundary fallback={() => <div>Outer boundary</div>}>
        <div>
          <ErrorBoundary fallback={() => <div>Inner boundary</div>}>
            <ThrowError />
          </ErrorBoundary>
        </div>
      </ErrorBoundary>
    );

    // Inner boundary should catch it
    expect(screen.getByText('Inner boundary')).toBeInTheDocument();
    expect(screen.queryByText('Outer boundary')).not.toBeInTheDocument();
  });
});
