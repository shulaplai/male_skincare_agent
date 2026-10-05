/**
 * Deterministic API fixtures for UI snapshots / a11y checks.
 *
 * Why: the visual gate must not depend on the developer's real database. Every
 * snapshot test intercepts the API and serves the data below, so
 * `npm run ui:test` gives the same pixels on any machine — and it can never leak
 * real skin photos or chat history into a snapshot file that gets committed.
 *
 * Shapes are copied from the live endpoints (2026-10-01); if a route changes
 * shape, update it here or the snapshot will fail loudly (which is the point).
 */

export const CONVERSATION_ID = 'fixtureconv0000000000000000000000'

/** 假相片（64×86 PNG，用代碼生成）：唔會用真用戶相，但畫面要見到 blur＋顯示掣。
 *
 * ⚠️ 圖案一定要**硬邊、高對比**。舊版係一塊低對比漸變（實測 67 色、channel std ≈ 10），
 * `blur(15px)` 對佢嘅影響只有平均 3.2/255 —— 低過 Playwright 嘅像素門檻，所以
 * 「皮膚相冇模糊」嗰個真 bug 喺 3 個 scene 出街，snapshot gate **一樣綠燈**。
 * 而家係 8px 棋盤格（3 色），模糊影響 79/255，一改就紅。
 * 要重做：Pillow 畫 8px 棋盤格 → PNG → base64（見 `docs/ui-plan.md`）。
 */
export const PHOTO_ID = 'f'.repeat(32)
const PHOTO_PNG_B64 =
  'iVBORw0KGgoAAAANSUhEUgAAAEAAAABWCAIAAADwhAcPAAABGElEQVR42u2aMQ6DMAxFAfUIPUovwNq5E9fo0omBvddg4g5cqEOlbp26VkqCLGHjWHreQEH8lzh2vqB9XK5NLqZ1zt4f+6Gq8V0TPAAAAAAAfKP9ft4h6n1pPCkEAAAAALCvD+AHSCEAAAAAP4AfIIUAAAAA/IBV/S49G9IPTOss4aw9hXQZfPaAIkP4TXyym9HXc/m/PN9vlZZRifrsnXpTqKTVgkHND8hVprm0pz90x8y93TpwFgIAANWQdCvdjqa/Atv6tmuojx8QdmLh3Dv4gewrU61GZyGdw9zYD+kMGSmmCimtWGAARfVqe8BF+kEAFqL5PkAVAgAAAADgfyFSCAAAAAAAP0AKAQAAAADgB0ghAADwjR9PDLOBIWdWywAAAABJRU5ErkJggg=='

export const CONVERSATIONS = [
  { id: CONVERSATION_ID, body_part: '面部皮膚', icon: '🧔', cloud_analysis: true },
  { id: 'fixtureconv1111111111111111111111', body_part: '頭皮', icon: '🧴', cloud_analysis: true },
]

export const CONSENT = { granted: true, at: '2026-10-01T09:00:00', required: false }

const COACH_PAYLOAD = {
  summary: 'T 字位偏油，下巴有一粒新瘡。',
  reply:
    '睇今次張相，T 字位反光範圍同上次差唔多，下巴嗰粒係新出嘅。建議照舊溫和潔面早晚一次，' +
    '精華繼續用煙酰胺，唔使加新產品；我會記住今次呢組數字，下次影相比對。',
  metrics: [
    { key: '油光', value: 2, dir: 'up', note: 'T 字位反光' },
    { key: '暗瘡', value: 1, dir: 'down', note: '下巴一粒' },
    { key: '毛孔', value: 2, dir: 'flat', note: '鼻頭較粗' },
  ],
  attributes: [
    { key: 'oiliness', severity: 2, note: 'T 字位反光' },
    { key: 'acne', severity: 1, note: '下巴一粒' },
  ],
  advice: ['早晚用溫和潔面，唔好用磨砂', '精華搽煙酰胺（日常）或 BHA（每週 2–3 次）', '日間搽防曬'],
  disclaimer: '以上建議只供參考，唔構成醫療意見。',
  escalate: false,
  vision_used: true,
  detected_events: [
    { type: 'diet', text: '食咗麻辣火鍋', tags: ['spicy'], product_name: '' },
    { type: 'product_start', text: '開始用煙酰胺精華', tags: [], product_name: '煙酰胺精華' },
  ],
  events_applied: false,
}

