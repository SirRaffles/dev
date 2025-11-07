/**
 * Storage migrations for prefillStore
 * Each migration handles the transition from one version to another
 */

export interface MigrationState {
  offlineQueue?: any[];
  validations?: Record<string, any>;
  validationInProgress?: Map<string, boolean>;
  prefills?: Record<string, any>;
  [key: string]: any;
}

export const migrations = {
  /**
   * Migration from v0 (unversioned) to v1
   * Clears stale data from beta version
   */
  0: (state: MigrationState): MigrationState => {
    console.log('Migrating from v0 to v1: Clearing stale data from beta version');
    return {
      ...state,
      offlineQueue: [],
      validations: {},
      validationInProgress: new Map()
    };
  },

  /**
   * Migration from v1 to v2
   * Placeholder for future migrations
   */
  1: (state: MigrationState): MigrationState => {
    console.log('Migrating from v1 to v2: No changes needed');
    return state;
  }
};

/**
 * Apply migrations from stored version to current version
 */
export function applyMigrations(state: MigrationState, fromVersion: number, toVersion: number): MigrationState {
  let migratedState = state;

  // Apply each migration in sequence
  for (let version = fromVersion; version < toVersion; version++) {
    const migration = migrations[version as keyof typeof migrations];
    if (migration) {
      migratedState = migration(migratedState);
    }
  }

  return migratedState;
}
