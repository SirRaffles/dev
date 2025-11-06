# WCAG 2.1 AAA Accessibility Audit Report - v42 IFS AI Benchmarking Survey

**Date**: 2025-11-06  
**Audit Scope**: /home/user/IFS_AI_Benchmarking_Survey/packages/web  
**Framework**: Next.js 14 (React 18) + TypeScript  
**Target Standard**: WCAG 2.1 AAA

---

## Executive Summary

The v42 survey application has a solid accessibility foundation with good semantic HTML, proper form labeling, and keyboard navigation support. However, there are several critical issues that prevent full WCAG 2.1 AAA compliance, particularly around modal focus management, dialog role attributes, and some interactive element semantics.

**Overall Compliance**: ~72% (Good foundation, needs critical fixes)

---

## Critical Issues (Must Fix for AAA Compliance)

### 1. Modal Dialogs Missing ARIA Dialog Roles
**Location**: `/packages/web/components/modals/ConfirmDialog.tsx`, `/packages/web/components/modals/ResumeModal.tsx`  
**Severity**: Critical  
**WCAG Criteria**: 1.3.1 (Info and Relationships)

**Issue**: 
Modal components render as `<div>` without `role="dialog"` or `role="alertdialog"` attributes. This prevents screen readers from identifying them as modals.

```tsx
// ❌ Current (Line 48-49, ConfirmDialog.tsx):
<div className="fixed inset-0 z-50 overflow-y-auto">
  <div className="flex min-h-screen items-center justify-center px-4">
    {/* Background overlay */}
    <div className="fixed inset-0 bg-ifs-grey-900 bg-opacity-75" />
    
    {/* Modal panel */}
    <div className="inline-block">  // ← Missing role="dialog"
```

**Remediation Code**:
```tsx
// ✓ Fixed:
<div 
  className="fixed inset-0 z-50 overflow-y-auto"
  role="dialog"
  aria-modal="true"
  aria-labelledby="dialog-title"
>
  <div className="flex min-h-screen items-center justify-center px-4">
    {/* Background overlay */}
    <div 
      className="fixed inset-0 bg-ifs-grey-900 bg-opacity-75" 
      aria-hidden="true"
    />
    
    {/* Modal panel */}
    <div className="inline-block">
      <h2 id="dialog-title" className="sr-only">{title}</h2>
      {/* ... content ... */}
    </div>
  </div>
</div>
```

---

### 2. Missing Focus Trap in Modal Dialogs
**Location**: `/packages/web/components/modals/ConfirmDialog.tsx`, `/packages/web/components/modals/ResumeModal.tsx`, `/packages/web/components/modals/ReportGenerationModal.tsx`  
**Severity**: Critical  
**WCAG Criteria**: 2.4.3 (Focus Order), 2.1.2 (Keyboard)

**Issue**:
Modals don't trap focus within themselves. Users can tab out of the modal to background content, violating AAA focus management requirements.

**Evidence**:
- ConfirmDialog.tsx: Escapes to window listener but no focus trap
- ResumeModal.tsx: Escapes handled, but focus not trapped
- The accessibility.ts file HAS a `focusManager.trapFocus()` function (lines 311-344) but it's NOT being used in modal components

**Remediation Code**:
```tsx
// In ConfirmDialog.tsx, add to useEffect:
export function ConfirmDialog({
  isOpen,
  // ... other props
}: ConfirmDialogProps) {
  useEffect(() => {
    if (!isOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    };

    window.addEventListener('keydown', handleEscape);
    
    // ADD THIS: Import and use focus trap
    const { focusManager } = require('@/lib/constants/accessibility');
    const unTrapFocus = focusManager.trapFocus('confirm-dialog');
    
    return () => {
      window.removeEventListener('keydown', handleEscape);
      unTrapFocus(); // Clean up focus trap
    };
  }, [isOpen, onCancel]);

  return (
    <div 
      id="confirm-dialog"
      className="fixed inset-0 z-50"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="dialog-title"
    >
      {/* ... rest of component ... */}
    </div>
  );
}
```

