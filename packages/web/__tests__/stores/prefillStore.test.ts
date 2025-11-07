/**
 * Tests for prefillStore
 *
 * Coverage:
 * - Issue #6: Offline queue size limits and FIFO eviction
 * - Issue #12: Validation race condition prevention
 * - Issue #14: localStorage versioning (integration)
 */

import { renderHook, act } from '@testing-library/react';
import { usePrefillStore, MAX_QUEUE_SIZE, OfflineAction } from '../../lib/stores/prefillStore';

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => {
      store[key] = value;
    },
    removeItem: (key: string) => {
      delete store[key];
    },
    clear: () => {
      store = {};
    }
  };
})();

Object.defineProperty(window, 'localStorage', {
  value: localStorageMock
});

// Mock console.warn to capture toast warnings
const originalWarn = console.warn;
let warnMessages: string[] = [];

beforeEach(() => {
  localStorageMock.clear();
  warnMessages = [];
  console.warn = jest.fn((message: string) => {
    warnMessages.push(message);
  });
});

afterEach(() => {
  console.warn = originalWarn;
});

describe('Issue #6: Offline Queue Size Limits', () => {
  describe('MAX_QUEUE_SIZE enforcement', () => {
    test('should respect MAX_QUEUE_SIZE constant', () => {
      expect(MAX_QUEUE_SIZE).toBe(100);
    });

    test('should allow adding items up to MAX_QUEUE_SIZE', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        // Add exactly MAX_QUEUE_SIZE items
        for (let i = 0; i < MAX_QUEUE_SIZE; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      expect(result.current.offlineQueue.length).toBe(MAX_QUEUE_SIZE);
    });

    test('should not exceed MAX_QUEUE_SIZE', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        // Add more than MAX_QUEUE_SIZE items
        for (let i = 0; i < MAX_QUEUE_SIZE + 10; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      // Should still be at MAX_QUEUE_SIZE
      expect(result.current.offlineQueue.length).toBe(MAX_QUEUE_SIZE);
    });
  });

  describe('FIFO eviction', () => {
    test('should remove oldest item when queue is full (FIFO)', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        // Fill queue to capacity
        for (let i = 0; i < MAX_QUEUE_SIZE; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      const firstAction = result.current.offlineQueue[0];

      act(() => {
        // Add one more item - should evict oldest
        result.current.addToOfflineQueue({
          id: 'action-new',
          type: 'create',
          questionId: 'q-new',
          data: { value: 'new' },
          timestamp: Date.now()
        });
      });

      // Queue should still be at max
      expect(result.current.offlineQueue.length).toBe(MAX_QUEUE_SIZE);

      // First item should be removed
      expect(result.current.offlineQueue.find(a => a.id === firstAction.id)).toBeUndefined();

      // New item should be at the end
      expect(result.current.offlineQueue[MAX_QUEUE_SIZE - 1].id).toBe('action-new');
    });

    test('should maintain FIFO order across multiple evictions', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        // Fill queue
        for (let i = 0; i < MAX_QUEUE_SIZE; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }

        // Add 5 more items
        for (let i = MAX_QUEUE_SIZE; i < MAX_QUEUE_SIZE + 5; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      // First 5 items should be evicted
      for (let i = 0; i < 5; i++) {
        expect(result.current.offlineQueue.find(a => a.id === `action-${i}`)).toBeUndefined();
      }

      // Items 5-104 should remain
      expect(result.current.offlineQueue[0].id).toBe('action-5');
      expect(result.current.offlineQueue[MAX_QUEUE_SIZE - 1].id).toBe('action-104');
    });
  });

  describe('Warning toast on eviction', () => {
    test('should show warning toast when item is evicted', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        // Fill queue
        for (let i = 0; i < MAX_QUEUE_SIZE; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      // Clear warnings from filling
      warnMessages = [];

      act(() => {
        // Add one more - should trigger warning
        result.current.addToOfflineQueue({
          id: 'action-overflow',
          type: 'create',
          questionId: 'q-overflow',
          data: { value: 'overflow' },
          timestamp: Date.now()
        });
      });

      // Should have warning about queue being full
      expect(warnMessages.length).toBeGreaterThan(0);
      expect(warnMessages.some(msg => msg.includes('Offline queue full'))).toBe(true);
    });

    test('should not show warning when queue is not full', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        result.current.addToOfflineQueue({
          id: 'action-1',
          type: 'create',
          questionId: 'q-1',
          data: { value: 1 },
          timestamp: Date.now()
        });
      });

      // No warnings when adding to non-full queue
      expect(warnMessages.filter(msg => msg.includes('Offline queue full'))).toHaveLength(0);
    });
  });

  describe('Queue management operations', () => {
    test('should remove specific item from queue', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        result.current.addToOfflineQueue({
          id: 'action-1',
          type: 'create',
          questionId: 'q-1',
          data: { value: 1 },
          timestamp: Date.now()
        });

        result.current.addToOfflineQueue({
          id: 'action-2',
          type: 'create',
          questionId: 'q-2',
          data: { value: 2 },
          timestamp: Date.now()
        });
      });

      expect(result.current.offlineQueue.length).toBe(2);

      act(() => {
        result.current.removeFromOfflineQueue('action-1');
      });

      expect(result.current.offlineQueue.length).toBe(1);
      expect(result.current.offlineQueue[0].id).toBe('action-2');
    });

    test('should clear entire queue', () => {
      const { result } = renderHook(() => usePrefillStore());

      act(() => {
        for (let i = 0; i < 10; i++) {
          result.current.addToOfflineQueue({
            id: `action-${i}`,
            type: 'create',
            questionId: `q-${i}`,
            data: { value: i },
            timestamp: Date.now()
          });
        }
      });

      expect(result.current.offlineQueue.length).toBe(10);

      act(() => {
        result.current.clearOfflineQueue();
      });

      expect(result.current.offlineQueue.length).toBe(0);
    });
  });
});

