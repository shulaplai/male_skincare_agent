import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'
import { installFixtures } from './fixtures'

/**
 * 無障礙 gate（WCAG 2.1 A/AA）。Phase 2 嘅目標係 `violations` = 0；
 * 開頭會有已知問題，所以用 `KNOWN` 逐條列明（唔准靜靜 skip）。
 */
const SCENES = ['home', 'chat', 'records', 'progress', 'settings', 'guide'] as const

/**
 * Phase 0 baseline（2026-10-01 量度）。呢啲係**真問題**，唔係 false positive；
 * 寫入嚟係為咗唔好一開就紅燈擋住所有工作，但 Phase 2 修完**必須清空**。
 *
 * 證據（`npx playwright test tests/ui/a11y.spec.ts`，390×844，fixture data）：
 *  - `color-contrast`：5 個 scene 共 **70 個節點**，全部來自 4 個 token：
 *      `--faint` #c0a8ae → 1.91–2.22:1（對話時間 `.meta`、`confidence .pct`、`.entry-date`、`.metric .d`）
 *      `--muted` #a1878f → 3.10–3.29:1（tab label `.tl`、`.k`、`.link-btn`、`.clip-bubble`）
 *      `--accent-deep` #c95f80 → 3.86:1（`.card h4`、`.block-title`、`.derived`）
 *      `--good` #2e9e5b → 3.41:1（`.delta.good`）
 *    Phase 2 做法：調深 4 個 token（≥4.5:1）＋ 字級下限 12px，然後刪走呢條。
 *  - `scrollable-region-focusable`：`main.view` 可以捲但冇 focusable 內容 → 鍵盤用戶捲唔到。
 *    Phase 2 做法：`tabindex="0"` + focus ring（同 `:focus-visible` 一齊做）。
 */
const KNOWN: Record<string, string[]> = {
  // ✅ 2026-10-01 Phase 1 清空：
  //   colour-contrast 70 個節點 → 0（換 token：--muted 5.06:1、--faint 4.60:1、
  //   --accent-deep 4.61:1、--good 5.09:1、--warn 4.79:1、--danger 4.99:1、
  //   淡底文字用 --accent-ink 5.67:1；散裝 hex 全部換 token）
  //   scrollable-region-focusable → 0（`main.view` 加 tabIndex + :focus-visible）
  // 呢個 map 應該永遠空。要加嘢入嚟 = 要喺 PR 講明點解唔即刻修。
}

/**
 * ⚠️ 淺色同**暗色都要跑**。教訓：第一版只跑淺色，結果暗色模式有 9 個對比度問題
 * 完全冇人知（`--bg2`／`--ink` 係從來冇定義過嘅變數，所以 fallback 去 `#eee`／`#333`
 * —— 暗色之下就係「淺底淺字」）。axe 會正確處理半透明背景，我手寫嘅量度唔會。
 */
for (const theme of ['light', 'dark'] as const) {
  for (const scene of SCENES) {
    test(`a11y · mobile ${theme} ${scene}`, async ({ page }) => {
      await installFixtures(page)
      if (theme === 'dark') await page.addInitScript(() => localStorage.setItem('skc-theme', 'dark'))
      await page.goto(`?layout=mobile&scene=${scene}`)
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(400)
      const results = await new AxeBuilder({ page })
        .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
        .analyze()
      const ids = [...new Set(results.violations.map((v) => v.id))]
      const unexpected = ids.filter((id) => !(id in KNOWN))
      expect(
        unexpected,
        `未記錄嘅無障礙問題（${theme} ${scene}，要修，或者寫入 KNOWN 並解釋）: ${unexpected.join(', ')}`,
      ).toEqual([])
    })
  }
}

/**
 * 標題層級（唔靠 axe）。`heading-order` 係 axe 嘅 **best-practice** rule，唔在
 * `wcag2a/2aa/21a/21aa` 入面 → 上面嗰 12 條 axe test 完全捉唔到。2026-10-05 實測：
 * `ShellTop` 出 `<h1>` 之後各 section 直接 `<h3>`，gate 一路綠燈（audit §6 講嘅盲點）。
 *
 * 規則（WCAG 冇明文，但係 axe 同絕大部分報讀器嘅預期）：
 *   1. 頁面第一個**可見** heading 要係 `<h1>`
 *   2. 之後每一級最多深一級（`h2` → `h4` = 跳級）
 * 用 1280×900（四個 shell 都會真 render）＋ 390×844（窄屏一律 `resolveLayout` → mobile）。
 */
const HEADING_SCENES = ['home', 'chat', 'records', 'progress', 'settings', 'guide'] as const

async function headingLevels(page: import('@playwright/test').Page): Promise<number[]> {
  return page.$$eval('h1,h2,h3,h4,h5,h6', (els) =>
    els
      // 只計真係見到嘅（`display:none` 嘅 panel 唔算層級）
      .filter((e) => e.getClientRects().length > 0 && getComputedStyle(e).visibility !== 'hidden')
      .map((e) => Number(e.tagName.slice(1))),
  )
}

function headingProblems(where: string, levels: number[]): string[] {
  const bad: string[] = []
  if (levels.length === 0) return [`${where}：一個 heading 都冇`]
  if (levels[0] !== 1) bad.push(`${where}：第一個 heading 係 h${levels[0]}（要 h1）`)
  for (let i = 1; i < levels.length; i++) {
    if (levels[i] > levels[i - 1] + 1) {
      bad.push(`${where}：h${levels[i - 1]} → h${levels[i]} 跳級（序列 ${levels.join(',')}）`)
    }
  }
  return bad
}

test.describe('heading 層級', () => {
  test('桌面（1280×900）：四個 shell × 六個 scene', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 900 })
    await installFixtures(page)
    const bad: string[] = []
    for (const layout of ['chat', 'journal', 'dash', 'mobile'] as const) {
      for (const scene of HEADING_SCENES) {
        await page.goto(`?layout=${layout}&scene=${scene}`)
        await page.waitForLoadState('networkidle')
        bad.push(...headingProblems(`${layout}·${scene}`, await headingLevels(page)))
      }
    }
    expect(bad, `標題層級問題：\n${bad.join('\n')}`).toEqual([])
  })

  test('手機（390×844）：mobile shell × 六個 scene', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 })
    await installFixtures(page)
    const bad: string[] = []
    for (const scene of HEADING_SCENES) {
      await page.goto(`?scene=${scene}`)
      await page.waitForLoadState('networkidle')
      bad.push(...headingProblems(`mobile·${scene}`, await headingLevels(page)))
    }
    expect(bad, `標題層級問題：\n${bad.join('\n')}`).toEqual([])
  })
})
