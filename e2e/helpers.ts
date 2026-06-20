import { expect, type Locator, type Page } from '@playwright/test';

// Nav tabs use role="tab" (ARIA tablist pattern).
export async function navigateToTab(page: Page, tabName: string) {
  await page.getByRole('tab', { name: tabName, exact: true }).click();
  // Wait for lazy-loaded content to appear.
  await page.waitForTimeout(800);
}

export async function openTab(page: Page, tabName: string) {
  await page.goto('/');
  await navigateToTab(page, tabName);
}

export async function openRecentTranscriptions(page: Page) {
  const historyToggle = page.getByRole('button', { name: /Recent Transcriptions/i });
  await expect(historyToggle).toBeVisible({ timeout: 5000 });
  await historyToggle.click();
  await page.waitForTimeout(800);
}

export async function findHistoryJobRow(
  page: Page,
  jobId: string,
  options: { timeout?: number } = {},
): Promise<Locator | null> {
  await openRecentTranscriptions(page);

  const jobRow = page.getByText(jobId.slice(0, 8), { exact: false });
  const isVisible = await jobRow.isVisible({ timeout: options.timeout ?? 3000 }).catch(() => false);
  return isVisible ? jobRow : null;
}

export async function openHistoryJobFromApp(page: Page, jobId: string): Promise<boolean> {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toBeVisible({ timeout: 10_000 });

  const jobRow = await findHistoryJobRow(page, jobId);
  if (!jobRow) {
    return false;
  }

  await jobRow.click();
  await page.waitForTimeout(1500);
  return true;
}
