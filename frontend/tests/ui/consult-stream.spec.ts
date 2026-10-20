import { expect, test } from '@playwright/test'
import { CONVERSATION_ID, installFixtures } from './fixtures'

/**
 * 送訊息唔應該係「撳完之後一片空白，等到 5.5 秒先彈一段字」（audit §7 串流）。
 *
 * 後端而家逐個 graph node 送一個 SSE frame（`POST /api/consult/stream`），前端每個
 * node 換一句「而家做緊咩」。呢個 spec 要釘住三件事：
 *
 * 1. UI 真係行串流嗰條 route（唔會偷偷跌返去舊嘅 `/api/consult`）；
 * 2. 等緊嗰陣見到嘅係「步驟」而唔再係靜態嘅「約 5–10 秒」；
 * 3. 最終回覆係由 `result` frame 砌出嚟（即係串流路徑真係有 deliver 到結果）。
 *
 * 另外釘住失敗形狀：串流中途失敗冇得改 HTTP status，所以錯誤一定係 in-band
 * `error` frame —— 用戶要見到「出錯」＋「重試」掣，唔可以靜靜死。
 */
const NODES = ['analyze', 'tools', 'advise', 'guardrail', 'persist']

const STAGES = ['睇緊你講嘅同相…', '查緊相關知識同記憶…', '寫緊建議…', '檢查安全…', '記低今次…']

const RESULT = {
  analysis: { summary: 'T 字位偏油', metrics: [], attributes: [], tool_calls: [] },
  tool_results: [],
  advice: { reply: '建議你溫和清潔，唔好擠。', items: ['一日洗兩次面'], disclaimer: '唔係醫療診斷', escalate: false },
  escalate: false,
  vision_used: false,
}

function sseBody(frames: object[]): string {
  return frames.map((f) => `data: ${JSON.stringify(f)}`).join('\n\n') + '\n\n'
}

test('等緊嘅時候顯示後端行緊邊個步驟，最後出建議', async ({ page }) => {
  await installFixtures(page)
  let posted: Record<string, unknown> | null = null
  let legacyCalls = 0
  // 舊路徑唔應該再被用到（glob `**/api/consult` 唔會 match `/api/consult/stream`）。
  await page.route('**/api/consult', (r) => {
    legacyCalls += 1
    return r.fulfill({ json: RESULT })
  })
  await page.route('**/api/consult/stream', async (r) => {
    posted = r.request().postDataJSON()
    // 留住個 response，先睇得到 pending bubble 寫咩。
    await new Promise((res) => setTimeout(res, 900))
    return r.fulfill({
      contentType: 'text/event-stream',
      body: sseBody([...NODES.map((node) => ({ type: 'node', node, ms: 2500 })), { type: 'result', ...RESULT }]),
    })
  })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  await page.getByRole('textbox', { name: /教練對話/ }).fill('下巴爆咗兩粒瘡')
  await page.getByRole('button', { name: '發送' }).click()

  // 撳完即刻唔應該係「約 5–10 秒」嗰句，而係講緊而家做咩。
  await expect(page.locator('.bubble.typing')).toContainText(STAGES[0])
  await expect(page.locator('.bubble.typing')).not.toContainText('約 5–10 秒')

  expect(posted?.conversation_id).toBe(CONVERSATION_ID)
  expect(posted?.text).toBe('下巴爆咗兩粒瘡')

  // 回覆由 `result` frame 砌出嚟，pending bubble 收返。
  await expect(page.locator('.bubble').last()).toContainText('建議你溫和清潔')
  await expect(page.locator('.bubble.typing')).toHaveCount(0)
  expect(legacyCalls, '應該行串流路徑，唔好跌返去舊 route').toBe(0)
})

test('串流中途解析失敗：出錯誤氣泡同「重試」掣，唔會靜靜死', async ({ page }) => {
  await installFixtures(page)
  await page.route('**/api/consult/stream', (r) =>
    r.fulfill({
      contentType: 'text/event-stream',
      body: sseBody([
        { type: 'node', node: 'analyze', ms: 2500 },
        { type: 'error', detail: '我今次分析唔到（模型回覆格式唔啱）。' },
      ]),
    }),
  )

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  await page.getByRole('textbox', { name: /教練對話/ }).fill('下巴爆咗兩粒瘡')
  await page.getByRole('button', { name: '發送' }).click()

  await expect(page.locator('.bubble').last()).toContainText('出錯：我今次分析唔到')
  await expect(page.getByRole('button', { name: /重試/ })).toBeVisible()
})