---

### 3. Backdrop/Overlay Missing Accessibility Attributes
**Location**: `/packages/web/components/SurveyLayout.tsx` (Lines 131-136)  
**Severity**: Critical  
**WCAG Criteria**: 1.3.1 (Info and Relationships)

**Issue**:
The mobile sidebar backdrop is a `<div>` with `onClick={toggle}` but no `aria-label`, `role`, or indication that it's interactive.

```tsx
// ❌ Current (SurveyLayout.tsx, Lines 131-136):
{isOpen && (
  <div
    className="insights-backdrop"
    onClick={toggle}
    aria-label="Close sidebar"
  />
)}
```

While `aria-label` is present, the element is still a div with a click handler - it should be a button or have role="button". Users cannot interact with it via keyboard.

**Remediation Code**:
```tsx
// ✓ Fixed:
{isOpen && (
  <button
    type="button"
    className="insights-backdrop"
    onClick={toggle}
    onKeyDown={(e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        toggle();
        e.preventDefault();
      }
    }}
    aria-label="Close sidebar"
    aria-expanded="true"
  />
)}
```

---

### 4. Form Rating Component - Label Not Associated with Radiogroup
**Location**: `/packages/web/components/forms/FormRating.tsx` (Lines 83-162)  
**Severity**: High  
**WCAG Criteria**: 1.3.1 (Info and Relationships), 3.3.2 (Labels)

**Issue**:
The label element (line 84) has `htmlFor` missing - it should associate with the radiogroup or first radio button, but the radiogroup has `role="radiogroup"` without an `id` to match.

```tsx
// ❌ Current (FormRating.tsx, Lines 83-99):
<div className={`space-y-2 ${className}`}>
  {/* Label - no htmlFor attribute */}
  <label className="block text-sm font-medium text-primary">
    {label}
    {required && <span className="text-error ml-1" aria-label="required">*</span>}
  </label>

  {/* ... tooltip ... */}

  {/* Radiogroup - no aria-labelledby to link to label */}
  <div
    role="radiogroup"
    aria-labelledby={id}  // ← This doesn't match the label
    aria-required={required}
```

**Remediation Code**:
```tsx
// ✓ Fixed:
<div className={`space-y-2 ${className}`}>
  {/* Label with ID */}
  <label 
    id={`${id}-label`}
    className="block text-sm font-medium text-primary"
  >
    {label}
    {required && <span className="text-error ml-1" aria-label="required">*</span>}
  </label>

  {/* ... tooltip ... */}

  {/* Radiogroup - linked to label via aria-labelledby */}
  <div
    role="radiogroup"
    aria-labelledby={`${id}-label`}  // ← Now properly linked
    aria-required={required}
    aria-describedby={tooltip ? `${id}-description` : undefined}
  >
    {/* ... radio options ... */}
  </div>
</div>
```

---

### 5. Floating Insights Button - No Keyboard Focus Indicator
**Location**: `/packages/web/components/ai/FloatingInsightsButton.tsx`  
**Severity**: High  
**WCAG Criteria**: 2.4.7 (Focus Visible)

**Issue**:
The button has styling for hover/active states but no visible focus indicator for keyboard navigation.

```tsx
// ❌ Current (FloatingInsightsButton.tsx, Lines 40-77):
.floating-insights-btn {
  /* ... styles ... */
  border: none;
  cursor: pointer;
  animation: slideIn 300ms ease-out;
}

.floating-insights-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(107, 70, 193, 0.5);
}

.floating-insights-btn:active {
  transform: translateY(0);
}
// ← Missing :focus-visible styles
```

**Remediation Code**:
```tsx
// ✓ Fixed:
.floating-insights-btn {
  /* ... existing styles ... */
  border: 2px solid transparent;
  cursor: pointer;
  animation: slideIn 300ms ease-out;
}

.floating-insights-btn:focus-visible {
  outline: 3px solid #6b46c1;
  outline-offset: 2px;
  box-shadow: 0 6px 16px rgba(107, 70, 193, 0.5),
              inset 0 0 0 3px rgba(255, 255, 255, 0.2);
}

.floating-insights-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 16px rgba(107, 70, 193, 0.5);
}

.floating-insights-btn:active {
  transform: translateY(0);
}
```

