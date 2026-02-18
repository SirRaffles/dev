import { useState, useEffect, useCallback } from 'react';
import { fetchJPRRecordings, JPRRecording } from '../utils/api';

export default function useRecordings() {
  const [recordings, setRecordings] = useState<JPRRecording[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchJPRRecordings();
      setRecordings(data.recordings);
      setTotal(data.total);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  return { recordings, total, loading, error, refresh };
}
