import { useState, useCallback, useRef, useEffect } from 'react';

/**
 * Shared hook for polling job status with backoff.
 * Used by useTranscription and useMultiModal to avoid duplication.
 */
export function usePollingJob(fetchStatusFn) {
  const [isActive, setIsActive] = useState(false);
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [progressMessage, setProgressMessage] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [phase, setPhase] = useState(null);

  const pollIntervalRef = useRef(null);
  const pollCountRef = useRef(0);
  const lastProgressRef = useRef(-1);
  const stagnantCountRef = useRef(0);

  // Exponential backoff when progress hasn't advanced for 3+ polls.
  // Caps at 10s. Resets to 1s whenever progress moves.
  const getPollInterval = () => {
    if (stagnantCountRef.current <= 3) {
      const count = pollCountRef.current;
      if (count < 10) return 1000;
      if (count < 30) return 2000;
      return 3000;
    }
    const exp = Math.min(stagnantCountRef.current - 3, 4);
    return Math.min(1000 * Math.pow(2, exp), 10000);
  };

  const stopPolling = useCallback(() => {
    if (pollIntervalRef.current) {
      clearTimeout(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }
  }, []);

  const pollJobStatus = useCallback(async (id) => {
    try {
      const data = await fetchStatusFn(id);

      const nextProgress = data.progress || 0;
      if (nextProgress !== lastProgressRef.current) {
        lastProgressRef.current = nextProgress;
        stagnantCountRef.current = 0;
      } else {
        stagnantCountRef.current += 1;
      }

      setProgress(nextProgress);
      setProgressMessage(data.progress_message || '');
      setPhase(data.phase ?? null);

      if (data.status === 'completed') {
        setResult(data);
        setIsActive(false);
        stopPolling();
        return data;
      } else if (data.status === 'failed') {
        setError(data.error || 'Processing failed');
        setIsActive(false);
        setJobId(null);
        stopPolling();
      }
      return data;
    } catch (err) {
      console.error('Error polling job status:', err);
      return null;
    }
  }, [fetchStatusFn, stopPolling]);

  // Start polling when job is created
  useEffect(() => {
    if (jobId && isActive) {
      pollCountRef.current = 0;
      lastProgressRef.current = -1;
      stagnantCountRef.current = 0;

      const schedulePoll = () => {
        pollIntervalRef.current = setTimeout(async () => {
          await pollJobStatus(jobId);
          pollCountRef.current += 1;
          if (pollIntervalRef.current !== null) {
            schedulePoll();
          }
        }, getPollInterval());
      };

      pollJobStatus(jobId);
      schedulePoll();
    }

    return stopPolling;
  }, [jobId, isActive, pollJobStatus, stopPolling]);

  const startJob = useCallback((id, message = 'Starting...') => {
    setError(null);
    setResult(null);
    setIsActive(true);
    setProgress(0);
    setProgressMessage(message);
    setJobId(id);
  }, []);

  const failJob = useCallback((msg) => {
    setError(msg);
    setIsActive(false);
  }, []);

  const reset = useCallback(() => {
    stopPolling();
    setIsActive(false);
    setJobId(null);
    setProgress(0);
    setProgressMessage('');
    setResult(null);
    setError(null);
    setPhase(null);
  }, [stopPolling]);

  const updateResult = useCallback((newResult) => {
    setResult(newResult);
  }, []);

  return {
    isActive,
    jobId,
    progress,
    progressMessage,
    result,
    error,
    phase,
    startJob,
    failJob,
    reset,
    updateResult,
    setProgress,
    setProgressMessage,
    stopPolling,
    pollJobStatus,
  };
}

export default usePollingJob;