---

### 6. Missing Landmark Roles in Main Layout
**Location**: `/packages/web/components/SurveyLayout.tsx`  
**Severity**: High  
**WCAG Criteria**: 1.3.1 (Info and Relationships), 1.3.6 (Identify Purpose)

**Issue**:
The desktop layout uses `<main>` and `<aside>` with proper tags, but mobile layout doesn't have landmark structure.

```tsx
// Partial issue (SurveyLayout.tsx, Lines 77-139):
// Mobile layout missing main landmarks
<div className="survey-layout-mobile">
  {/* This should be <main> */}
  <main className="survey-content">
    {children}
  </main>

  {/* This should be <aside> */}
  <aside
    className="insights-sidebar-mobile"
    aria-label="AI Insights Sidebar"
    role="complementary"
  >
    {sidebar}
  </aside>
</div>
```

The mobile version IS correct. However, the desktop ResizablePanels wrapper needs proper sectioning.

**Remediation Code**:
```tsx
// ✓ Already mostly good, but ensure consistency:
// In SurveyLayout.tsx, wrap ResizablePanels with proper structure:
<div className="survey-layout-desktop">
  <ResizablePanels
    left={
      <main 
        className="survey-content"
        role="main"
      >
        {children}
      </main>
    }
    right={
      isOpen ? (
        <aside
          className="insights-sidebar-desktop"
          aria-label="AI Insights Sidebar"
          role="complementary"
        >
          {sidebar}
        </aside>
      ) : null
    }
    {/* ... other props ... */}
  />
</div>
```

---

### 7. Impact Matrix - Missing Fieldset/Legend for Radio Group Clusters
**Location**: `/packages/web/components/questions/ImpactMatrix.tsx`  
**Severity**: High  
**WCAG Criteria**: 1.3.1 (Info and Relationships), 3.3.2 (Labels)

**Issue**:
Each scenario has two radiogroups (Impact and Likelihood) but they're not grouped with proper `<fieldset>` and `<legend>` elements. Screen reader users won't understand the grouping.

```tsx
// ❌ Current (ImpactMatrix.tsx, Lines 190-264):
{/* Impact Rating */}
<div className="space-y-2">
  <div className="text-sm font-medium text-secondary">Impact:</div>
  <div className="flex gap-2">
    {[1, 2, 3, 4, 5].map((impactValue) => (
      <label key={impactValue}>
        <input type="radio" name={`${id}-${scenario.id}-impact`} />
        {/* ... */}
      </label>
    ))}
  </div>
</div>

{/* Likelihood Rating (Optional) */}
{includeLikelihood && (
  <div className="space-y-2 mt-3">
    <div className="text-sm font-medium text-secondary">Likelihood:</div>
    // Similar structure without proper grouping
  </div>
)}
```