export const MESSAGES = [
  { id: 1, role: 'user', text: 'opp', payload: { photos: [] }, created_at: '2026-09-30T11:16:07' },
  {
    id: 2,
    role: 'coach',
    text: COACH_PAYLOAD.reply,
    payload: { ...COACH_PAYLOAD, detected_events: [], reply: 'Hello！想我幫你追蹤皮膚，先影一張自然光下嘅正面相，或者打幾隻字講下而家嘅狀況。' },
    created_at: '2026-09-30T11:16:07',
  },
  {
    id: 3,
    role: 'user',
    text: '（已上傳皮膚影片）',
    payload: { photos: [], clip: { duration: 12.4, frames: 6 } },
    created_at: '2026-10-01T09:12:00',
  },
  { id: 4, role: 'coach', text: COACH_PAYLOAD.reply, payload: COACH_PAYLOAD, created_at: '2026-10-01T09:12:20' },
  { id: 5, role: 'user', text: '（已上傳皮膚相）', payload: { photos: [PHOTO_ID] }, created_at: '2026-10-01T09:30:00' },
  { id: 6, role: 'coach', text: '睇到你張相，T 字位同上次差唔多。', payload: { ...COACH_PAYLOAD, detected_events: [] }, created_at: '2026-10-01T09:30:20' },
]

export const SUMMARY = {
  conversation: CONVERSATIONS[0],
  entries: [
    {
      id: 'e2', date: '2026-10-01', note: '今日塊面冇咁油',
      metrics: [{ key: '油光', value: 2, dir: 'down' }],
      attributes: [
        { key: 'oiliness', severity: 2, note: 'T 字位反光' },
        { key: 'acne', severity: 1, note: '下巴一粒' },
      ],
      /* ⚠️ 要有相：`entries[].photos` 以前係空 array，所以「記錄」／日記／今日
         三個 scene 喺 snapshot 同 a11y gate 眼入面**根本冇相**。結果 2026-10-01
         嗰個「相冇模糊」嘅真 bug 喺呢三頁出街，而 51 個 snapshot 全綠 ——
         網冇窿，只係個網冇蓋到嗰度。 */
      photos: [`photos/${PHOTO_ID}.jpg`], products: [],
    },
    {
      id: 'e1', date: '2026-09-30', note: '', metrics: [],
      attributes: [{ key: 'oiliness', severity: 3, note: '' }, { key: 'acne', severity: 2, note: '' }],
      photos: [`photos/${PHOTO_ID}.jpg`], products: [],
    },
  ],
  insights: [
    { id: 'i1', kind: 'derived', text: 'T 字位長期偏油', confidence: 0.75, direction: 'problem', tag: 'oiliness', scope: 'conversation' },
    { id: 'i2', kind: 'preference', text: '偏好清爽 gel 質地', confidence: 0.6, direction: 'normal', tag: 'texture', scope: 'global' },
  ],
  timeline: [
    { date: '2026-10-01', text: '食咗麻辣火鍋', source: 'user', scope: 'global' },
    { date: '2026-10-01', text: '開始用煙酰胺精華', source: 'user', scope: 'conversation' },
  ],
  anchors: [
    { key: 'oiliness', label: '油光', severity: 2, prev: 3, month: 3, quarter: null },
    { key: 'acne', label: '暗瘡', severity: 1, prev: 2, month: 2, quarter: null },
  ],
}

