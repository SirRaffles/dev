import { useState, useRef, useEffect, useCallback } from 'react';
import { checkWakeStatus } from '../utils/api';
import type { WakeStatus } from '../utils/api';

interface UseWakeOnLanParams {
  onAwake?: () => Promise<void> | void;
}

interface UseWakeOnLanReturn {
  macState: string | null;
  setMacState: React.Dispatch<React.SetStateAction<string | null>>;
  wakeStartTime: number | null;
  detectProxy: () => Promise<WakeStatus | null>;
  triggerWake: (apiUrl: string) => void;
  queueSubmit: () => void;
  hasPendingSubmit: () => boolean;
}

/**
 * Manages Wake-on-LAN state for NAS proxy deployments.
 * Detects if behind a wake proxy, tracks Mac state, and handles
 * auto-wake + queued submission when Mac becomes available.
 */
export default function useWakeOnLan({ onAwake }: UseWakeOnLanParams): UseWakeOnLanReturn {
  // null = direct connection (no proxy), otherwise 'awake', 'sleeping', 'waking'
  const [macState, setMacState] = useState<string | null>(null);
  const [wakeStartTime, setWakeStartTime] = useState<number | null>(null);
  const pendingSubmitRef = useRef(false);

  // Check initial wake status on mount
  const detectProxy = useCallback(async (): Promise<WakeStatus | null> => {
    const proxyData = await checkWakeStatus();
    if (proxyData) {
      setMacState(proxyData.mac_state);
      return proxyData;
    }
    return null;
  }, []);

  // Poll while waking; fire onAwake when ready
  useEffect(() => {
    if (macState !== 'waking') return;
    const interval = setInterval(async () => {
      const status = await checkWakeStatus();
      if (!status) return;
      setMacState(status.mac_state);
      if (status.mac_state === 'awake' && status.model_loaded) {
        clearInterval(interval);
        if (onAwake) await onAwake();
        if (pendingSubmitRef.current) {
          pendingSubmitRef.current = false;
        }
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [macState, onAwake]);

  // Trigger wake and queue a submit
  const triggerWake = useCallback((apiUrl: string) => {
    pendingSubmitRef.current = true;
    setWakeStartTime(Date.now());
    setMacState('waking');
    // Fire a request to trigger WoL on the proxy
    fetch(`${apiUrl}/health`).catch(() => {});
  }, []);

  // Queue a pending submit (when already waking)
  const queueSubmit = useCallback(() => {
    pendingSubmitRef.current = true;
  }, []);

  const hasPendingSubmit = useCallback(() => {
    const pending = pendingSubmitRef.current;
    pendingSubmitRef.current = false;
    return pending;
  }, []);

  return {
    macState,
    setMacState,
    wakeStartTime,
    detectProxy,
    triggerWake,
    queueSubmit,
    hasPendingSubmit,
  };
}