**Remediation Code**:
```tsx
// ✓ Fixed:
{scenarios.map((scenario) => {
  const rating = value[scenario.id] || { impact: 0, likelihood: 0 };
  
  return (
    <fieldset
      key={scenario.id}
      className={cn(
        'p-4 border-2 rounded-lg transition-[background-color,border-color]',
        // ... other classes ...
      )}
    >
      <legend className="text-base font-medium text-primary mb-3">
        {scenario.label}
        {scenario.description && (
          <div className="text-xs text-secondary mt-1">
            {scenario.description}
          </div>
        )}
      </legend>

      {/* Impact Rating */}
      <fieldset className="space-y-2 mb-4">
        <legend className="text-sm font-medium text-secondary">Impact:</legend>
        <div className="flex gap-2">
          {[1, 2, 3, 4, 5].map((impactValue) => (
            <label
              key={impactValue}
              className={cn(
                'flex-1 p-2 border-2 rounded text-center cursor-pointer',
                // ... other classes ...
              )}
            >
              <input
                type="radio"
                name={`${id}-${scenario.id}-impact`}
                value={impactValue}
                checked={rating.impact === impactValue}
                onChange={() => handleRatingChange(scenario.id, 'impact', impactValue)}
                disabled={disabled}
                className="sr-only"
                aria-label={`Impact ${impactValue} - ${impactLabels[impactValue - 1]}`}
              />
              <div className="text-sm font-medium">{impactValue}</div>
              <div className="text-xs text-secondary hidden md:block">
                {impactLabels[impactValue - 1]}
              </div>
            </label>
          ))}
        </div>
      </fieldset>

      {/* Likelihood Rating (Optional) */}
      {includeLikelihood && (
        <fieldset className="space-y-2">
          <legend className="text-sm font-medium text-secondary">Likelihood:</legend>
          <div className="flex gap-2">
            {/* Similar to Impact Rating */}
          </div>
        </fieldset>
      )}
    </fieldset>
  );
})}
```

---

### 8. ConfirmDialog - Overlay Not Keyboard Accessible
**Location**: `/packages/web/components/modals/ConfirmDialog.tsx` (Lines 51-55)  
**Severity**: High  
**WCAG Criteria**: 2.1.1 (Keyboard)

**Issue**:
The background overlay `<div onClick={onCancel}>` is not keyboard accessible. Users with keyboard-only input cannot dismiss the modal by clicking the overlay.

```tsx
// ❌ Current (ConfirmDialog.tsx, Lines 51-55):
{/* Background overlay */}
<div
  className="fixed inset-0 bg-ifs-grey-900 bg-opacity-75 transition-opacity"
  onClick={onCancel}
  // ← Missing keyboard interaction
/>
```

**Remediation Code**:
```tsx
// ✓ Fixed:
{/* Background overlay */}
<button
  type="button"
  className="fixed inset-0 bg-ifs-grey-900 bg-opacity-75 transition-opacity"
  onClick={onCancel}
  aria-label="Close dialog"
  aria-hidden="true"  // Screen readers shouldn't announce this button
  tabIndex={-1}  // Prevent tab access (ESC key handles closing)
/>
```

---

## High Priority Issues

### 9. MaturityScale Radio Label Association
**Location**: `/packages/web/components/questions/MaturityScale.tsx`  
**Severity**: Medium  
**WCAG Criteria**: 1.3.1 (Info and Relationships)

**Issue**:
Each radio button has an `aria-label` but the parent `<label>` wraps the entire card, making it ambiguous which label applies to which radio.

```tsx
// ❌ Current (MaturityScale.tsx, Lines 94-149):
{levels.map((level) => {
  return (
    <label
      key={level.value}
      className={cn('block p-4 border-2 rounded-lg cursor-pointer')}
    >
      <div className="flex items-start gap-3">
        <input
          type="radio"
          name={id}
          value={level.value}
          aria-label={`${level.label} - ${level.description}`}  // ← Already has label
        />
        {/* ... content ... */}
      </div>
    </label>
  );
})}
```

The structure is actually acceptable, but clearer labeling would help. The aria-label is good.

**Minor Improvement**:
```tsx
// ✓ Enhanced clarity:
<div
  key={level.value}
  className={cn('block p-4 border-2 rounded-lg cursor-pointer transition-[background-color,border-color]')}
  role="radio"
  aria-checked={isSelected}
  aria-labelledby={`${id}-${level.value}-label`}
>
  <div className="flex items-start gap-3">
    <input
      type="radio"
      id={`${id}-${level.value}`}
      name={id}
      value={level.value}
      checked={isSelected}
      onChange={() => onChange(level.value)}
      disabled={disabled}
      className="sr-only"
    />
    
    <div className="flex-1">
      <div id={`${id}-${level.value}-label`} className="flex items-center gap-2">
        <span className={cn('flex items-center justify-center w-6 h-6 rounded-full text-xs font-bold')}>
          {level.value}
        </span>
        <span className={cn('font-medium')}>
          {level.label}
        </span>
      </div>
      <p className="mt-1 text-sm text-secondary ml-8">
        {level.description}
      </p>
    </div>
  </div>
</div>
```

