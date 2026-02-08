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

  const pollIntervalRef = useRef(null);
  const pollCountRef = useRef(0);

  const getPollInterval = () => {
    const count = pollCountRef.current;
    if (count < 10) return 1000;   // First 10s: every 1s
    if (count < 30) return 2000;   // Next 40s: every 2s
    return 5000;                    // After that: every 5s
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

      setProgress(data.progress || 0);
      setProgressMessage(data.progress_message || '');

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
