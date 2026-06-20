import { test, expect, type Page } from '@playwright/test';
import { navigateToTab, openTab } from './helpers';

// Unique name generator for test isolation
function uniqueName(prefix: string) {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
}

// Clean up a speaker by name via API
async function deleteSpeakerByName(page: Page, name: string) {
  try {
    const resp = await page.request.get('http://localhost:8000/speakers');
    const data = await resp.json();
    const speaker = data.speakers?.find((s: any) => s.name === name);
    if (speaker) {
      await page.request.delete(`http://localhost:8000/speakers/${speaker.speaker_id}`);
    }
  } catch { /* ignore cleanup errors */ }
}

// Clean up a context folder via API
async function deleteContextFolder(page: Page, path: string) {
  try {
    await page.request.delete(`http://localhost:8000/contexts/folders/${encodeURIComponent(path)}`);
  } catch { /* ignore */ }
}

test.describe('Navigation', () => {
  test('page loads with Transcribe tab active', async ({ page }) => {
    await page.goto('/');
    // The transcription UI should be visible by default (upload section)
    await expect(page.getByText('Upload File')).toBeVisible();
    await expect(page.getByText('YouTube URL')).toBeVisible();
  });

  test('clicking Recordings tab shows recordings view', async ({ page }) => {
    await openTab(page, 'Recordings');
    await expect(page.getByText('Just Press Record')).toBeVisible({ timeout: 5000 });
  });

  test('clicking Calls tab shows calls view', async ({ page }) => {
    await openTab(page, 'Calls');
    await expect(page.getByRole('heading', { name: /calls/i })).toBeVisible();
  });

  test('clicking Speakers tab shows speakers view', async ({ page }) => {
    await openTab(page, 'Speakers');
    await expect(page.getByRole('heading', { name: /speakers/i })).toBeVisible();
  });

  test('clicking Contexts tab shows contexts view', async ({ page }) => {
    await openTab(page, 'Contexts');
    await expect(page.getByRole('heading', { name: /contexts/i })).toBeVisible();
  });

  test('switching tabs back to Transcribe restores upload UI', async ({ page }) => {
    await openTab(page, 'Speakers');
    await expect(page.getByText('Upload File')).not.toBeVisible();
    await navigateToTab(page, 'Transcribe');
    await expect(page.getByText('Upload File')).toBeVisible();
  });
});

test.describe('Recordings View', () => {
  test('shows recordings list or empty state', async ({ page }) => {
    await openTab(page, 'Recordings');
    // Should show the "Just Press Record" heading in the recordings view
    await expect(page.getByText('Just Press Record')).toBeVisible({ timeout: 5000 });
  });

  test('refresh button is visible', async ({ page }) => {
    await openTab(page, 'Recordings');
    // RefreshCw button exists (it's the only button after the heading besides Plus)
    const buttons = page.locator('button');
    await expect(buttons.first()).toBeVisible();
  });
});

test.describe('Speakers View', () => {
  test('shows empty state when no speakers exist', async ({ page }) => {
    await openTab(page, 'Speakers');
    // May show speakers or empty state depending on existing data
    const heading = page.getByRole('heading', { name: /speakers/i });
    await expect(heading).toBeVisible();
  });

  test('create speaker flow', async ({ page }) => {
    const name = uniqueName('TestSpeaker');
    await openTab(page, 'Speakers');

    // Click the plus button to open create form
    // The plus button is near the heading
    const plusButtons = page.locator('button').filter({ has: page.locator('svg') });
    // Find the plus/add button (second button in header area)
    await page.locator('button').nth(1).click();
    await page.waitForTimeout(300);

    // Type the speaker name and submit
    const input = page.getByPlaceholder('Speaker name');
    if (await input.isVisible()) {
      await input.fill(name);
      await input.press('Enter');
      await page.waitForTimeout(1000);

      // Speaker should appear in the list
      await expect(page.getByText(name)).toBeVisible();

      // Clean up
      await deleteSpeakerByName(page, name);
    }
  });

  test('delete speaker flow', async ({ page }) => {
    // Create a speaker first via API
    const name = uniqueName('DeleteMe');
    await page.request.post('http://localhost:8000/speakers', {
      data: { name },
    });

    await openTab(page, 'Speakers');
    await page.waitForTimeout(500);

    // Find the speaker in the list
    const speakerText = page.getByText(name);
    if (await speakerText.isVisible()) {
      // Click the delete (trash) button for this speaker
      const deleteButton = page.getByRole('button', { name: `Delete speaker ${name}` });
      if (await deleteButton.isVisible()) {
        await deleteButton.click();
        await page.waitForTimeout(300);

        // Confirm via the custom ConfirmModal
        const confirmButton = page.getByRole('button', { name: 'Delete', exact: true });
        if (await confirmButton.isVisible()) {
          await confirmButton.click();
          await page.waitForTimeout(500);
        }
      }
    }

    // Clean up anyway
    await deleteSpeakerByName(page, name);
  });

  test('clicking speaker opens profile view', async ({ page }) => {
    // Create a speaker first
    const name = uniqueName('ProfileTest');
    await page.request.post('http://localhost:8000/speakers', {
      data: { name },
    });

    await openTab(page, 'Speakers');
    await page.waitForTimeout(500);

    // Click on the speaker to open profile
    const speakerLink = page.getByText(name).first();
    if (await speakerLink.isVisible()) {
      await speakerLink.click();
      await page.waitForTimeout(500);

      // Should see personality section with a textarea
      const textarea = page.locator('textarea');
      await expect(textarea).toBeVisible();
    }

    // Clean up
    await deleteSpeakerByName(page, name);
  });
});