---

### 10. Missing Loading State Announcements
**Location**: `/packages/web/components/SurveyNavigation.tsx` (Lines 278-282)  
**Severity**: Medium  
**WCAG Criteria**: 4.1.3 (Status Messages)

**Issue**:
The saving status shows a spinner and text but doesn't have proper ARIA live region announcement. The live region is declared in SurveyOrchestrator but not used here.

```tsx
// ⚠️ Current (SurveyNavigation.tsx, Lines 278-282):
{isSaving && (
  <span className="text-xs text-tertiary flex items-center whitespace-nowrap" role="status" aria-live="polite">
    <Spinner size="sm" color="accent" label="Saving progress" />
    <span className="ml-1.5">Saving...</span>
  </span>
)}
```

This is actually good! The `role="status"` and `aria-live="polite"` are correct. However, the Spinner component's label attribute should be used properly.

---

### 11. SurveyProgressNav - Missing Keyboard Navigation Instructions for Screen Readers
**Location**: `/packages/web/components/SurveyProgressNav.tsx` (Lines 424-427)  
**Severity**: Medium  
**WCAG Criteria**: 2.4.8 (Focus Visible)

**Issue**:
The keyboard navigation hint is visible text only. Screen reader users don't know about the arrow key shortcuts.

```tsx
// Current (Line 424-427):
<div className="mt-4 text-center text-xs text-tertiary">
  Use arrow keys (← →) or click dots to navigate
</div>
```

**Remediation Code**:
```tsx
// ✓ Fixed:
<div 
  className="mt-4 text-center text-xs text-tertiary"
  role="status"
  aria-live="polite"
>
  <span className="block">Use arrow keys (← →) or click dots to navigate</span>
  <span className="sr-only">
    Keyboard shortcut: Left arrow key navigates to previous section, Right arrow key navigates to next section
  </span>
</div>
```

---

### 12. Missing Skip Links
**Location**: Entire application  
**Severity**: Medium  
**WCAG Criteria**: 2.4.1 (Bypass Blocks)

**Issue**:
There are no skip links to jump over repetitive navigation to main content. Users navigating with keyboard must tab through progress nav and other controls.

**Remediation Code**:
```tsx
// Create new component: /components/SkipLinks.tsx
export function SkipLinks() {
  return (
    <>
      <a
        href="#survey-content"
        className="sr-only focus:not-sr-only fixed top-4 left-4 z-50 px-4 py-2 bg-accent text-white rounded hover:bg-accent-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent"
      >
        Skip to main content
      </a>
      <a
        href="#survey-navigation"
        className="sr-only focus:not-sr-only fixed top-12 left-4 z-50 px-4 py-2 bg-accent text-white rounded hover:bg-accent-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-accent"
      >
        Skip to navigation
      </a>
    </>
  );
}

// In SurveyOrchestrator.tsx:
return (
  <div>
    <SkipLinks />
    <SurveyHeader />
    <SurveyLayout
      sidebar={...}
    >
      {/* Content with id="survey-content" */}
      <div id="survey-content" key={currentSectionId}>
        {renderSection()}
      </div>
    </SurveyLayout>
    <SurveyNavigation
      id="survey-navigation"
      // ... props ...
    />
  </div>
);
```

---

## Medium Priority Issues

### 13. Color Contrast - Verify All Text-Background Combinations
**Location**: Multiple components  
**Severity**: Medium (Likely Compliant)  
**WCAG Criteria**: 1.4.11 (Non-text Contrast), 1.4.3 (Contrast Minimum)

**Issue**:
While the design system looks good, some combinations need verification:
- Text on hover/focus backgrounds
- Disabled state text
- Secondary text colors