export const CORRELATIONS = {
  candidates: [
    { tag: 'spicy', label: '辣', days: 3, attribute: 'acne', delta: 1, strength: 'strong' },
  ],
  lines: ['辣 → 暗瘡：3 次之中 3 次之後一日暗瘡升 1 級'],
  entry_days: 4,
  cause_episodes: 3,
  note: '樣本仍然少，當參考。',
}

export const GUIDE = {
  title: '男士護膚基本資料',
  subtitle: '呢版係參考資料，唔係診斷。所有內容都註明出處；有醫療問題請諮詢皮膚科醫生。',
  sections: [
    {
      id: 'daily', title: '一日應該點護膚', icon: '☀️', summary: '三步就夠：潔面、保濕、防曬。',
      blocks: [{ type: 'para', text: '最基本而有效嘅護膚得三步：**潔面、保濕、防曬**。', items: [], tone: 'info', image_id: '', citations: ['www.nhs.uk :: Acne'] }],
    },
    {
      id: 'logging', title: '點樣記錄最準確', icon: '📝', summary: '每日 20 秒片（鏡頭慢慢掃）＞影相＞打幾隻字。',
      blocks: [
        { type: 'callout', text: '**（app 建議）** 每日拍一段約 20 秒嘅片，鏡頭慢慢掃過成塊面。', items: [], tone: 'tip', image_id: '', citations: [] },
        { type: 'steps', text: '', items: ['**影相**：自然光、唔好化妝', '**同一條件**：同一時間、同一光源'], tone: 'info', image_id: '', citations: [] },
      ],
    },
  ],
  sources: ['www.nhs.uk :: Acne'],
}

export const SETTINGS = {
  llm_provider: 'deepseek', model: 'deepseek-v4-flash', vision_model: 'deepseek-v4-flash-vision-exp', has_api_key: true,
}

export const HEALTH = { status: 'ok' }

/**
 * 攔截所有 API，令 UI 唔會讀到開發機嘅真 data。
 *
 * ⚠️ 註冊次序係反轉嘅：Playwright 由**最後註冊**嘅 route 開始 match。所以 catch-all
 * （即係 `page.route` 收 `**` + `/api/` + `**` 嗰條）一定要**最先**註冊，否則佢會食晒
 * 全部 request（真實撞過）。
 *
 * ⚠️ 亦唔好喺註解入面直接寫嗰個 glob：星號加斜線嘅組合會提早閂咗 JSDoc，
 * 令後面嘅文字變成 code → eslint 報 `no-unused-expressions`（實測過）。
 */
export async function installFixtures(page: import('@playwright/test').Page): Promise<void> {
  // 1) catch-all 先：冇 fixture 嘅 API 一律回空物件，唔會打真 server
  await page.route('**/api/**', (r) => r.fulfill({ json: {} }))
  // 2) 之後逐個具體 route 覆蓋
  await page.route('**/api/health', (r) => r.fulfill({ json: HEALTH }))
  await page.route('**/health', (r) => r.fulfill({ json: HEALTH }))
  await page.route('**/api/consent', (r) => r.fulfill({ json: CONSENT }))
  await page.route('**/api/settings', (r) => r.fulfill({ json: SETTINGS }))
  await page.route('**/api/conversations', (r) => {
    if (r.request().method() === 'POST') return r.fulfill({ json: CONVERSATIONS[0] })
    return r.fulfill({ json: CONVERSATIONS })
  })
  await page.route('**/api/conversations/*/messages', (r) => r.fulfill({ json: MESSAGES }))
  await page.route('**/api/conversations/*/summary', (r) => r.fulfill({ json: SUMMARY }))
  await page.route('**/api/conversations/*/correlations', (r) => r.fulfill({ json: CORRELATIONS }))
  await page.route('**/api/guide', (r) => r.fulfill({ json: GUIDE }))
  // 相片：回一張固定嘅 PNG（唔係 JSON），令 <img> 有嘢顯示（snapshot 要確定性）
  await page.route('**/api/photos/*', (r) =>
    r.fulfill({ status: 200, contentType: 'image/png', body: Buffer.from(PHOTO_PNG_B64, 'base64') }),
  )
}
