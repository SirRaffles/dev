import { useState, useEffect, useCallback } from 'react';
import { fetchCalls, CallMetadata } from '../utils/api';

export default function useCalls() {
  const [calls, setCalls] = useState<CallMetadata[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchCalls(50, 0, statusFilter);
      setCalls(data.calls);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { refresh(); }, [refresh]);

  return { calls, total, loading, error, refresh, statusFilter, setStatusFilter };
}
