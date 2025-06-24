
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('RSS_Automation_Test_2025-06-24', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_dashboard_initial_load.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_dashboard_loaded.png', { fullPage: true } });

    // Click element
    await page.click('text=🔄 RSS 자동 수집');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_auto_collection_tab.png', { fullPage: true } });

    // Click element
    await page.click('text=🔍 필터링 관리');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_filtering_management_tab.png', { fullPage: true } });

    // Fill input field
    await page.fill('input[aria-label="테스트할 영상 제목"]', '아이유가 추천하는 립스틱 리뷰');

    // Click element
    await page.click('div[data-testid="stSelectbox"] >> text="personal"');

    // Click element
    await page.click('text="media"');

    // Click element
    await page.click('button[title="🧪 필터링 테스트"]');

    // Click element
    await page.click('text=🧪 필터링 테스트');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_filtering_test_result.png', { fullPage: true } });

    // Fill input field
    await page.fill('input[aria-label="테스트할 영상 제목"]', '60초 메이크업 챌린지 #shorts');

    // Click element
    await page.click('text=🧪 필터링 테스트');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_shorts_filtering_test.png', { fullPage: true } });

    // Click element
    await page.click('text=⏰ 과거 영상 수집');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_historical_collection_tab.png', { fullPage: true } });

    // Click element
    await page.click('text=📊 Google Sheets 연동');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_google_sheets_tab.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://127.0.0.1:8002/docs');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_api_documentation.png', { fullPage: true } });

    // Click element
    await page.click('text=Test Content Filter');

    // Click element
    await page.click('text=Try it out');

    // Fill input field
    await page.fill('textarea', '{"title": "아이유가 추천하는 립스틱 리뷰", "description": "인기 연예인 아이유가 직접 사용해본 립스틱을 추천합니다", "channel_type": "media"}');

    // Click element
    await page.click('text=Execute');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_api_filter_test_result.png', { fullPage: true } });

    // Click element
    await page.click('text=Health Check');

    // Click element
    await page.click('text=Try it out');

    // Click element
    await page.click('text=Execute');

    // Take screenshot
    await page.screenshot({ path: 'rss_automation_api_health_check_result.png', { fullPage: true } });
});