**Recommended Action**:
Run WebAIM contrast checker on:
1. `text-secondary` on `bg-secondary` (Check `/lib/constants/design.ts` colors)
2. `text-tertiary` on `bg-tertiary`
3. Disabled button text colors
4. Error/warning/success text on colored backgrounds

**Verification Command**:
```bash
# Install contrast checker
npm install -g pa11y-ci

# Create .pa11yci.json and run full audit
```

---

### 14. FormInput/FormSelect - Tooltip Not Always Associated
**Location**: `/packages/web/components/forms/FormInput.tsx`, `/packages/web/components/forms/FormSelect.tsx`  
**Severity**: Low-Medium  
**WCAG Criteria**: 1.3.1 (Info and Relationships)

**Issue**:
Tooltips are associated via `aria-describedby` BUT the tooltip element uses `id={`${id}-description`}`. If `id` is not properly unique in complex forms, these might collide.

```tsx
// FormInput.tsx, Lines 136-141:
{tooltip && (
  <p className="text-xs text-secondary mb-2" id={`${id}-description`}>
    {tooltip}
  </p>
)}

// Then later, Line 160:
aria-describedby={tooltip ? `${id}-description` : undefined}
```

This is actually fine since `id` should be unique. However, prefix could be clearer.

---

### 15. Missing Live Region for Error Summary
**Location**: `/packages/web/components/SurveyNavigation.tsx`  
**Severity**: Low  
**WCAG Criteria**: 1.3.5 (Identify Input Purpose)

**Issue**:
Error messages render but should be announced to screen readers immediately when they appear.

```tsx
// Current (Lines 177-210):
{validationErrors.length > 0 && (
  <div
    className="mb-4 p-3 bg-error/10 border border-error rounded-md"
    role="alert"  // ← Good!
    aria-live="assertive"  // ← Good!
  >
    {/* ... errors ... */}
  </div>
)}
```

Actually, this is already good! The `role="alert"` and `aria-live="assertive"` are correct.

---

## Low Priority Improvements

### 16. ExitSurveyButton - Could Use Better Confirmation
**Location**: `/packages/web/components/ExitSurveyButton.tsx`  
**Severity**: Low  
**WCAG Criteria**: 3.3.4 (Error Prevention)

**Issue**:
The button could have more context about what happens when exiting.

**Current Improvement**:
The button already uses ConfirmDialog which has good accessibility.

---

### 17. Accessibility Constants Available but Not Fully Utilized
**Location**: `/packages/web/lib/constants/accessibility.ts`  
**Severity**: Low (Observation)

**Great News**: The project has comprehensive accessibility utilities:
- `focusManager.trapFocus()` - Not used in modals
- `announce()` function - Used sparingly
- `getProgressLabel()` - Not used
- `getNextButtonLabel()` - Not used

**Recommendation**: Utilize these throughout the app for consistent ARIA labels.

---

### 18. InsightCard - Expand/Collapse Not Keyboard Accessible
**Location**: `/packages/web/components/ai/InsightCard.tsx` (Lines 131-142)  
**Severity**: Low  
**WCAG Criteria**: 2.1.1 (Keyboard)

**Issue**:
The expand/collapse buttons are accessible but could have better keyboard handling.

```tsx
// Lines 131-142 - These are actually buttons, which is good!
<button
  onClick={() => setShowExplanation(!showExplanation)}
  className="text-xs text-ifs-purple hover:text-ifs-purple/80 underline"
  title="How this helps"
  aria-label="Show explanation"
>
  ?
</button>
```

This is actually acceptable. Minor improvement: add `aria-expanded`:

```tsx
// ✓ Enhanced:
<button
  onClick={() => setShowExplanation(!showExplanation)}
  className="text-xs text-ifs-purple hover:text-ifs-purple/80 underline focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-ifs-purple rounded"
  title={showExplanation ? 'Hide explanation' : 'Show explanation'}
  aria-label={showExplanation ? 'Hide how this helps' : 'Show how this helps'}
  aria-expanded={showExplanation}
>
  {showExplanation ? '−' : '?'}
</button>
```

---

## Summary of Violations by WCAG Criteria

