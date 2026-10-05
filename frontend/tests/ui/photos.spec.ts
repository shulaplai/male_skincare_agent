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

// 對應 backend `app/photo.py` 嘅 `THUMB_WIDTHS`（兩邊改要一齊改）
const THUMB_WIDTHS = [96, 192, 200, 264, 296, 336]

test('螢幕上嘅相要用縮圖 URL，原檔淨係全螢幕先下載', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await installFixtures(page)
  await page.goto('?layout=journal&scene=home')
  await page.waitForLoadState('networkidle')
  await page.waitForTimeout(500)

  const srcs = await page.$$eval(PHOTO_SELECTOR, (els) =>
    els.map((el) => el.getAttribute('src') ?? ''),
  )
  expect(srcs.length, 'fixture 應該有相').toBeGreaterThan(0)

  // audit §7：手機首頁為咗 98×98 嘅格下載 605.9 KB（14 張原檔）。格仔用 2× 縮圖
  // 係一樣清，所以「有相冇 ?w=」就係嗰個 bug 返嚟。
  const missing = srcs.filter((s) => !/\?w=\d+$/.test(s))
  expect(missing, '有相冇用 ?w= 縮圖').toEqual([])
  const widths = [...new Set(srcs.map((s) => Number(s.split('?w=')[1])))]
  expect(
    widths.every((w) => THUMB_WIDTHS.includes(w)),
    `縮圖闊度唔喺 whitelist（後端會 400）：${widths.join(',')}`,
  ).toBe(true)

  // 反過來：全螢幕睇相一定要原檔，唔可以慳到用縮圖。
  await page.locator('.photo .reveal').first().click()
  await page.locator('.photo-open').first().click()
  const lightbox = page.locator('.lightbox img')
  await expect(lightbox).toBeVisible()
  expect(await lightbox.getAttribute('src')).not.toContain('?w=')
})
