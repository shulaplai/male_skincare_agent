import { defineConfig } from '@playwright/test'

/**
 * UI snapshot + a11y gate（Phase 0，2026-10-01 用戶批准）。
 *
 * 四個原則：
 * 1. **Deterministic**：所有 API 由 `tests/ui/fixtures.ts` 攔截，唔會讀開發機嘅真 data
 *    （所以 snapshot 唔會因為你傾多兩句就爆 diff，亦唔會 commit 到真嘅皮膚相）。
 * 2. **Vite 自己起**：`webServer` 用 5180 埠（唔會撞你手上嘅 :5173／:5174）。
 * 3. **單一 project**：viewport 由每個 test 自己 `setViewportSize` 決定。用三個 project
 *    會令 24 個 case 變 72 張 snapshot（~9MB），冇必要。
 * 4. **動畫停用**：`animations: 'disabled'`，唔係就會 flaky。
 */
export default defineConfig({
  testDir: './tests/ui',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 2 : undefined,
  reporter: process.env.CI ? [['github'], ['html', { open: 'never' }]] : [['list']],
  snapshotDir: './tests/ui/__screenshots__',
  expect: {
    toHaveScreenshot: {
      // 字型有 sub-pixel 差異；0.2% 像素容差可以食 anti-aliasing，但位移會遠超呢個數
      maxDiffPixelRatio: 0.002,
      animations: 'disabled',
      caret: 'hide',
    },
  },
  use: {
    baseURL: 'http://127.0.0.1:5180',
    locale: 'zh-HK',
    timezoneId: 'Asia/Hong_Kong',
    deviceScaleFactor: 2,
    launchOptions: { args: ['--force-color-profile=srgb', '--font-render-hinting=none'] },
  },
  webServer: {
    command: 'npx vite --port 5180 --strictPort',
    url: 'http://127.0.0.1:5180',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
