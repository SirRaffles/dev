import { useEffect, useState, useCallback } from 'react';
import { fetchLearningLog, LearningEvent } from '../utils/api';

const PAGE_SIZE = 50;

export function useLearningLog(filter: { type?: string } = {}) {
  const [events, setEvents] = useState<LearningEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const reload = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchLearningLog({ ...filter, limit: PAGE_SIZE, offset: page * PAGE_SIZE })
      .then((r) => {
        if (cancelled) return;
        setEvents(r.events);
        setTotal(r.total);
      })
      .catch((e) => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [filter.type, page]);

  useEffect(() => {
    const cancel = reload();
    return cancel;
  }, [reload]);

  return {
    events, total, page, setPage, loading, error, reload,
    pageSize: PAGE_SIZE,
    hasNext: (page + 1) * PAGE_SIZE < total,
    hasPrev: page > 0,
  };
}
