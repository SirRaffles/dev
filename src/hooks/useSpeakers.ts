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

  const removeMany = useCallback(async (ids: string[]): Promise<{ ok: number; failed: { id: string; error: string }[] }> => {
    const failed: { id: string; error: string }[] = [];
    let ok = 0;
    // Sequential — the API rate limit is 120/min so bulk deletes are safe,
    // but keeping it serial avoids spiking against the current user's budget.
    for (const id of ids) {
      try {
        await deleteSpeaker(id);
        ok += 1;
      } catch (e: any) {
        failed.push({ id, error: e?.message || 'Delete failed' });
      }
    }
    await refresh();
    return { ok, failed };
  }, [refresh]);

  return { speakers, loading, error, refresh, addSpeaker, removeSpeaker, removeMany };
}
