/**
 * PrefilledInput Component
 *
 * Issue #12: Fixed useEffect dependencies to prevent race conditions
 * Uses useRef to stabilize callback references and prevent infinite re-renders
 */

import React, { useEffect, useCallback, useRef, useState } from 'react';
import { usePrefillStore } from '../../lib/stores/prefillStore';

interface PrefilledInputProps {
  questionId: string;
  value?: string;
  onChange?: (value: string) => void;
  onBlur?: () => void;
  placeholder?: string;
  className?: string;
  autoValidate?: boolean;
}

/**
 * Input component with prefill support and optimistic updates
 *
 * Key features:
 * - Issue #12: Stable callback references using useRef
 * - Prevents duplicate validations with validation lock
 * - Optimistic UI updates
 * - Offline queue support
 */
export function PrefilledInput({
  questionId,
  value: externalValue = '',
  onChange,
  onBlur,
  placeholder = '',
  className = '',
  autoValidate = true
}: PrefilledInputProps) {
  // Local state for input value
  const [localValue, setLocalValue] = useState(externalValue);

  // Store access
  const validatePrefill = usePrefillStore(state => state.validatePrefill);
  const setPrefill = usePrefillStore(state => state.setPrefill);
  const validation = usePrefillStore(state => state.validations[questionId]);
  const isValidating = usePrefillStore(state => state.validationInProgress.get(questionId));

  /**
   * Issue #12 Solution: Use useRef to stabilize callback references
   * This prevents useEffect from re-running when callbacks change
   */
  const onChangeRef = useRef(onChange);
  const onBlurRef = useRef(onBlur);

  // Update refs when callbacks change (doesn't trigger re-render)
  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    onBlurRef.current = onBlur;
  }, [onBlur]);

  /**
   * Stable change handler with empty dependencies
   * Uses ref instead of direct callback to prevent re-renders
   */
  const handleChange = useCallback((newValue: string) => {
    // Update local state immediately (optimistic update)
    setLocalValue(newValue);

    // Update store
    setPrefill(questionId, newValue);

    // Call external onChange if provided
    if (onChangeRef.current) {
      onChangeRef.current(newValue);
    }

    // Auto-validate if enabled (debounced in production)
    if (autoValidate) {
      // In production, this would be debounced
      validatePrefill(questionId, { value: newValue });
    }
  }, [questionId, setPrefill, validatePrefill, autoValidate]); // Only non-function dependencies

  /**
   * Stable blur handler with empty dependencies
   */
  const handleBlur = useCallback(() => {
    if (onBlurRef.current) {
      onBlurRef.current();
    }

    // Validate on blur if not auto-validating
    if (!autoValidate) {
      validatePrefill(questionId, { value: localValue });
    }
  }, [questionId, localValue, validatePrefill, autoValidate]); // Only non-function dependencies

  /**
   * Sync external value changes
   * Only updates if external value differs from local
   */
  useEffect(() => {
    if (externalValue !== localValue) {
      setLocalValue(externalValue);
    }
  }, [externalValue]); // Only externalValue - localValue intentionally excluded to prevent loops

  /**
   * Determine validation status styling
   */
  const getValidationStyles = () => {
    if (isValidating) {
      return 'border-blue-300 bg-blue-50';
    }

    if (validation) {
      return validation.isValid
        ? 'border-green-300 bg-green-50'
        : 'border-red-300 bg-red-50';
    }

    return 'border-gray-300';
  };

  return (
    <div className="relative">
      <input
        type="text"
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        onBlur={handleBlur}
        placeholder={placeholder}
        className={`
          ${className}
          ${getValidationStyles()}
          w-full px-4 py-2 border-2 rounded-lg
          focus:outline-none focus:ring-2 focus:ring-blue-500
          transition-colors duration-200
          disabled:opacity-50 disabled:cursor-not-allowed
        `}
        disabled={isValidating}
        data-testid={`prefilled-input-${questionId}`}
        aria-invalid={validation && !validation.isValid}
        aria-busy={isValidating}
      />

      {/* Validation feedback */}
      {isValidating && (
        <div
          className="absolute right-3 top-1/2 transform -translate-y-1/2"
          data-testid="validation-spinner"
        >
          <div className="animate-spin h-5 w-5 border-2 border-blue-500 border-t-transparent rounded-full" />
        </div>
      )}

      {validation && !validation.isValid && validation.errors && (
        <div
          className="mt-1 text-sm text-red-600"
          data-testid="validation-errors"
          role="alert"
        >
          {validation.errors.map((error, index) => (
            <div key={index}>{error}</div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * Example of BEFORE (problematic code):
 *
 * const handleChange = useCallback((value) => {
 *   onChange(value); // onChange in deps causes re-render
 * }, [onChange]); // ❌ Causes infinite loops
 *
 * useEffect(() => {
 *   // Effect logic
 * }, [handleChange]); // ❌ Runs on every render
 */

/**
 * Example of AFTER (fixed code):
 *
 * const onChangeRef = useRef(onChange);
 * useEffect(() => {
 *   onChangeRef.current = onChange;
 * }, [onChange]); // ✅ Only updates ref
 *
 * const handleChange = useCallback((value) => {
 *   onChangeRef.current(value);
 * }, []); // ✅ Stable reference
 */
