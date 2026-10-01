import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * 視覺回歸。加新 scene／新 shell 一定要加 case（漏咗就等於冇網）。
 * 改 UI 之後如果 diff 係**預期之內**：`npm run ui:update`，並且喺 commit message 講明點解。
 *
 * ⚠️ 呢個 spec 唔會打真後端：`installFixtures()` 攔截所有 API。
 */
const MOBILE = { width: 390, height: 844 }
const DESKTOP = { width: 1280, height: 900 }
const LAYOUTS = ['chat', 'journal', 'dash', 'mobile'] as const
const SCENES = ['home', 'chat', 'records', 'progress', 'settings', 'guide'] as const

async function settle(page: import('@playwright/test').Page, query: string) {
  await page.goto(query)
  await page.waitForLoadState('networkidle')
  // Webfont 載入完先影：`font-display: swap` 會令文字高度變，影早咗就 flaky（實測 3% 像素差）
  await page.evaluate(() => document.fonts?.ready)
  await page.waitForTimeout(400) // 入場動畫收尾（animations 已 disabled，穩陣起見）
}

test.describe('手機 390×844', () => {
  test.use({ viewport: MOBILE })
  for (const layout of LAYOUTS) {
    for (const scene of SCENES) {
      test(`${layout} · ${scene}`, async ({ page }) => {
        await installFixtures(page)
        // chat 結構冇 scene tabs（左欄係 site nav）
        const query = layout === 'chat' ? '?layout=chat' : `?layout=${layout}&scene=${scene}`
        await settle(page, query)
        await expect(page).toHaveScreenshot(`390-${layout}-${scene}.png`)
      })
    }
  }
})

test.describe('桌面 1280×900', () => {
  test.use({ viewport: DESKTOP })
  for (const layout of LAYOUTS) {
    test(`${layout} 首屏`, async ({ page }) => {
      await installFixtures(page)
      await settle(page, `?layout=${layout}`)
      await expect(page).toHaveScreenshot(`1280-${layout}.png`)
    })
  }
})

test('手機：長 thread 捲到底，輸入框要仲喺畫面（P1-4 回歸網）', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize(MOBILE)
  await settle(page, '?layout=mobile&scene=chat')
  const box = await page.locator('.compose').boundingBox()
  expect(box, '.compose 一定要存在').not.toBeNull()
  expect(box!.y + box!.height).toBeLessThanOrEqual(MOBILE.height + 1)
  await expect(page).toHaveScreenshot('390-mobile-chat-scrolled.png')
})

test('760/761 斷點（resolveLayout 嘅唯一真源）', async ({ page }) => {
  await installFixtures(page)
  for (const width of [760, 761]) {
    await page.setViewportSize({ width, height: 900 })
    await settle(page, '?scene=chat')
    const layout = await page.locator('.app').getAttribute('class')
    // 760 一定要 mobile、761 一定要唔係（`index.css` 同 `defs.ts` 兩邊要一致）
    expect(layout, `寬 ${width}`).toContain(width === 760 ? 'layout-mobile' : 'layout-chat')
    await expect(page).toHaveScreenshot(`breakpoint-${width}.png`)
  }
})

test('影片上載中：見到條片＋進度，唔會漏出「抽格」字眼', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize(MOBILE)
  // 慢上載：睇得到 uploading 狀態
  await page.route('**/api/videos*', async (r) => {
    await new Promise((res) => setTimeout(res, 1500))
    await r.fulfill({
      json: {
        video_id: 'a'.repeat(32), path: 'a'.repeat(32), duration: 12.4, fps: 30, width: 1080, height: 1920,
        sampled: 6, dropped: 3, timestamps: [1, 2, 3, 4, 5, 6],
        frames: Array.from({ length: 6 }, (_, i) => ({ id: String(i + 1).repeat(32), path: `photos/${i}` })),
        compressed: true, compress_error: null, original_bytes: 62_000_000, stored_bytes: 5_000_000,
      },
    })
  })
  await settle(page, '?layout=mobile&scene=chat')
  await page.setInputFiles('input[type=file]', 'tests/ui/assets/clip.mp4')
  await page.waitForTimeout(300)
  const compose = (await page.locator('.compose').innerText()).replace(/\s+/g, ' ')
  expect(compose).not.toMatch(/抽|張相|格數|壓縮|MB/) // 唔可以 leak 內部實作
  await expect(page.locator('.clip-chip.uploading')).toBeVisible()
  await expect(page).toHaveScreenshot('390-clip-uploading.png')
  await page.waitForTimeout(1800)
  await expect(page.locator('.attach')).toHaveCount(0) // 唔會逐格出縮圖
  await expect(page).toHaveScreenshot('390-clip-ready.png')
})

test('暗色模式（手機）：全部 scene 都要有 snapshot', async ({ page }) => {
  await installFixtures(page)
  await page.addInitScript(() => localStorage.setItem('skc-theme', 'dark'))
  await page.setViewportSize(MOBILE)
  for (const scene of ['home', 'chat', 'records', 'progress', 'settings']) {
    await settle(page, `?layout=mobile&scene=${scene}`)
    await page.evaluate(() => localStorage.setItem('skc-theme', 'dark'))
    await expect(page).toHaveScreenshot(`390-dark-${scene}.png`)
  }
})

test('橫向（844×390）：唔會爆版、輸入框仍然喺畫面', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize({ width: 844, height: 390 })
  await settle(page, '?layout=mobile&scene=chat')
  const box = await page.locator('.compose').boundingBox()
  expect(box, '.compose 一定要存在').not.toBeNull()
  expect(box!.y + box!.height).toBeLessThanOrEqual(390 + 1)
  const scrollW = await page.evaluate(() => document.scrollingElement.scrollWidth)
  expect(scrollW).toBeLessThanOrEqual(845) // 唔可以有橫向溢出
  await expect(page).toHaveScreenshot('844x390-landscape-chat.png')
})

test('平板（768×1024）：mobile 結構 + chat 都要正常', async ({ page }) => {
  await installFixtures(page)
  await page.setViewportSize({ width: 768, height: 1024 })
  for (const scene of ['home', 'chat']) {
    await settle(page, `?layout=mobile&scene=${scene}`)
    await expect(page).toHaveScreenshot(`768-tablet-${scene}.png`)
  }
})
