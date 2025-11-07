import React, { useState } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import ErrorBoundary from '../../components/errors/ErrorBoundary';
import AppErrorFallback from '../../components/errors/AppErrorFallback';

// Suppress console.error for cleaner test output
const originalError = console.error;
beforeAll(() => {
  console.error = jest.fn();
});

afterAll(() => {
  console.error = originalError;
});

// Component that can toggle between error and normal state
const ToggleErrorComponent = ({ shouldError = false }) => {
  if (shouldError) {
    throw new Error('Toggle error');
  }
  return <div>Component working correctly</div>;
};

// Component with controlled error state
const ControlledErrorComponent = () => {
  const [hasError, setHasError] = useState(false);

  if (hasError) {
    throw new Error('Controlled error');
  }

  return (
    <div>
      <p>Component is stable</p>
      <button onClick={() => setHasError(true)}>Trigger Error</button>
    </div>
  );
};

describe('Error Recovery Integration Tests', () => {
  test('recovers from error when Try Again is clicked', () => {
    let shouldThrow = true;

    const TestComponent = () => {
      if (shouldThrow) {
        throw new Error('Test error');
      }
      return <div>Recovered successfully</div>;
    };

    const { rerender } = render(
      <ErrorBoundary>
        <TestComponent />
      </ErrorBoundary>
    );

    // Should show error fallback
    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();

    // Fix the error condition
    shouldThrow = false;

    // Click Try Again
    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    fireEvent.click(tryAgainButton);

    // Force a rerender with the fixed component
    rerender(
      <ErrorBoundary>
        <TestComponent />
      </ErrorBoundary>
    );

    // Should show recovered content
    expect(screen.getByText('Recovered successfully')).toBeInTheDocument();
  });

  test('AppErrorFallback provides clear error messages', () => {
    const TestError = new Error('Network timeout');

    render(
      <AppErrorFallback
        error={TestError}
        resetError={jest.fn()}
        errorContext="the data fetch"
      />
    );

    expect(screen.getByText(/Exit Readiness Assessment Error/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /return to start/i })).toBeInTheDocument();
  });

  test('AppErrorFallback handles network errors with helpful message', () => {
    const networkError = new Error('Network request failed');

    render(
      <AppErrorFallback error={networkError} resetError={jest.fn()} />
    );

    expect(
      screen.getByText(/problem with your internet connection/i)
    ).toBeInTheDocument();
  });

  test('AppErrorFallback handles timeout errors', () => {
    const timeoutError = new Error('Request timeout exceeded');

    render(
      <AppErrorFallback error={timeoutError} resetError={jest.fn()} />
    );

    expect(screen.getByText(/took too long to complete/i)).toBeInTheDocument();
  });

  test('AppErrorFallback handles JSON errors', () => {
    const jsonError = new Error('Invalid JSON response');

    render(
      <AppErrorFallback error={jsonError} resetError={jest.fn()} />
    );

    expect(screen.getByText(/unexpected response from the server/i)).toBeInTheDocument();
  });

  test('AppErrorFallback calls resetError when Try Again is clicked', () => {
    const resetError = jest.fn();

    render(
      <AppErrorFallback
        error={new Error('Test error')}
        resetError={resetError}
      />
    );

    const tryAgainButton = screen.getByRole('button', { name: /try loading the assessment again/i });
    fireEvent.click(tryAgainButton);

    expect(resetError).toHaveBeenCalledTimes(1);
  });

  test('nested error boundaries isolate errors correctly', () => {
    const InnerComponent = () => {
      throw new Error('Inner error');
    };

    const OuterComponent = () => (
      <div>
        <p>Outer component content</p>
        <ErrorBoundary
          fallback={() => <div>Inner boundary caught error</div>}
        >
          <InnerComponent />
        </ErrorBoundary>
        <p>More outer content</p>
      </div>
    );

    render(
      <ErrorBoundary
        fallback={() => <div>Outer boundary caught error</div>}
      >
        <OuterComponent />
      </ErrorBoundary>
    );

    // Inner boundary should catch the error
    expect(screen.getByText('Inner boundary caught error')).toBeInTheDocument();
    expect(screen.getByText('Outer component content')).toBeInTheDocument();
    expect(screen.getByText('More outer content')).toBeInTheDocument();
    expect(screen.queryByText('Outer boundary caught error')).not.toBeInTheDocument();
  });

  test('multiple error boundaries work independently', () => {
    const ErrorComponent1 = () => {
      throw new Error('Error 1');
    };

    const SafeComponent = () => <div>Safe component</div>;

    render(
      <div>
        <ErrorBoundary
          fallback={() => <div>Boundary 1 error</div>}
        >
          <ErrorComponent1 />
        </ErrorBoundary>
        <ErrorBoundary
          fallback={() => <div>Boundary 2 error</div>}
        >
          <SafeComponent />
        </ErrorBoundary>
      </div>
    );

    expect(screen.getByText('Boundary 1 error')).toBeInTheDocument();
    expect(screen.getByText('Safe component')).toBeInTheDocument();
  });

  test('error boundary with onError callback logs errors', () => {
    const errorLog = jest.fn();

    const ErrorComponent = () => {
      throw new Error('Logged error');
    };

    render(
      <ErrorBoundary onError={errorLog}>
        <ErrorComponent />
      </ErrorBoundary>
    );

    expect(errorLog).toHaveBeenCalled();
    expect(errorLog).toHaveBeenCalledWith(
      expect.objectContaining({
        message: 'Logged error',
      }),
      expect.any(Object)
    );
  });

  test('error boundary shows development details in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    const ErrorComponent = () => {
      throw new Error('Development error with stack trace');
    };

    render(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText(/Error Details/i)).toBeInTheDocument();
    expect(screen.getByText(/Development error with stack trace/i)).toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('error count increments correctly', () => {
    let throwCount = 0;

    const ErrorComponent = () => {
      if (throwCount > 0) {
        throw new Error(`Error ${throwCount}`);
      }
      return <div>No error</div>;
    };

    const { rerender } = render(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    // Should show no error initially
    expect(screen.getByText('No error')).toBeInTheDocument();

    // Trigger first error
    throwCount = 1;
    rerender(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    expect(screen.getByText(/error occurred 1 times/i)).toBeInTheDocument();
  });

  test('Reload Page button triggers page reload', () => {
    // Mock window.location.reload
    const mockReload = jest.fn();
    Object.defineProperty(window, 'location', {
      value: { reload: mockReload },
      writable: true,
    });

    const ErrorComponent = () => {
      throw new Error('Reload test error');
    };

    render(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', { name: /reload page/i });
    fireEvent.click(reloadButton);

    expect(mockReload).toHaveBeenCalledTimes(1);
  });

  test('AppErrorFallback Return to Start button navigates home', () => {
    // Mock window.location.href
    delete window.location;
    window.location = { href: '' };

    render(
      <AppErrorFallback
        error={new Error('Test error')}
        resetError={jest.fn()}
      />
    );

    const returnButton = screen.getByRole('button', { name: /return to home page/i });
    fireEvent.click(returnButton);

    expect(window.location.href).toBe('/');
  });
});

describe('Error Boundary Stress Tests', () => {
  test('handles rapid error and recovery cycles', async () => {
    let shouldError = false;

    const ToggleComponent = () => {
      if (shouldError) {
        throw new Error('Rapid error');
      }
      return <div>Stable state</div>;
    };

    const { rerender } = render(
      <ErrorBoundary>
        <ToggleComponent />
      </ErrorBoundary>
    );

    // Perform rapid error/recovery cycles
    for (let i = 0; i < 5; i++) {
      shouldError = true;
      rerender(
        <ErrorBoundary>
          <ToggleComponent />
        </ErrorBoundary>
      );

      await waitFor(() => {
        expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
      });

      shouldError = false;
      const tryAgainButton = screen.getByRole('button', { name: /try again/i });
      fireEvent.click(tryAgainButton);

      rerender(
        <ErrorBoundary>
          <ToggleComponent />
        </ErrorBoundary>
      );

      await waitFor(() => {
        expect(screen.getByText('Stable state')).toBeInTheDocument();
      });
    }

    // Should still be functional after stress test
    expect(screen.getByText('Stable state')).toBeInTheDocument();
  });

  test('error boundary does not crash with null or undefined error', () => {
    const NullErrorComponent = () => {
      throw null;
    };

    render(
      <ErrorBoundary>
        <NullErrorComponent />
      </ErrorBoundary>
    );

    // Should still show fallback UI
    expect(screen.getByText(/Oops! Something went wrong/i)).toBeInTheDocument();
  });
});

describe('Error Boundary Accessibility Tests', () => {
  test('error fallback has proper ARIA attributes', () => {
    const ErrorComponent = () => {
      throw new Error('Accessibility test error');
    };

    render(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    const alertElement = screen.getByRole('alert');
    expect(alertElement).toHaveAttribute('aria-live', 'assertive');
  });

  test('error fallback buttons have proper labels', () => {
    const ErrorComponent = () => {
      throw new Error('Button label test');
    };

    render(
      <ErrorBoundary>
        <ErrorComponent />
      </ErrorBoundary>
    );

    const tryAgainButton = screen.getByRole('button', { name: /try again/i });
    const reloadButton = screen.getByRole('button', { name: /reload page/i });

    expect(tryAgainButton).toHaveAttribute('aria-label', 'Try again');
    expect(reloadButton).toHaveAttribute('aria-label', 'Reload page');
  });

  test('AppErrorFallback buttons have proper accessibility labels', () => {
    render(
      <AppErrorFallback
        error={new Error('Accessibility test')}
        resetError={jest.fn()}
      />
    );

    const tryAgainButton = screen.getByRole('button', {
      name: /try loading the assessment again/i,
    });
    const returnButton = screen.getByRole('button', {
      name: /return to home page/i,
    });

    expect(tryAgainButton).toBeInTheDocument();
    expect(returnButton).toBeInTheDocument();
  });
});
