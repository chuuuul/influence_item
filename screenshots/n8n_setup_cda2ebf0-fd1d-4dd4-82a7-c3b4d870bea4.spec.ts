
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('n8n_setup_2025-06-24', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Navigate to URL
    await page.goto('https://w4dynowndihynzdcafxnidvm.hooks.n8n.cloud');

    // Take screenshot
    await page.screenshot({ path: 'n8n_initial_page.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Navigate to URL
    await page.goto('http://localhost:5678');

    // Take screenshot
    await page.screenshot({ path: 'n8n_setup_page.png', { fullPage: true } });

    // Fill input field
    await page.fill('input[name="email"]', 'admin@influence-item.com');

    // Fill input field
    await page.fill('input[name="firstName"]', 'Admin');

    // Fill input field
    await page.fill('input[name="lastName"]', 'User');

    // Fill input field
    await page.fill('input[name="password"]', 'Password123!');

    // Take screenshot
    await page.screenshot({ path: 'n8n_form_filled.png' });

    // Click element
    await page.click('button[type="submit"]');

    // Click element
    await page.click('button:has-text("Next")');

    // Take screenshot
    await page.screenshot({ path: 'n8n_after_setup.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("Get started")');

    // Take screenshot
    await page.screenshot({ path: 'n8n_dashboard.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("Skip")');

    // Take screenshot
    await page.screenshot({ path: 'n8n_main_dashboard.png', { fullPage: true } });
});