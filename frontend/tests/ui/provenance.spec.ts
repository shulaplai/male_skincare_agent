import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * Issue #14 — provenance on the assistant bubble, non-pixel assertions only.
 *
 * Two falsehoods to keep out of the DOM:
 * 1. an unknown `vision_used` (null) must NOT render 「文字分析（未睇相）」 —
 *    that claim says the model looked at the photo and found nothing, which is a
 *    different fact from "we don't know";
 * 2. a fake-mode turn must say so, and a live one must name the resolved
 *    provider · model (the labels are pure functions in `src/format.ts`).
 */
test('provenance chip + honest three-state vision', async ({ page }) => {
  await installFixtures(page)
  // Registered AFTER the catch-all so it wins (Playwright matches last-first).
  await page.route('**/api/conversations/*/messages', (r) =>
    r.fulfill({
      json: [
        {
          id: 1,
          role: 'coach',
          text: '舊訊息，唔記得有冇睇相',
          payload: { summary: '舊', reply: '舊', vision_used: null },
          provenance: { mode: 'fake', provider: 'fake', adapter: 'FakeLLM', model: '' },
          created_at: '2026-10-01T09:30:00',
        },
        {
          id: 2,
          role: 'coach',
          text: '今次真係睇咗張相，但冇乜特別。',
          payload: { summary: '睇', reply: '睇', vision_used: false },
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

  await expect(bubbles.nth(0).getByText('FakeLLM · 測試模式')).toBeVisible()
  await expect(bubbles.nth(0)).not.toContainText('未睇相')

  await expect(bubbles.nth(1).getByText('openai · gpt-4o-mini')).toBeVisible()
  await expect(bubbles.nth(1)).toContainText('文字分析（未睇相）')
})