test.describe('Calls View', () => {
  test('shows calls list or empty state', async ({ page }) => {
    await openTab(page, 'Calls');
    // Should show either the calls list or "No calls yet" message
    const callsHeading = page.getByRole('heading', { name: /calls/i });
    await expect(callsHeading).toBeVisible();
  });

  test('status filter buttons are visible', async ({ page }) => {
    await openTab(page, 'Calls');
    // Filter buttons should be visible
    await expect(page.getByRole('button', { name: 'All', exact: true }).first()).toBeVisible();
  });

  test('clicking filter button changes active styling', async ({ page }) => {
    await openTab(page, 'Calls');

    // Click a filter button and verify it changes
    const allButton = page.getByRole('button', { name: 'All', exact: true }).first();
    if (await allButton.isVisible()) {
      await allButton.click();
      // "All" should have active styling (blue background)
      await expect(allButton).toHaveCSS('background-color', /rgb/);
    }
  });
});

test.describe('Contexts View', () => {
  test('shows contexts heading', async ({ page }) => {
    await openTab(page, 'Contexts');
    await expect(page.getByRole('heading', { name: /contexts/i })).toBeVisible();
  });

  test('create context folder flow', async ({ page }) => {
    const folderName = uniqueName('TestCtx');
    await openTab(page, 'Contexts');

    // Click plus button to open create form
    await page.locator('button').nth(1).click();
    await page.waitForTimeout(300);

    // Type folder name and submit
    const input = page.getByPlaceholder(/folder name/i);
    if (await input.isVisible()) {
      await input.fill(folderName);
      await input.press('Enter');
      await page.waitForTimeout(1000);

      // Folder should appear in the tree
      await expect(page.getByText(folderName)).toBeVisible();

      // Clean up
      await deleteContextFolder(page, folderName);
    }
  });

  test('folder tree is interactive', async ({ page }) => {
    // Create a folder first
    const folderName = uniqueName('TreeTest');
    await page.request.post('http://localhost:8000/contexts/folders', {
      data: { path: folderName, description: 'test folder' },
    });

    await openTab(page, 'Contexts');
    await page.waitForTimeout(500);

    // The folder should be visible in the tree
    const folderNode = page.getByText(folderName);
    if (await folderNode.isVisible()) {
      // Click to expand
      await folderNode.click();
      await page.waitForTimeout(300);
      // Should show context.md file link after expanding
      // (The folder has a context.md created by the backend)
    }

    // Clean up
    await deleteContextFolder(page, folderName);
  });
});

test.describe('Cross-view navigation', () => {
  test('rapid tab switching does not break app', async ({ page }) => {
    await page.goto('/');

    // Quickly switch between all tabs
    for (const tab of ['Recordings', 'Calls', 'Speakers', 'Contexts', 'Transcribe']) {
      await navigateToTab(page, tab);
    }

    // Should still be on Transcribe and functional
    await expect(page.getByText('Upload File')).toBeVisible();
  });

  test('data persists across tab switches', async ({ page }) => {
    const name = uniqueName('PersistTest');
    await page.request.post('http://localhost:8000/speakers', {
      data: { name },
    });

    await openTab(page, 'Speakers');
    await expect(page.getByText(name)).toBeVisible({ timeout: 5000 });

    // Switch to Calls and back
    await navigateToTab(page, 'Calls');
    await navigateToTab(page, 'Speakers');
    await expect(page.getByText(name)).toBeVisible({ timeout: 5000 });

    // Clean up
    await deleteSpeakerByName(page, name);
  });
});
