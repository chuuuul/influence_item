
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('n8n_workflow_import_2025-06-24', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Click element
    await page.click('button:has-text("Create Workflow")');

    // Take screenshot
    await page.screenshot({ path: 'workflow_editor.png', { fullPage: true } });

    // Take screenshot
    await page.screenshot({ path: 'import_dialog.png' });

    // Click element
    await page.click('[data-test-id="main-header-workflows"]');

    // Click element
    await page.click('text=Workflows');

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Take screenshot
    await page.screenshot({ path: 'back_to_dashboard.png' });

    // Click element
    await page.click('button[aria-label*="menu"]');

    // Click element
    await page.click('button[data-testid*="dropdown"]');

    // Click element
    await page.click('button[aria-label="Close this dialog"]');

    // Take screenshot
    await page.screenshot({ path: 'after_escape.png' });

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Take screenshot
    await page.screenshot({ path: 'clean_dashboard.png' });

    // Click element
    await page.click('button:has-text('▼')');

    // Click element
    await page.click('button:has-text('Create Workflow')');

    // Take screenshot
    await page.screenshot({ path: 'workflow_editor_page.png', { fullPage: true } });

    // Take screenshot
    await page.screenshot({ path: 'import_dialog_open.png' });

    // Click element
    await page.click('button[aria-label*="menu"]');

    // Click element
    await page.click('button:has-text('⋯')');

    // Click element
    await page.click('[data-test-id*="menu"]');

    // Take screenshot
    await page.screenshot({ path: 'menu_opened.png' });

    // Click element
    await page.click('text=Import from File...');

    // Take screenshot
    await page.screenshot({ path: 'import_file_dialog.png' });

    // Click element
    await page.click('[data-test-id*="menu"]');

    // Click element
    await page.click('text=Import from URL...');

    // Take screenshot
    await page.screenshot({ path: 'import_url_dialog.png' });

    // Click element
    await page.click('button:has-text('Cancel')');

    // Take screenshot
    await page.screenshot({ path: 'file_input_visible.png' });

    // Take screenshot
    await page.screenshot({ path: 'workflow_imported.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text('Save')');

    // Take screenshot
    await page.screenshot({ path: 'workflow_saved.png' });

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Click element
    await page.click('button:has-text('Create Workflow')');

    // Click element
    await page.click('[data-test-id*="menu"]');

    // Click element
    await page.click('text=Import from File...');

    // Take screenshot
    await page.screenshot({ path: 'second_workflow_imported.png', { fullPage: true } });

    // Click element
    await page.click('[data-test-id*="menu"]');

    // Click element
    await page.click('text=Import from File...');

    // Take screenshot
    await page.screenshot({ path: 'notification_workflow_loaded.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Take screenshot
    await page.screenshot({ path: 'final_dashboard.png', { fullPage: true } });
});