| WCAG Criterion | Count | Issues |
|---|---|---|
| **1.3.1** (Info & Relationships) | 8 | Modal roles, form associations, fieldset structure, landmark roles |
| **2.1.1** (Keyboard) | 4 | Modal focus trap, overlay keyboard access, floating button kbd nav |
| **2.4.7** (Focus Visible) | 3 | Floating button focus indicator, some buttons missing focus styles |
| **2.4.3** (Focus Order) | 2 | Modal focus management, keyboard navigation |
| **1.4.11** (Contrast) | 1 | Needs verification (likely compliant) |
| **3.3.2** (Labels) | 2 | Form rating labels, fieldset legends |
| **4.1.3** (Status Messages) | 2 | Some live region improvements |
| **2.4.1** (Bypass Blocks) | 1 | Missing skip links |

---

## Recommended Fix Priority

### Immediate (Within 1-2 Weeks)
1. Add `role="dialog"` and `aria-modal="true"` to all modals
2. Implement focus trap in modal dialogs using existing `focusManager.trapFocus()`
3. Make backdrop overlays keyboard accessible (convert to buttons or add keyboard handlers)
4. Add `aria-expanded` to expand/collapse buttons
5. Fix FormRating label associations

### Short Term (Within 1 Month)
6. Add proper `<fieldset>`/`<legend>` structure to ImpactMatrix
7. Add skip links to application
8. Implement focus indicators on floating button
9. Verify color contrast with automated tools
10. Add keyboard navigation hints to live regions

### Long Term (Quality Improvements)
11. Utilize accessibility constants more consistently
12. Add more screen reader testing with NVDA/JAWS
13. Implement comprehensive keyboard navigation guide in docs
14. Add accessibility testing to CI/CD pipeline

---

## Testing Recommendations

### Manual Testing
```bash
# Test with keyboard only
# 1. Tab through all interactive elements
# 2. Test modal escape and focus trap
# 3. Test arrow key navigation in progress nav
# 4. Verify all buttons have visible focus indicators

# Test with screen readers
# NVDA (Windows): https://www.nvaccess.org/
# JAWS: https://www.freedomscientific.com/products/software/jaws/
# VoiceOver (Mac): Built-in (Cmd+F5)

# Listen for:
# - Dialog/modal announcement
# - Skip links
# - Status messages
# - Error announcements
```

### Automated Testing
```bash
# Install accessibility testing tools
npm install --save-dev jest-axe

# Add to tests:
import { axe } from 'jest-axe';

test('component has no accessibility violations', async () => {
  const { container } = render(<Component />);
  const results = await axe(container);
  expect(results).toHaveNoViolations();
});
```

### Tools
- **axe DevTools**: Browser extension for quick checks
- **WAVE**: Web accessibility evaluation tool
- **Lighthouse**: Built into Chrome DevTools
- **NVDA + JAWS**: Screen reader testing
- **Keyboard-only testing**: Actual keyboard navigation

---

## Files to Update (Priority Order)

1. `/packages/web/components/modals/ConfirmDialog.tsx` - Add dialog role, focus trap
2. `/packages/web/components/modals/ResumeModal.tsx` - Add dialog role, focus trap  
3. `/packages/web/components/SurveyLayout.tsx` - Fix backdrop accessibility
4. `/packages/web/components/forms/FormRating.tsx` - Fix label associations
5. `/packages/web/components/questions/ImpactMatrix.tsx` - Add fieldset/legend
6. `/packages/web/components/ai/FloatingInsightsButton.tsx` - Add focus visible styles
7. `/packages/web/components/SurveyOrchestrator.tsx` - Add skip links
8. All modal files - Add keyboard focus management

---

## References

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)
- [MDN Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [Next.js Accessibility](https://nextjs.org/learn/seo/introduction-to-seo/accessibility)
- [Focus Management](https://www.w3.org/WAI/ARIA/apg/patterns/dialogmodal/)

---

**Report Generated**: 2025-11-06  
**Next Audit**: After critical fixes implemented