describe('Issue #12: Validation Race Condition Prevention', () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test('should prevent duplicate validations for same question', async () => {
    const { result } = renderHook(() => usePrefillStore());

    const questionId = 'q-1';

    // Start first validation
    act(() => {
      result.current.validatePrefill(questionId, { value: 'test' });
    });

    // Validation should be in progress
    expect(result.current.validationInProgress.get(questionId)).toBe(true);

    // Try to start second validation - should be prevented
    const consoleSpy = jest.spyOn(console, 'warn');
    act(() => {
      result.current.validatePrefill(questionId, { value: 'test2' });
    });

    // Should log warning about duplicate validation
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('Validation already in progress')
    );

    consoleSpy.mockRestore();
  });

  test('should release validation lock after completion', async () => {
    const { result } = renderHook(() => usePrefillStore());

    const questionId = 'q-1';

    // Start validation
    await act(async () => {
      result.current.validatePrefill(questionId, { value: 'test' });
      // Fast-forward timers to complete validation
      jest.advanceTimersByTime(150);
    });

    // Wait for async completion
    await act(async () => {
      await Promise.resolve();
    });

    // Lock should be released
    expect(result.current.validationInProgress.get(questionId)).toBeFalsy();
  });

  test('should allow validation after previous one completes', async () => {
    const { result } = renderHook(() => usePrefillStore());

    const questionId = 'q-1';

    // First validation
    await act(async () => {
      result.current.validatePrefill(questionId, { value: 'test1' });
      jest.advanceTimersByTime(150);
    });

    await act(async () => {
      await Promise.resolve();
    });

    // Lock should be released
    expect(result.current.validationInProgress.get(questionId)).toBeFalsy();

    // Second validation should be allowed
    act(() => {
      result.current.validatePrefill(questionId, { value: 'test2' });
    });

    // Should be in progress again
    expect(result.current.validationInProgress.get(questionId)).toBe(true);
  });

  test('should handle multiple questions validating concurrently', async () => {
    const { result } = renderHook(() => usePrefillStore());

    // Start validations for different questions
    act(() => {
      result.current.validatePrefill('q-1', { value: 'test1' });
      result.current.validatePrefill('q-2', { value: 'test2' });
      result.current.validatePrefill('q-3', { value: 'test3' });
    });

    // All should be in progress
    expect(result.current.validationInProgress.get('q-1')).toBe(true);
    expect(result.current.validationInProgress.get('q-2')).toBe(true);
    expect(result.current.validationInProgress.get('q-3')).toBe(true);

    // Complete all validations
    await act(async () => {
      jest.advanceTimersByTime(150);
      await Promise.resolve();
    });

    // All locks should be released
    expect(result.current.validationInProgress.get('q-1')).toBeFalsy();
    expect(result.current.validationInProgress.get('q-2')).toBeFalsy();
    expect(result.current.validationInProgress.get('q-3')).toBeFalsy();
  });
});

describe('Integration: Queue + Validation', () => {
  test('should handle offline queue and validation together', async () => {
    const { result } = renderHook(() => usePrefillStore());

    const questionId = 'q-1';

    // Add to queue
    act(() => {
      result.current.addToOfflineQueue({
        id: 'action-1',
        type: 'create',
        questionId,
        data: { value: 'test' },
        timestamp: Date.now()
      });
    });

    expect(result.current.offlineQueue.length).toBe(1);

    // Validate
    await act(async () => {
      result.current.validatePrefill(questionId, { value: 'test' });
      jest.advanceTimersByTime(150);
      await Promise.resolve();
    });

    // Both operations should complete successfully
    expect(result.current.offlineQueue.length).toBe(1);
    expect(result.current.validations[questionId]).toBeDefined();
    expect(result.current.validations[questionId].isValid).toBe(true);
  });
});