/**
 * 逐字打出嚟（typewriter）。
 *
 * 背景：`playwright.config.ts` 預設 `reducedMotion: 'reduce'`，所以其他 39 個 gate 都係
 * 即刻出全句。呢個 test 專登開返 motion，確認三件事：①真係逐字（第一步短過全句）
 * ②最後一定出齊全句（唔會卡住／食字）③打完之後仍然貼住底部（唔會令用戶睇唔到最新一行）。
 */
test('教練回覆逐字打出嚟，而且會打齊同貼住底部', async ({ page }) => {
  const FULL = '建議你溫和清潔，一日洗兩次面，唔好擠。之後記得補水同防曬。'
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await installFixtures(page)
  await page.route('**/api/consult/stream', (r) =>
    r.fulfill({
      contentType: 'text/event-stream',
      body: sseBody([
        { type: 'node', node: 'analyze', ms: 120 },
        {
          type: 'result',
          ...RESULT,
          advice: { ...RESULT.advice, reply: FULL },
        },
      ]),
    }),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  await page.getByRole('textbox', { name: /教練對話/ }).fill('下巴爆咗兩粒瘡')
  await page.getByRole('button', { name: '發送' }).click()

  const bubble = page.locator('.bubble').last()
  const typed = bubble.locator('.reply-text')
  // 等到第一個字出咗，但仲未打晒
  await expect(typed).toContainText('建議')
  const partial = (await typed.innerText()).replace(/\s/g, '')
  expect(partial.length, '應該真係逐字打出嚟（未打晒）').toBeLessThan(FULL.length)

  // 打完：全句都在，而且順序一樣
  await expect(typed).toHaveText(FULL, { timeout: 5000 })
})

/**
 * 三段式回覆（2026-10-20 用戶要求）：① 標題 → ② 正文 → ③ AI 分析卡，逐段出。
 *
 * 釘住嘅係**次序**，唔止「最後有齊三樣」：以前卡片同正文一齊彈，用戶會先讀卡
 * 再讀解釋；而徽章（睇相／雲端／model）亦已經收埋，唔應該再出返嚟。
 */
test('回覆分三段出：標題 → 正文 → AI 分析卡，而且冇內部徽章', async ({ page }) => {
  const TITLE = '下巴新瘡：先減刺激'
  const BODY = '下巴嗰兩粒係新出嘅，先停新產品三日睇下會唔會消。我會記住今日呢組數字。'
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await installFixtures(page)
  await page.route('**/api/consult/stream', (r) =>
    r.fulfill({
      contentType: 'text/event-stream',
      body: sseBody([
        { type: 'node', node: 'analyze', ms: 60 },
        { type: 'result', ...RESULT, advice: { ...RESULT.advice, title: TITLE, reply: BODY } },
      ]),
    }),
  )
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('?layout=mobile&scene=chat')
  await page.waitForLoadState('networkidle')

  await page.getByRole('textbox', { name: /教練對話/ }).fill('下巴爆咗兩粒瘡')
  await page.getByRole('button', { name: '發送' }).click()

  const bubble = page.locator('.bubble').last()
  const title = bubble.locator('.coach-title')
  const body = bubble.locator('.reply-text')

  // ① 標題先出齊
  await expect(title).toHaveText(TITLE)
  // ② 正文仲打緊 → ③ 分析卡一定未出
  await expect(body).not.toHaveText(BODY)
  await expect(bubble.locator('.card')).toHaveCount(0)

  // ② 正文打完
  await expect(body).toHaveText(BODY, { timeout: 6000 })
  // ③ 之後才出卡
  await expect(bubble.locator('.card')).toBeVisible()

  // 內部狀態徽章唔應該再出（睇相／雲端／model 名）
  await expect(bubble.locator('.vision-badge')).toHaveCount(0)
})
