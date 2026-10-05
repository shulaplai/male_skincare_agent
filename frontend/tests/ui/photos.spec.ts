import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * 皮膚相**一定要先模糊**——唔係 snapshot 可以代替嘅 gate。
 *
 * 為咩要獨立寫一個 spec，而唔係靠 `snapshots.spec.ts`：
 * 2026-10-01 加咗 `BlurPhoto` 之後，`RecordsView`／`MobileHome`／`JournalHome` 三個
 * 地方一直係裸 `<img src="/api/photos/…">`（`JournalHome` 仲包住
 * `<a target="_blank">`，撳一下開原圖）。實測 3 個 scene 共 **42 張相、0 張有模糊**
 * （`getComputedStyle(img).filter === 'none'`），但 **51 個 snapshot 全綠** ——
 * 因為 fixture 嗰張假相係低對比漸變，`blur(15px)` 只改到平均 3.2/255，低過
 * Playwright 嘅像素門檻。即係：
 *
 *   ⚠️ 「有 snapshot」唔等於「量到你改嘅嘢」。相冇模糊係**語義**問題
 *      （邊個睇得到用戶嘅自拍），要用斷言講，唔係用像素差。
 *
 * fixture 相已經換成 8px 棋盤格（模糊影響 79/255），所以 snapshot 亦開始捉得到；
 * 但呢個 spec 仍然係主要嘅網：佢直接講出要求。
 */
const PHOTO_SCENES = [
  { layout: 'mobile', scene: 'home', what: '「今日」tab（手機一開就見到）' },
  { layout: 'mobile', scene: 'records', what: '「記錄」tab' },
  { layout: 'journal', scene: 'home', what: '日記 feed' },
] as const

const PHOTO_SELECTOR = 'img[src*="/api/photos/"]'

for (const { layout, scene, what } of PHOTO_SCENES) {
  test(`${what}：每張皮膚相都要模糊，而且唔可以用 <a> 開原圖`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await installFixtures(page)
    await page.goto(`?layout=${layout}&scene=${scene}`)
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const imgs = page.locator(PHOTO_SELECTOR)
    const count = await imgs.count()
    expect(count, 'fixture 應該有相，否則呢個 spec 冇量到嘢').toBeGreaterThan(0)

    const state = await page.evaluate(
      (sel) =>
        [...document.querySelectorAll(sel)].map((el) => {
          const wrap = el.closest('.photo')
          return {
            hasPhotoWrapper: !!wrap,
            blurred: !!wrap && wrap.classList.contains('blurred'),
            shown: !!wrap && wrap.classList.contains('shown'),
            filter: getComputedStyle(el).filter,
            insideAnchor: !!el.closest('a'),
          }
        }),
      PHOTO_SELECTOR,
    )

    expect(state.filter((s) => !s.hasPhotoWrapper), '有相冇經 BlurPhoto').toEqual([])
    expect(state.filter((s) => s.shown), '一開始就唔應該係「已顯示」狀態').toEqual([])
    expect(state.filter((s) => !s.blurred), '有相冇 blurred class').toEqual([])
    expect(
      state.every((s) => s.filter.includes('blur')),
      `filter 要真係有 blur，實際：${JSON.stringify(state.map((s) => s.filter))}`,
    ).toBe(true)
    expect(
      state.filter((s) => s.insideAnchor),
      '相唔可以包喺 <a> 度（撳一下會喺新 tab 開原圖，繞過模糊）',
    ).toEqual([])

    // 撳「顯示」之後一定要變清（唔係永遠模糊 = 遮住功能）
    await page.locator('.photo .reveal').first().click()
    await page.waitForTimeout(300)
    const after = await page.evaluate(
      (sel) => {
        const el = document.querySelector(sel)!
        return {
          shown: !!el.closest('.photo')?.classList.contains('shown'),
          filter: getComputedStyle(el).filter,
        }
      },
      PHOTO_SELECTOR,
    )
    expect(after.shown).toBe(true)
    expect(after.filter.includes('blur')).toBe(false)
  })
}

test('對話入面嘅相亦要模糊（唔可以只得 chat 有做）', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installFixtures(page)
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)

  const imgs = page.locator(PHOTO_SELECTOR)
  expect(await imgs.count()).toBeGreaterThan(0)
  const bad = await page.evaluate(
    (sel) =>
      [...document.querySelectorAll(sel)]
        .filter((el) => {
          const w = el.closest('.photo')
          return !w || !w.classList.contains('blurred') || !getComputedStyle(el).filter.includes('blur')
        })
        .map((el) => el.getAttribute('src')),
    PHOTO_SELECTOR,
  )
  expect(bad).toEqual([])
})
