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
