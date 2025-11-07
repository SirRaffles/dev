/**
 * Phase 2: Data Integrity Architecture
 * Main entry point for @app/web package
 */

// Store exports
export {
  usePrefillStore,
  MAX_QUEUE_SIZE,
  STORAGE_VERSION,
  type OfflineAction,
  type PrefillValidation,
  type PrefillState
} from './lib/stores/prefillStore';

export {
  migrations,
  applyMigrations,
  type MigrationState
} from './lib/stores/migrations';

// Component exports
export {
  OfflineQueueStatus,
  CompactOfflineQueueStatus
} from './components/prefills/OfflineQueueStatus';

export {
  PrefilledInput
} from './components/forms/PrefilledInput';
