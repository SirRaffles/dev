import { useState, useCallback, useRef, useEffect } from 'react';
import {
  fetchJobStatus,
  fetchBatchStatus,
  submitTranscription,
  submitYouTubeTranscription,
  submitBatchTranscription,
} from '../utils/api';
import { usePollingJob } from './usePollingJob';

const fetchTranscriptionStatus = (id: string) => fetchJobStatus(id, false);

interface BatchProgressItem {
  job_id: string;
  status: string;
  progress: number;
  error?: string;
}

interface BatchResultItem {
  job_id: string;
  result: any;
}

export function useTranscription() {
  const job = usePollingJob(fetchTranscriptionStatus);

  // Batch-specific state (not shared with useMultiModal)
  const [batchProgress, setBatchProgress] = useState<BatchProgressItem[]>([]);
  const [batchResults, setBatchResults] = useState<BatchResultItem[]>([]);
  const [batchId, setBatchId] = useState<string | null>(null);
  const batchPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Poll batch job status
  const pollBatchJobStatus = useCallback(async (batchId: string) => {
    try {
      const data = await fetchBatchStatus(batchId);

      setBatchProgress(data.jobs.map((j: any) => ({
        job_id: j.job_id,
        status: j.status,
        progress: j.progress,
        error: j.error,
      })));

      job.setProgress(data.overall_progress);
      job.setProgressMessage(`${data.completed}/${data.total} files completed`);

      if (data.overall_status === 'completed') {
        // Fetch all completed job results for batch navigation
        if (data.jobs.length > 0) {
          const allResults: BatchResultItem[] = await Promise.all(
            data.jobs.map(async (j: any) => {
              try {
                const resultData = await fetchJobStatus(j.job_id);
                return { job_id: j.job_id, result: resultData };
              } catch {
                return { job_id: j.job_id, result: null };
              }
            })
          );
          setBatchResults(allResults.filter(r => r.result !== null));
          // Display first result by default
          const firstResult = allResults.find(r => r.result !== null);
          if (firstResult) {
            job.updateResult(firstResult.result);
            job.startJob(firstResult.job_id);
          }
        }
        job.stopPolling();
        if (batchPollRef.current) {
          clearInterval(batchPollRef.current);
          batchPollRef.current = null;
        }
      } else if (data.overall_status === 'failed' && data.completed === 0) {
        job.failJob('All files failed to transcribe');
        if (batchPollRef.current) {
          clearInterval(batchPollRef.current);
          batchPollRef.current = null;
        }
      }
    } catch (err) {
      console.error('Error polling batch status:', err);
    }
  }, [job]);

  // Cleanup batch polling on unmount
  useEffect(() => {
    return () => {
      if (batchPollRef.current) {
        clearInterval(batchPollRef.current);
        batchPollRef.current = null;
      }
    };
  }, []);

  // Submit file for transcription
  const transcribeFile = useCallback(async (file: File, options: Record<string, any> = {}) => {
    job.reset();
    setBatchProgress([]);

    try {
      job.startJob(null, 'Starting...');
      const data = await submitTranscription(file, options);
      job.startJob(data.job_id, 'Processing...');
    } catch (err: any) {
      job.failJob(err.message || 'Failed to start transcription');
    }
  }, [job]);

  // Submit YouTube URL for transcription
  const transcribeYouTube = useCallback(async (url: string, options: Record<string, any> = {}) => {
    job.reset();
    setBatchProgress([]);

    try {
      job.startJob(null, 'Downloading video...');
      const data = await submitYouTubeTranscription(url, options);

      if (data.status === 'completed') {
        // Captions fast path: result is already available, fetch it directly
        const result = await fetchJobStatus(data.job_id, false);
        job.updateResult(result);
        job.startJob(data.job_id, 'Complete (YouTube captions)');
      } else {
        job.startJob(data.job_id, 'Processing...');
      }
    } catch (err: any) {
      job.failJob(err.message || 'Failed to start YouTube transcription');
    }
  }, [job]);

  // Submit multiple files for batch transcription
  const transcribeBatch = useCallback(async (files: File[], options: Record<string, any> = {}) => {
    job.reset();
    setBatchProgress([]);

    try {
      job.startJob(null, 'Uploading files...');
      const data = await submitBatchTranscription(files, options);

      setBatchProgress(data.job_ids.map((id: string) => ({ job_id: id, progress: 0, status: 'pending' })));

      // Start polling batch status (uses interval, not the single-job poller)
      const newBatchId = data.batch_id;
      setBatchId(newBatchId);
      batchPollRef.current = setInterval(() => {
        pollBatchJobStatus(newBatchId);
      }, 2000);
      pollBatchJobStatus(newBatchId);
    } catch (err: any) {
      job.failJob(err.message || 'Failed to start batch transcription');
    }
  }, [job, pollBatchJobStatus]);

  // Select a specific batch result to display
  const selectBatchResult = useCallback((index: number) => {
    if (batchResults[index]) {
      job.updateResult(batchResults[index].result);
      job.startJob(batchResults[index].job_id);
    }
  }, [batchResults, job]);

  // Track an already-submitted job by ID (e.g. after retry)
  const trackJob = useCallback((jobId: string) => {
    job.reset();
    setBatchProgress([]);
    setBatchResults([]);
    job.startJob(jobId, 'Retrying...');
  }, [job]);

  // Reset (also clears batch state)
  const reset = useCallback(() => {
    job.reset();
    setBatchProgress([]);
    setBatchResults([]);
    setBatchId(null);
    if (batchPollRef.current) {
      clearInterval(batchPollRef.current);
      batchPollRef.current = null;
    }
  }, [job]);

  return {
    isTranscribing: job.isActive,
    jobId: job.jobId,
    progress: job.progress,
    progressMessage: job.progressMessage,
    result: job.result,
    error: job.error,
    batchId,
    batchProgress,
    batchResults,
    selectBatchResult,
    transcribeFile,
    transcribeYouTube,
    transcribeBatch,
    trackJob,
    reset,
    updateResult: job.updateResult,
  };
}

export default useTranscription;
