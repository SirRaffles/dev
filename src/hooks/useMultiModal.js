import { useCallback } from 'react';
import { fetchJobStatus, submitMultiModalProcessing } from '../utils/api';
import { usePollingJob } from './usePollingJob';

const fetchMultiModalStatus = (id) => fetchJobStatus(id, true);

export function useMultiModal() {
  const job = usePollingJob(fetchMultiModalStatus);

  const processDocument = useCallback(async (file, options = {}) => {
    job.reset();
    job.startJob(null, 'Starting document processing...');

    try {
      const data = await submitMultiModalProcessing(file, options);
      job.startJob(data.job_id, 'Processing document...');
    } catch (err) {
      job.failJob(err.message || 'Failed to start document processing');
    }
  }, [job]);

  return {
    isProcessing: job.isActive,
    jobId: job.jobId,
    progress: job.progress,
    progressMessage: job.progressMessage,
    result: job.result,
    error: job.error,
    processDocument,
    reset: job.reset,
    updateResult: job.updateResult,
  };
}

export default useMultiModal;
