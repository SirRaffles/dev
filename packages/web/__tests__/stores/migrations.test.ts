/**
 * Tests for localStorage migrations
 *
 * Coverage:
 * - Issue #14: Storage versioning
 * - Migration from v0 to v1
 * - Stale data cleanup
 * - New installations
 */

import { migrations, applyMigrations, MigrationState } from '../../lib/stores/migrations';

describe('Issue #14: localStorage Versioning and Migrations', () => {
  describe('Migration v0 to v1', () => {
    test('should clear stale data from beta version', () => {
      const staleState: MigrationState = {
        offlineQueue: [
          { id: '1', type: 'create', questionId: 'q-1', data: { stale: true }, timestamp: 123 },
          { id: '2', type: 'update', questionId: 'q-2', data: { stale: true }, timestamp: 456 }
        ],
        validations: {
          'q-1': { questionId: 'q-1', isValid: true, timestamp: 789 },
          'q-2': { questionId: 'q-2', isValid: false, errors: ['old error'], timestamp: 101112 }
        },
        prefills: {
          'q-1': 'some old value',
          'q-2': 'another old value'
        },
        validationInProgress: new Map([['q-1', true]])
      };

      const migratedState = migrations[0](staleState);

      // Should clear offline queue
      expect(migratedState.offlineQueue).toEqual([]);

      // Should clear validations
      expect(migratedState.validations).toEqual({});

      // Should clear validation in progress
      expect(migratedState.validationInProgress).toEqual(new Map());

      // Should preserve other state
      expect(migratedState.prefills).toEqual(staleState.prefills);
    });

    test('should log migration message', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      const state: MigrationState = {
        offlineQueue: [],
        validations: {}
      };

      migrations[0](state);

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('Migrating from v0 to v1')
      );

      consoleSpy.mockRestore();
    });

    test('should handle empty state', () => {
      const emptyState: MigrationState = {};

      const migratedState = migrations[0](emptyState);

      expect(migratedState.offlineQueue).toEqual([]);
      expect(migratedState.validations).toEqual({});
      expect(migratedState.validationInProgress).toEqual(new Map());
    });

    test('should handle partially populated state', () => {
      const partialState: MigrationState = {
        offlineQueue: [
          { id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }
        ]
        // No validations or other fields
      };

      const migratedState = migrations[0](partialState);

      expect(migratedState.offlineQueue).toEqual([]);
      expect(migratedState.validations).toEqual({});
    });
  });

  describe('Migration v1 to v2', () => {
    test('should be a no-op placeholder', () => {
      const state: MigrationState = {
        offlineQueue: [
          { id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }
        ],
        validations: {
          'q-1': { questionId: 'q-1', isValid: true, timestamp: 456 }
        },
        prefills: {
          'q-1': 'value'
        }
      };

      const migratedState = migrations[1](state);

      // Should return state unchanged
      expect(migratedState).toEqual(state);
    });

    test('should log no changes message', () => {
      const consoleSpy = jest.spyOn(console, 'log').mockImplementation();

      migrations[1]({});

      expect(consoleSpy).toHaveBeenCalledWith(
        expect.stringContaining('No changes needed')
      );

      consoleSpy.mockRestore();
    });
  });

  describe('applyMigrations helper', () => {
    test('should apply single migration', () => {
      const state: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }],
        validations: { 'q-1': { questionId: 'q-1', isValid: true, timestamp: 456 } }
      };

      const migratedState = applyMigrations(state, 0, 1);

      // Should have applied v0 migration
      expect(migratedState.offlineQueue).toEqual([]);
      expect(migratedState.validations).toEqual({});
    });

    test('should apply multiple migrations in sequence', () => {
      const state: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }],
        validations: { 'q-1': { questionId: 'q-1', isValid: true, timestamp: 456 } },
        someData: 'test'
      };

      const migratedState = applyMigrations(state, 0, 2);

      // Should apply v0 and v1 migrations
      expect(migratedState.offlineQueue).toEqual([]);
      expect(migratedState.validations).toEqual({});
    });

    test('should handle no migrations needed', () => {
      const state: MigrationState = {
        offlineQueue: [],
        validations: {}
      };

      const migratedState = applyMigrations(state, 1, 1);

      // Should return state unchanged
      expect(migratedState).toEqual(state);
    });

    test('should skip if fromVersion equals toVersion', () => {
      const state: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }]
      };

      const migratedState = applyMigrations(state, 2, 2);

      // Should not apply any migrations
      expect(migratedState.offlineQueue).toHaveLength(1);
    });

    test('should handle migration chain', () => {
      const initialState: MigrationState = {
        offlineQueue: [
          { id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 },
          { id: '2', type: 'update', questionId: 'q-2', data: {}, timestamp: 456 }
        ],
        validations: {
          'q-1': { questionId: 'q-1', isValid: true, timestamp: 789 },
          'q-2': { questionId: 'q-2', isValid: false, timestamp: 101112 }
        },
        prefills: {
          'q-1': 'value1',
          'q-2': 'value2'
        }
      };

      // Migrate from v0 to v2
      const migratedState = applyMigrations(initialState, 0, 2);

      // v0 migration should clear queue and validations
      expect(migratedState.offlineQueue).toEqual([]);
      expect(migratedState.validations).toEqual({});

      // v1 migration should leave everything as-is
      // prefills should be preserved
      expect(migratedState.prefills).toEqual(initialState.prefills);
    });
  });

  describe('Edge cases', () => {
    test('should handle migration with undefined fromVersion', () => {
      const state: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }]
      };

      // Treat undefined as version 0
      const migratedState = applyMigrations(state, 0, 1);

      expect(migratedState.offlineQueue).toEqual([]);
    });

    test('should preserve extra state properties during migration', () => {
      const state: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }],
        validations: {},
        customField: 'should be preserved',
        anotherCustom: { nested: 'data' }
      };

      const migratedState = migrations[0](state);

      // Should preserve custom fields
      expect(migratedState.customField).toBe('should be preserved');
      expect(migratedState.anotherCustom).toEqual({ nested: 'data' });
    });

    test('should handle very large offline queue during migration', () => {
      const largeQueue = Array.from({ length: 1000 }, (_, i) => ({
        id: `action-${i}`,
        type: 'create' as const,
        questionId: `q-${i}`,
        data: { value: i },
        timestamp: Date.now()
      }));

      const state: MigrationState = {
        offlineQueue: largeQueue,
        validations: {}
      };

      const migratedState = migrations[0](state);

      // Should clear all items
      expect(migratedState.offlineQueue).toEqual([]);
    });

    test('should handle corrupt validation data during migration', () => {
      const state: MigrationState = {
        offlineQueue: [],
        validations: {
          'q-1': { questionId: 'q-1', isValid: true, timestamp: 123 } as any,
          'q-2': null as any, // Corrupt data
          'q-3': undefined as any, // Corrupt data
          'q-4': 'invalid' as any // Corrupt data
        }
      };

      const migratedState = migrations[0](state);

      // Should clear all validations including corrupt ones
      expect(migratedState.validations).toEqual({});
    });
  });

  describe('Version upgrade scenarios', () => {
    test('should handle fresh install (no previous version)', () => {
      const newState: MigrationState = {
        offlineQueue: [],
        validations: {},
        prefills: {}
      };

      // No migration needed for fresh install
      const result = applyMigrations(newState, 1, 1);

      expect(result).toEqual(newState);
    });

    test('should handle upgrade from beta (v0) to stable (v1)', () => {
      const betaState: MigrationState = {
        offlineQueue: [
          { id: 'beta-1', type: 'create', questionId: 'q-beta', data: { beta: true }, timestamp: 123 }
        ],
        validations: {
          'q-beta': { questionId: 'q-beta', isValid: false, errors: ['beta error'], timestamp: 456 }
        },
        prefills: {
          'q-beta': 'beta value'
        }
      };

      const stableState = applyMigrations(betaState, 0, 1);

      // Should clear beta data
      expect(stableState.offlineQueue).toEqual([]);
      expect(stableState.validations).toEqual({});

      // Should preserve prefills
      expect(stableState.prefills).toEqual({ 'q-beta': 'beta value' });
    });

    test('should handle multi-version upgrade', () => {
      const oldState: MigrationState = {
        offlineQueue: [{ id: '1', type: 'create', questionId: 'q-1', data: {}, timestamp: 123 }],
        validations: { 'q-1': { questionId: 'q-1', isValid: true, timestamp: 456 } }
      };

      // Skip multiple versions
      const currentState = applyMigrations(oldState, 0, 2);

      // Should apply all intermediate migrations
      expect(currentState.offlineQueue).toEqual([]);
      expect(currentState.validations).toEqual({});
    });
  });

  describe('Real-world scenarios', () => {
    test('should migrate user with pending offline actions', () => {
      const userState: MigrationState = {
        offlineQueue: [
          { id: 'offline-1', type: 'create', questionId: 'q-1', data: { answer: 'yes' }, timestamp: 1000 },
          { id: 'offline-2', type: 'update', questionId: 'q-2', data: { answer: 'no' }, timestamp: 2000 }
        ],
        validations: {
          'q-1': { questionId: 'q-1', isValid: true, timestamp: 1500 }
        },
        prefills: {
          'q-1': 'yes',
          'q-2': 'no',
          'q-3': 'maybe'
        }
      };

      const migratedState = migrations[0](userState);

      // Offline queue should be cleared (user will need to re-enter data)
      expect(migratedState.offlineQueue).toEqual([]);

      // Validations should be cleared
      expect(migratedState.validations).toEqual({});

      // Prefills should be preserved (most important user data)
      expect(migratedState.prefills).toEqual(userState.prefills);
    });

    test('should handle migration during active validation', () => {
      const activeState: MigrationState = {
        offlineQueue: [],
        validations: {
          'q-active': { questionId: 'q-active', isValid: true, timestamp: Date.now() }
        },
        validationInProgress: new Map([
          ['q-1', true],
          ['q-2', true]
        ]),
        prefills: {
          'q-active': 'current value'
        }
      };

      const migratedState = migrations[0](activeState);

      // Should clear in-progress validations
      expect(migratedState.validationInProgress).toEqual(new Map());

      // Should clear completed validations
      expect(migratedState.validations).toEqual({});

      // Should preserve data
      expect(migratedState.prefills).toEqual(activeState.prefills);
    });
  });
});
