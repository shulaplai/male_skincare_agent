import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * 主動問候唔會掛住一個空白「AI 分析」卡（2026-10-22 用戶要求）。
 *
 * 背景：`format.fromServerMessage` 以前**無條件**砌 `{title:'AI 分析', metrics: [],
 * advice: []}`，所以每一條問候（`payload.proactive`，只有一句話、冇 metrics／items）
 * 下面都出一個空白卡 —— 連「AI 分析」個標題都照出，睇落好似壞咗。
 *
 * 呢個 spec 同時釘住兩邊：有內容嘅回覆**仍然要**有卡（唔可以一刀切刪走），
 * 冇內容嘅就一個都沒有。反轉驗證：將 `buildAnalysis` 改返無條件回傳 → 第一條斷言紅。
 */
const PROACTIVE = {
  id: 1,
  role: 'coach' as const,
  text: '夜喇，收工未呀？今日皮膚點，有冇試新嘢搽？',
  payload: { proactive: 'evening', greeting: true },
  created_at: '2026-10-21T13:58:00',
}

const FULL = {
  id: 2,
  role: 'coach' as const,
  text: '下巴兩粒新瘡，先停新產品三日。',
  payload: {
    title: '下巴新瘡：先減刺激',
    reply: '下巴兩粒新瘡，先停新產品三日。',
    metrics: [{ key: '暗瘡', value: 2, dir: 'up' as const, note: '下巴兩粒' }],
    advice: ['停新產品 3 日'],
    vision_used: true,
  },
  created_at: '2026-10-21T14:10:00',
}

test('主動問候冇分析卡；有指標嘅回覆照樣有', async ({ page }) => {
  await installFixtures(page)
  await page.route('**/api/conversations/*/messages', (r) =>
    r.fulfill({ json: [PROACTIVE, FULL] }),
  )

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  const bubbles = page.locator('.thread .msg.coach')
  await expect(bubbles).toHaveCount(2)

  // 問候：有正文、冇卡、冇「AI 分析」字
  await expect(bubbles.nth(0)).toContainText('今日皮膚點')
  await expect(bubbles.nth(0).locator('.card')).toHaveCount(0)
  await expect(bubbles.nth(0)).not.toContainText('AI 分析')

  // 真回覆：卡仍然在（唔可以一刀切）
  await expect(bubbles.nth(1).locator('.card')).toHaveCount(1)
  await expect(bubbles.nth(1).locator('.card')).toContainText('AI 分析')
})
