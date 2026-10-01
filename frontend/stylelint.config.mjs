/**
 * Stylelint（Phase 0，2026-10-01 用戶批准）。
 *
 * 設計原則：**只報「真嘢」**。第一次跑量到 584 個問題，但 578 個係排版口味
 * （369 × rule-empty-line-before、49 × 單行多個 declaration…）—— 呢個 repo 嘅 CSS 係
 * 手寫 compact 風格，排版唔應該由 stylelint 管（要排版用 Prettier）。所以：
 *
 *  1. 關掉所有純排版規則（下面列明）；
 *  2. 保留正確性規則（語法、未知屬性、重複 selector…）→ 呢啲係 error；
 *  3. `color-no-hex` 先做 **warning**：`index.css` 仲有 ~50 個 raw hex（大部分係
 *     `var(--x, #fff)` 嘅 fallback）。Phase 1 有完整 token 之後會逐個清，然後**轉 error**。
 */
export default {
  extends: ['stylelint-config-standard'],
  rules: {
    // ── 純排版／口味：交俾 Prettier 或者人手，唔用 stylelint 管 ──
    'rule-empty-line-before': null,
    'at-rule-empty-line-before': null,
    'declaration-empty-line-before': null,
    'comment-empty-line-before': null,
    'custom-property-empty-line-before': null,
    'declaration-block-single-line-max-declarations': null,
    'color-function-notation': null,
    'alpha-value-notation': null,
    'media-feature-range-notation': null,
    'value-keyword-case': null,
    'number-max-precision': null,
    'selector-class-pattern': null,
    'no-descending-specificity': null,
    'comment-whitespace-inside': null,

    // ── 正確性：error ──
    // ⚠️ `no-duplicate-selectors` 暫時係 warning：`index.css` 有 6 個 selector 定義兩次
    // （`.chip` `.convo` `.entry-date` `.entry-photos` `.hint` `.mem .t`）。併合會改
    // cascade 次序 = 可能改外觀，所以要同 Phase 1 token 化一齊做、逐個有 snapshot 睇住。
    'no-duplicate-selectors': [true, { severity: 'warning' }],
    'declaration-block-no-duplicate-properties': true,
    'property-no-unknown': true,
    'unit-no-unknown': true,
    'selector-pseudo-class-no-unknown': true,
    'selector-pseudo-element-no-unknown': true,
    'selector-type-no-unknown': true,
    'function-no-unknown': [true, { ignoreFunctions: ['color-mix', 'theme'] }],

    // ── 顏色：Phase 1 轉 error（見上面註解）──
    'color-no-hex': [true, { severity: 'warning' }],
  },
  ignoreFiles: ['dist/**', 'node_modules/**'],
}
