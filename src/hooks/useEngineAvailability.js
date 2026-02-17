import { useState, useCallback } from 'react';
import { API_URL } from '../utils/api';

/**
 * Fetches and tracks engine availability from the backend /health endpoint.
 * Returns engine flags and a fallback notice when Voxtral Local is unavailable.
 */
export default function useEngineAvailability() {
  const [voxtralAvailable, setVoxtralAvailable] = useState(false);
  const [voxtralLocalAvailable, setVoxtralLocalAvailable] = useState(false);
  const [backendError, setBackendError] = useState(null);
  const [fallbackNotice, setFallbackNotice] = useState(null);

  // Returns settings overrides if fallback is needed, or null if engines are fine
  const refreshEngines = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/health`);
      const data = await res.json();
      setBackendError(null);
      if (data.voxtral_available) setVoxtralAvailable(true);
      if (data.engines?.['voxtral-local']?.available) {
        setVoxtralLocalAvailable(true);
        return null; // no fallback needed
      } else {
        setFallbackNotice('Voxtral Local unavailable \u2014 using Whisper engine');
        return { engine: 'whisper', modelSize: 'large-v3-turbo' };
      }
    } catch {
      setBackendError('Cannot connect to transcription backend. Please check that the server is running.');
      return { engine: 'whisper', modelSize: 'large-v3-turbo' };
    }
  }, []);

  const dismissFallbackNotice = useCallback(() => setFallbackNotice(null), []);

  return {
    voxtralAvailable,
    voxtralLocalAvailable,
    backendError,
    fallbackNotice,
    dismissFallbackNotice,
    refreshEngines,
  };
}
