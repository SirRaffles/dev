import { test, expect } from '@playwright/test';

test.skip('refinement badge appears post-completion when auto_refine is set', async ({ page }) => {
  // TODO: when App exposes a job-deep-link, mock /job/{id} responses and
  // assert the badge transitions: hidden → "Refining…" → "Refined".
  // For now, manual validation in Plan 3 Task 9 covers this surface.
  await page.goto('/');
  await expect(page.getByText(/Refining…|Refined/)).toBeVisible({ timeout: 10_000 });
});
