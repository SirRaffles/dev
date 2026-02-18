import { useState, useEffect, useCallback } from 'react';
import { fetchSpeakers, createSpeaker, deleteSpeaker, Speaker } from '../utils/api';

export default function useSpeakers() {
  const [speakers, setSpeakers] = useState<Speaker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSpeakers();
      setSpeakers(data);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const addSpeaker = useCallback(async (name: string) => {
    await createSpeaker(name);
    await refresh();
  }, [refresh]);

  const removeSpeaker = useCallback(async (speakerId: string) => {
    await deleteSpeaker(speakerId);
    await refresh();
  }, [refresh]);

  return { speakers, loading, error, refresh, addSpeaker, removeSpeaker };
}
