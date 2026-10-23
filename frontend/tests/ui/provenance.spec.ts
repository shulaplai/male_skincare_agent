import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * 對話氣泡**唔會** leak 內部狀態（2026-10-20 產品決定）。
 *
 * 歷史：issue #14 曾經要求喺氣泡出兩個徽章 —— 「已睇相分析（雲端）／文字分析（未睇相）」
 * 同回覆出處（`FakeLLM · 測試模式` / `openai · gpt-4o-mini`）。當時嘅理由係誠實：
 * 用戶要知道自己有冇被睇相、係邊個模型答。用戶後來說「一體化分析（雲端或者佢用咗啲
 * 咩模型嗰啲），全部隱藏咗佢」—— 對話要保持乾淨，內部狀態唔應該出現在用戶面前。
 *
 * 呢個 spec 釘住「收埋」，而唔係「冇呢個資料」：
 * 1. 氣泡入面冇任何徽章，亦冇 provider／model／「雲端」字眼；
 * 2. 誠實性冇消失，只係搬咗位 —— `vision_used` 同 `provenance` 仍然喺 payload、
 *    `/api/consult` response 同 `data/runs.jsonl` trace 入面（後端 test 覆蓋），
 *    前端只係唔 render。
 *
 * payload 特意用「難睇嘅」形狀（`vision_used: null`、`vision_clip: true`、
 * `mode: 'fake'`）：如果邊日有人手痕加返徽章，呢兩個 case 會即刻紅。
 */
test('顧問氣泡唔會顯示雲端／模型／睇相狀態', async ({ page }) => {
  await installFixtures(page)
  // Registered AFTER the catch-all so it wins (Playwright matches last-first).
  await page.route('**/api/conversations/*/messages', (r) =>
    r.fulfill({
      json: [
        {
          id: 1,
          role: 'coach',
          text: '舊訊息，唔記得有冇睇相',
          payload: { summary: '舊', reply: '舊訊息，唔記得有冇睇相', vision_used: null },
          provenance: { mode: 'fake', provider: 'fake', adapter: 'FakeLLM', model: '' },
          created_at: '2026-10-01T09:30:00',
        },
        {
          id: 2,
          role: 'coach',
          text: '今次張相睇得清楚，T 字位偏油。',
          payload: {
            summary: '睇',
            reply: '今次張相睇得清楚，T 字位偏油。',
            vision_used: false,
            vision_clip: true,
          },
          provenance: {
            mode: 'live',
            provider: 'openai',
            adapter: 'OpenAICompatLLM',
            model: 'gpt-4o-mini',
          },
          created_at: '2026-10-01T09:31:00',
        },
      ],
    }),
  )

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  const bubbles = page.locator('.thread .msg.coach')
  await expect(bubbles).toHaveCount(2)

  // 冇徽章（`.vision-badge` 嘅 CSS 亦已經刪走 → 呢個係「唔准返嚟」嘅閘）
  await expect(page.locator('.vision-badge')).toHaveCount(0)

  // 冇內部字眼漏出（連 model 名都唔可以有）
  const leak = ['雲端', 'FakeLLM', '測試模式', 'openai', 'gpt-4o-mini', '未睇相', '已睇相', '已睇片']
  for (const word of leak) {
    await expect(bubbles.nth(0)).not.toContainText(word)
    await expect(bubbles.nth(1)).not.toContainText(word)
  }
})
