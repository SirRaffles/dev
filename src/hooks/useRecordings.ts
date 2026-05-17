import { useState, useEffect, useCallback, useRef } from 'react';
import { fetchRecordings, JPRRecording, JPRListParams } from '../utils/api';

export type RecordingsStatus = 'all' | 'unprocessed' | 'processed' | 'processing' | 'failed';
export type RecordingsSort = 'date' | 'completed_at';

interface Options {
  status?: RecordingsStatus;
  sortBy?: RecordingsSort;
  sortDir?: 'asc' | 'desc';
  q?: string;
  debounceMs?: number;
}

/**
 * Recordings hook with server-side filter/sort/search.
 *
 * Search is debounced (default 250 ms) so typing doesn't hammer the backend.
 * Refresh is force-through (no debounce) for explicit user-triggered refreshes.
 */
export default function useRecordings(opts: Options = {}) {
  const {
    status = 'all',
    sortBy = 'date',
    sortDir = 'desc',
    q = '',
    debounceMs = 250,
  } = opts;

  const [recordings, setRecordings] = useState<JPRRecording[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const abortRef = useRef<AbortController | null>(null);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async (params: JPRListParams) => {
    // Cancel any pending request for stale params.
    if (abortRef.current) abortRef.current.abort();
    const ac = new AbortController();
    abortRef.current = ac;

    setLoading(true);
    setError(null);
    try {
      const data = await fetchRecordings(params);
      if (ac.signal.aborted) return;
      setRecordings(data.recordings);
      setTotal(data.total);
    } catch (e: any) {
      if (ac.signal.aborted) return;
      setError(e?.message || 'Failed to load recordings');
    } finally {
      if (!ac.signal.aborted) setLoading(false);
    }
  }, []);

  // Run (debounced) whenever any filter changes.
  useEffect(() => {
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    const params: JPRListParams = {
      status,
      sort_by: sortBy,
      sort_dir: sortDir,
      q,
      limit: 200,
    };
    const delay = q && q.length > 0 ? debounceMs : 0;
    debounceTimerRef.current = setTimeout(() => load(params), delay);
    return () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    };
  }, [status, sortBy, sortDir, q, debounceMs, load]);

  const refresh = useCallback(() => {
    load({ status, sort_by: sortBy, sort_dir: sortDir, q, limit: 200 });
  }, [status, sortBy, sortDir, q, load]);

  return { recordings, total, loading, error, refresh };
}
