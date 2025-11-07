/**
 * OfflineQueueStatus Component
 *
 * Issue #6: Displays offline queue status and warnings
 * Shows visual feedback when queue is near capacity
 */

import React from 'react';
import { usePrefillStore, MAX_QUEUE_SIZE } from '../../lib/stores/prefillStore';

interface OfflineQueueStatusProps {
  className?: string;
}

/**
 * Component to display offline queue status
 * - Shows queue size and maximum capacity
 * - Provides visual warning when queue is >80% full
 * - Hides when queue is empty
 */
export function OfflineQueueStatus({ className = '' }: OfflineQueueStatusProps) {
  // Subscribe to queue size from store
  const queueSize = usePrefillStore(state => state.offlineQueue.length);

  // Don't render if queue is empty
  if (queueSize === 0) {
    return null;
  }

  // Calculate capacity percentage
  const percentFull = (queueSize / MAX_QUEUE_SIZE) * 100;
  const isNearFull = percentFull > 80;
  const isCritical = percentFull > 95;

  // Determine status level and styling
  const statusLevel = isCritical ? 'critical' : isNearFull ? 'warning' : 'info';

  const statusColors = {
    info: 'bg-blue-100 text-blue-800 border-blue-300',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-300',
    critical: 'bg-red-100 text-red-800 border-red-300'
  };

  const statusIcons = {
    info: '📊',
    warning: '⚠️',
    critical: '🚨'
  };

  return (
    <div
      className={`
        ${statusColors[statusLevel]}
        ${className}
        px-4 py-3 rounded-lg border-2 shadow-sm
        flex items-center justify-between
        transition-all duration-300
      `}
      role="status"
      aria-live="polite"
      data-testid="offline-queue-status"
    >
      <div className="flex items-center space-x-3">
        <span className="text-2xl" role="img" aria-label={statusLevel}>
          {statusIcons[statusLevel]}
        </span>
        <div>
          <p className="font-semibold text-sm">
            Offline Queue: {queueSize}/{MAX_QUEUE_SIZE} actions pending
          </p>
          {isNearFull && (
            <p className="text-xs mt-1">
              {isCritical
                ? 'Queue is almost full! Oldest actions will be removed.'
                : 'Queue is filling up. Consider syncing soon.'}
            </p>
          )}
        </div>
      </div>

      {/* Progress bar */}
      <div className="ml-4 flex-shrink-0">
        <div className="w-24 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              isCritical ? 'bg-red-500' : isNearFull ? 'bg-yellow-500' : 'bg-blue-500'
            }`}
            style={{ width: `${Math.min(percentFull, 100)}%` }}
            role="progressbar"
            aria-valuenow={queueSize}
            aria-valuemin={0}
            aria-valuemax={MAX_QUEUE_SIZE}
          />
        </div>
      </div>
    </div>
  );
}

/**
 * Compact version of the status indicator
 * Useful for headers or toolbars
 */
export function CompactOfflineQueueStatus() {
  const queueSize = usePrefillStore(state => state.offlineQueue.length);

  if (queueSize === 0) {
    return null;
  }

  const percentFull = (queueSize / MAX_QUEUE_SIZE) * 100;
  const isNearFull = percentFull > 80;

  return (
    <div
      className={`
        inline-flex items-center space-x-2 px-3 py-1 rounded-full text-xs font-medium
        ${isNearFull ? 'bg-yellow-100 text-yellow-800' : 'bg-blue-100 text-blue-800'}
      `}
      data-testid="compact-offline-queue-status"
    >
      <span>{isNearFull ? '⚠️' : '📊'}</span>
      <span>
        {queueSize}/{MAX_QUEUE_SIZE}
      </span>
    </div>
  );
}
