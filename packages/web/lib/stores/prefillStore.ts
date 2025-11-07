/**
 * Prefill Store - Zustand store with localStorage persistence
 *
 * Features:
 * - Issue #6: Offline queue with size limits and FIFO eviction
 * - Issue #12: Validation lock to prevent race conditions
 * - Issue #14: localStorage versioning with migrations
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { applyMigrations } from './migrations';

// Issue #6: Maximum offline queue size (FIFO eviction)
const MAX_QUEUE_SIZE = 100;

// Issue #14: Storage version for migrations
const STORAGE_VERSION = 1;

// Type definitions
export interface OfflineAction {
  id: string;
  type: 'create' | 'update' | 'delete';
  questionId: string;
  data: any;
  timestamp: number;
}

export interface PrefillValidation {
  questionId: string;
  isValid: boolean;
  errors?: string[];
  timestamp: number;
}

export interface PrefillState {
  // Data
  prefills: Record<string, any>;
  offlineQueue: OfflineAction[];
  validations: Record<string, PrefillValidation>;

  // Issue #12: Validation lock to prevent race conditions
  validationInProgress: Map<string, boolean>;

  // Actions
  setPrefill: (questionId: string, value: any) => void;
  removePrefill: (questionId: string) => void;

  // Issue #6: Queue management with size limits
  addToOfflineQueue: (action: OfflineAction) => void;
  removeFromOfflineQueue: (actionId: string) => void;
  clearOfflineQueue: () => void;

  // Issue #12: Validation with race condition protection
  validatePrefill: (questionId: string, action: any) => Promise<void>;
  setValidation: (questionId: string, validation: PrefillValidation) => void;
}

// Mock toast for warnings (replace with actual toast library)
const toast = {
  warning: (message: string) => {
    console.warn(`[Toast Warning]: ${message}`);
    // In production, this would trigger a UI toast notification
  }
};

/**
 * Create the prefill store with persistence
 */
export const usePrefillStore = create<PrefillState>()(
  persist(
    (set, get) => ({
      // Initial state
      prefills: {},
      offlineQueue: [],
      validations: {},
      validationInProgress: new Map<string, boolean>(),

      // Set a prefill value
      setPrefill: (questionId: string, value: any) => {
        set((state) => ({
          prefills: {
            ...state.prefills,
            [questionId]: value
          }
        }));
      },

      // Remove a prefill value
      removePrefill: (questionId: string) => {
        set((state) => {
          const { [questionId]: removed, ...rest } = state.prefills;
          return { prefills: rest };
        });
      },

      /**
       * Issue #6: Add action to offline queue with size limit
       * Implements FIFO eviction when queue is full
       */
      addToOfflineQueue: (action: OfflineAction) => {
        set((state) => {
          const queue = [...state.offlineQueue];

          // Check if queue is at max capacity
          if (queue.length >= MAX_QUEUE_SIZE) {
            // Remove oldest item (FIFO)
            queue.shift();

            // Show warning toast
            toast.warning(`Offline queue full. Oldest action removed.`);
          }

          // Add new action to end of queue
          queue.push(action);

          return { offlineQueue: queue };
        });
      },

      // Remove specific action from queue
      removeFromOfflineQueue: (actionId: string) => {
        set((state) => ({
          offlineQueue: state.offlineQueue.filter(action => action.id !== actionId)
        }));
      },

      // Clear entire offline queue
      clearOfflineQueue: () => {
        set({ offlineQueue: [] });
      },

      /**
       * Issue #12: Validate prefill with race condition protection
       * Prevents duplicate validations from running concurrently
       */
      validatePrefill: async (questionId: string, action: any) => {
        const state = get();

        // Check if validation already in progress
        if (state.validationInProgress.get(questionId)) {
          console.warn(`Validation already in progress for question: ${questionId}`);
          return;
        }

        // Set validation lock
        const newInProgress = new Map(state.validationInProgress);
        newInProgress.set(questionId, true);
        set({ validationInProgress: newInProgress });

        try {
          // Simulate API call for validation
          // In production, this would be an actual API call
          await new Promise(resolve => setTimeout(resolve, 100));

          // Mock validation result
          const isValid = true;
          const validation: PrefillValidation = {
            questionId,
            isValid,
            errors: isValid ? undefined : ['Validation failed'],
            timestamp: Date.now()
          };

          // Update validation state
          get().setValidation(questionId, validation);

        } catch (error) {
          console.error(`Validation error for question ${questionId}:`, error);

          // Set error validation
          get().setValidation(questionId, {
            questionId,
            isValid: false,
            errors: ['Validation request failed'],
            timestamp: Date.now()
          });
        } finally {
          // Release validation lock
          const finalInProgress = new Map(get().validationInProgress);
          finalInProgress.delete(questionId);
          set({ validationInProgress: finalInProgress });
        }
      },

      // Set validation result
      setValidation: (questionId: string, validation: PrefillValidation) => {
        set((state) => ({
          validations: {
            ...state.validations,
            [questionId]: validation
          }
        }));
      }
    }),
    {
      name: 'prefill-storage',

      /**
       * Issue #14: localStorage versioning
       */
      version: STORAGE_VERSION,

      /**
       * Issue #14: Migration function for schema changes
       * Handles versioning and data migrations
       */
      migrate: (persistedState: any, version: number) => {
        console.log(`Migrating storage from version ${version} to ${STORAGE_VERSION}`);

        // If no version or version 0, apply migrations
        if (version === undefined || version < STORAGE_VERSION) {
          const migratedState = applyMigrations(
            persistedState,
            version || 0,
            STORAGE_VERSION
          );

          return migratedState;
        }

        // No migration needed
        return persistedState;
      },

      /**
       * Custom storage implementation to handle Map serialization
       * Maps need special handling for localStorage
       */
      storage: {
        getItem: (name) => {
          const str = localStorage.getItem(name);
          if (!str) return null;

          const { state } = JSON.parse(str);

          // Deserialize Map for validationInProgress
          if (state.validationInProgress) {
            state.validationInProgress = new Map(Object.entries(state.validationInProgress));
          } else {
            state.validationInProgress = new Map();
          }

          return JSON.parse(str);
        },

        setItem: (name, value) => {
          const str = JSON.stringify(value);
          const parsed = JSON.parse(str);

          // Serialize Map for validationInProgress
          if (parsed.state.validationInProgress instanceof Map) {
            parsed.state.validationInProgress = Object.fromEntries(
              parsed.state.validationInProgress
            );
          }

          localStorage.setItem(name, JSON.stringify(parsed));
        },

        removeItem: (name) => localStorage.removeItem(name)
      }
    }
  )
);

// Export constants for testing
export { MAX_QUEUE_SIZE, STORAGE_VERSION };
