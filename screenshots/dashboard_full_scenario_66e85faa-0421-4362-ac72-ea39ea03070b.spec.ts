
import { test } from '@playwright/test';
import { expect } from '@playwright/test';

test('dashboard_full_scenario_2025-06-24', async ({ page, context }) => {
  
    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Take screenshot
    await page.screenshot({ path: 'dashboard_home_page.png', { fullPage: true } });

    // Click element
    await page.click('[data-testid="baseButton-secondary"]:has-text("💰 수익화 가능 후보")');

    // Click element
    await page.click('button:has-text("💰 수익화 가능 후보")');

    // Take screenshot
    await page.screenshot({ path: 'monetizable_candidates_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("🔍 수익화 필터링 목록")');

    // Take screenshot
    await page.screenshot({ path: 'filtered_products_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("🤖 AI 콘텐츠 생성")');

    // Take screenshot
    await page.screenshot({ path: 'ai_content_generator_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("💰 API 사용량 추적")');

    // Take screenshot
    await page.screenshot({ path: 'api_usage_tracking_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("💸 예산 관리")');

    // Take screenshot
    await page.screenshot({ path: 'budget_management_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("📹 영상 분석")');

    // Take screenshot
    await page.screenshot({ path: 'video_analysis_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("📈 통계 및 리포트")');

    // Take screenshot
    await page.screenshot({ path: 'statistics_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("⚙️ 시스템 설정")');

    // Take screenshot
    await page.screenshot({ path: 'settings_page.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("🏠 홈")');

    // Click element
    await page.click('button:has-text("🔍 새 영상 분석 시작")');

    // Take screenshot
    await page.screenshot({ path: 'quick_action_video_analysis.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("📊 통계 리포트 생성")');

    // Click element
    await page.click('button:has-text("💾 데이터 백업")');

    // Click element
    await page.click('button:has-text("⚙️ 시스템 점검")');

    // Take screenshot
    await page.screenshot({ path: 'responsive_tablet_view.png', { fullPage: true } });

    // Take screenshot
    await page.screenshot({ path: 'responsive_mobile_view.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("🤖 AI 콘텐츠 생성")');

    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Click element
    await page.click('button:has-text("🤖 AI 콘텐츠 생성")');

    // Take screenshot
    await page.screenshot({ path: 'ai_content_generator_working.png', { fullPage: true } });

    // Click element
    await page.click('div[data-baseweb="tab-list"] button:nth-child(2)');

    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Click element
    await page.click('button:has-text("🤖 AI 콘텐츠 생성")');

    // Take screenshot
    await page.screenshot({ path: 'ai_content_generator_fixed.png', { fullPage: true } });

    // Fill input field
    await page.fill('input[aria-label="채널명"]', '홍지윤 Yoon');

    // Click element
    await page.click('a[href*="ai_content_generator_simple"]');

    // Take screenshot
    await page.screenshot({ path: 'ai_content_generator_simple_page.png', { fullPage: true } });

    // Fill input field
    await page.fill('input[data-testid="stTextInput"]', '홍지윤 Yoon');

    // Click element
    await page.click('button:has-text("🚀 AI 콘텐츠 생성")');

    // Take screenshot
    await page.screenshot({ path: 'ai_content_generation_result.png', { fullPage: true } });

    // Click element
    await page.click('button:has-text("아이유 - 틴트 립")');

    // Take screenshot
    await page.screenshot({ path: 'preset_button_test.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:8501/budget_management');

    // Take screenshot
    await page.screenshot({ path: 'budget_management_full_page.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:8501/api_usage_tracking');

    // Take screenshot
    await page.screenshot({ path: 'api_usage_tracking_full_page.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:8501/monetizable_candidates');

    // Take screenshot
    await page.screenshot({ path: 'monetizable_candidates_full_page.png', { fullPage: true } });

    // Navigate to URL
    await page.goto('http://localhost:8501');

    // Take screenshot
    await page.screenshot({ path: 'final_dashboard_test.png', { fullPage: true } });
});