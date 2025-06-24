
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('n8n_second_workflow_2025-06-24', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Click element
    await page.click('button:has-text("Create Workflow")');

    // Click element
    await page.click('[data-test-id*="menu"]');

    // Click element
    await page.click('text=Import from File...');

    // Take screenshot
    await page.screenshot({ path: 'notification_workflow_imported.png', { fullPage: true } });

    // Take screenshot
    await page.screenshot({ path: 'ctrl_i_pressed.png' });

    // Take screenshot
    await page.screenshot({ path: 'after_paste.png', { fullPage: true } });

    // Click element
    await page.click('text=Add first step...');

    // Click element
    await page.click('[data-test-id*="add"] button');

    // Take screenshot
    await page.screenshot({ path: 'node_selector.png' });

    // Click element
    await page.click('text=Workflow');
});