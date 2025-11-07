import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import AppErrorFallback from '../../components/errors/AppErrorFallback';

describe('AppErrorFallback Component', () => {
  const mockResetError = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('renders with basic error', () => {
    const error = new Error('Test error message');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    expect(screen.getByText(/Exit Readiness Assessment Error/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /try loading the assessment again/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /return to home page/i })).toBeInTheDocument();
  });

  test('displays custom error context', () => {
    const error = new Error('Test error');

    render(
      <AppErrorFallback
        error={error}
        resetError={mockResetError}
        errorContext="the survey data"
      />
    );

    expect(screen.getByText(/while loading the survey data/i)).toBeInTheDocument();
  });

  test('provides user-friendly message for network errors', () => {
    const networkError = new Error('Failed to fetch data from network');

    render(<AppErrorFallback error={networkError} resetError={mockResetError} />);

    expect(
      screen.getByText(/problem with your internet connection/i)
    ).toBeInTheDocument();
  });

  test('provides user-friendly message for timeout errors', () => {
    const timeoutError = new Error('Request timeout after 30s');

    render(<AppErrorFallback error={timeoutError} resetError={mockResetError} />);

    expect(screen.getByText(/took too long to complete/i)).toBeInTheDocument();
  });

  test('provides user-friendly message for JSON parsing errors', () => {
    const jsonError = new Error('Unexpected token in JSON at position 0');

    render(<AppErrorFallback error={jsonError} resetError={mockResetError} />);

    expect(screen.getByText(/unexpected response from the server/i)).toBeInTheDocument();
  });

  test('provides generic message for unknown errors', () => {
    const unknownError = new Error('Something strange happened');

    render(<AppErrorFallback error={unknownError} resetError={mockResetError} />);

    expect(
      screen.getByText(/We encountered an error while loading the assessment/i)
    ).toBeInTheDocument();
  });

  test('handles null error gracefully', () => {
    render(<AppErrorFallback error={null} resetError={mockResetError} />);

    expect(screen.getByText(/An unknown error occurred/i)).toBeInTheDocument();
  });

  test('handles undefined error gracefully', () => {
    render(<AppErrorFallback error={undefined} resetError={mockResetError} />);

    expect(screen.getByText(/An unknown error occurred/i)).toBeInTheDocument();
  });

  test('Try Again button calls resetError callback', () => {
    const error = new Error('Test error');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    const tryAgainButton = screen.getByRole('button', {
      name: /try loading the assessment again/i,
    });
    fireEvent.click(tryAgainButton);

    expect(mockResetError).toHaveBeenCalledTimes(1);
  });

  test('Return to Start button navigates to home', () => {
    const error = new Error('Test error');

    // Mock window.location
    delete window.location;
    window.location = { href: '' };

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    const returnButton = screen.getByRole('button', { name: /return to home page/i });
    fireEvent.click(returnButton);

    expect(window.location.href).toBe('/');
  });

  test('displays technical details in development mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'development';

    const error = new Error('Development mode error');
    error.stack = 'Error: Development mode error\n    at Test.js:10:15';

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    expect(screen.getByText(/Technical Details/i)).toBeInTheDocument();
    expect(screen.getByText(/Development mode error/i)).toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('hides technical details in production mode', () => {
    const originalEnv = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';

    const error = new Error('Production mode error');
    error.stack = 'Error: Production mode error\n    at Test.js:10:15';

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    expect(screen.queryByText(/Technical Details/i)).not.toBeInTheDocument();

    process.env.NODE_ENV = originalEnv;
  });

  test('displays helpful troubleshooting steps', () => {
    const error = new Error('Test error');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    expect(screen.getByText(/If this problem persists/i)).toBeInTheDocument();
    expect(screen.getByText(/Refreshing your browser/i)).toBeInTheDocument();
    expect(screen.getByText(/Clearing your browser cache/i)).toBeInTheDocument();
    expect(screen.getByText(/Checking your internet connection/i)).toBeInTheDocument();
    expect(screen.getByText(/Trying a different browser/i)).toBeInTheDocument();
  });

  test('renders error icon', () => {
    const error = new Error('Test error');

    const { container } = render(
      <AppErrorFallback error={error} resetError={mockResetError} />
    );

    // Check for SVG icon (lucide-react AlertTriangle)
    const svg = container.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  test('buttons have proper styling classes', () => {
    const error = new Error('Test error');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    const tryAgainButton = screen.getByRole('button', {
      name: /try loading the assessment again/i,
    });
    const returnButton = screen.getByRole('button', { name: /return to home page/i });

    // Try Again button should have blue styling
    expect(tryAgainButton.className).toContain('bg-blue-600');

    // Return button should have gray styling
    expect(returnButton.className).toContain('bg-gray-200');
  });

  test('has proper accessibility structure', () => {
    const error = new Error('Test error');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    // Check for proper heading hierarchy
    const heading = screen.getByText(/Exit Readiness Assessment Error/i);
    expect(heading.tagName).toBe('H1');

    // Check buttons have aria-labels
    const tryAgainButton = screen.getByRole('button', {
      name: /try loading the assessment again/i,
    });
    const returnButton = screen.getByRole('button', { name: /return to home page/i });

    expect(tryAgainButton).toHaveAttribute('aria-label');
    expect(returnButton).toHaveAttribute('aria-label');
  });

  test('renders with long error messages', () => {
    const longError = new Error(
      'This is a very long error message that contains a lot of details about what went wrong, including specific file paths, network endpoints, and other technical information that might be useful for debugging but could be overwhelming for users.'
    );

    render(<AppErrorFallback error={longError} resetError={mockResetError} />);

    // Should still render without breaking layout
    expect(screen.getByText(/Exit Readiness Assessment Error/i)).toBeInTheDocument();
  });

  test('handles error without message property', () => {
    const error = { toString: () => 'String error' };

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    expect(
      screen.getByText(/We encountered an error while loading the assessment/i)
    ).toBeInTheDocument();
  });

  test('handles error with special characters in message', () => {
    const error = new Error('Error with <script>alert("xss")</script>');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    // React automatically escapes content, so script shouldn't execute
    expect(screen.getByText(/Exit Readiness Assessment Error/i)).toBeInTheDocument();
  });

  test('error context is properly interpolated', () => {
    const error = new Error('Test');

    render(
      <AppErrorFallback
        error={error}
        resetError={mockResetError}
        errorContext="the custom module"
      />
    );

    expect(screen.getByText(/while loading the custom module/i)).toBeInTheDocument();
  });

  test('displays all action buttons in correct order', () => {
    const error = new Error('Test error');

    render(<AppErrorFallback error={error} resetError={mockResetError} />);

    const buttons = screen.getAllByRole('button');

    // Should have exactly 2 buttons
    expect(buttons).toHaveLength(2);

    // First button should be Try Again
    expect(buttons[0]).toHaveTextContent(/Try Again/i);

    // Second button should be Return to Start
    expect(buttons[1]).toHaveTextContent(/Return to Start/i);
  });

  test('icon buttons have proper gap spacing', () => {
    const error = new Error('Test error');

    const { container } = render(
      <AppErrorFallback error={error} resetError={mockResetError} />
    );

    // Check for gap classes on buttons (flex gap-2)
    const buttons = container.querySelectorAll('button');
    buttons.forEach(button => {
      expect(button.className).toContain('gap-2');
    });
  });

  test('responsive layout classes are applied', () => {
    const error = new Error('Test error');

    const { container } = render(
      <AppErrorFallback error={error} resetError={mockResetError} />
    );

    // Check for responsive container classes
    const mainContainer = container.querySelector('.min-h-screen');
    expect(mainContainer).toBeInTheDocument();
    expect(mainContainer?.className).toContain('flex');
    expect(mainContainer?.className).toContain('items-center');
    expect(mainContainer?.className).toContain('justify-center');
  });
});

describe('AppErrorFallback error categorization', () => {
  const mockResetError = jest.fn();

  test('correctly identifies network errors with various patterns', () => {
    const networkErrors = [
      new Error('network error occurred'),
      new Error('Failed to fetch'),
      new Error('Network request failed'),
      new Error('NetworkError: Connection lost'),
    ];

    networkErrors.forEach(error => {
      const { unmount } = render(
        <AppErrorFallback error={error} resetError={mockResetError} />
      );

      expect(
        screen.getByText(/problem with your internet connection/i)
      ).toBeInTheDocument();

      unmount();
    });
  });

  test('correctly identifies timeout errors with various patterns', () => {
    const timeoutErrors = [
      new Error('timeout exceeded'),
      new Error('Request timeout'),
      new Error('Operation timed out'),
    ];

    timeoutErrors.forEach(error => {
      const { unmount } = render(
        <AppErrorFallback error={error} resetError={mockResetError} />
      );

      expect(screen.getByText(/took too long to complete/i)).toBeInTheDocument();

      unmount();
    });
  });

  test('correctly identifies JSON errors with various patterns', () => {
    const jsonErrors = [
      new Error('JSON parse error'),
      new Error('Invalid JSON format'),
      new Error('SyntaxError: Unexpected token in JSON'),
    ];

    jsonErrors.forEach(error => {
      const { unmount } = render(
        <AppErrorFallback error={error} resetError={mockResetError} />
      );

      expect(
        screen.getByText(/unexpected response from the server/i)
      ).toBeInTheDocument();

      unmount();
    });
  });
});
