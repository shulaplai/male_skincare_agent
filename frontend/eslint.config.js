import js from '@eslint/js'
import jsxA11y from 'eslint-plugin-jsx-a11y'
import reactHooks from 'eslint-plugin-react-hooks'
import tseslint from 'typescript-eslint'

/**
 * ESLint（flat config）。故意**唔**加 formatting 規則 —— 排版交俾 Prettier。
 * `jsx-a11y` 係 Phase 2 嘅網：icon-only 按鈕冇 accessible name 會即刻被抓。
 */
export default tseslint.config(
  { ignores: ['dist', 'node_modules', 'tests/ui/__screenshots__'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    plugins: { 'jsx-a11y': jsxA11y, 'react-hooks': reactHooks },
    rules: {
      ...jsxA11y.flatConfigs.recommended.rules,
      // ── Phase 0 baseline（2026-10-01）──
      // 量到 44 個真問題：`<span onClick>` / `<div onClick>` / `<a>` 當按鈕（改名、刪除、
      // 切換部位、theme、dropdown…）—— 鍵盤同 screen reader 用戶用唔到。呢啲係 **Phase 2
      // 要做嘅真 bug**，但 Phase 0 唔應該一開就紅燈擋住所有工作，所以先降做 warning，
      // Phase 2 修完（改用 <button> + focus ring）之後**必須**轉返 error 並清到 0。
      // 目標清單：Sidebar 14、Chat 10、JournalHome 9、ShellTop 7、其餘 ~5。
      'jsx-a11y/click-events-have-key-events': 'warn',
      'jsx-a11y/no-static-element-interactions': 'warn',
      'jsx-a11y/anchor-is-valid': 'warn',
      'jsx-a11y/no-noninteractive-element-to-interactive-role': 'warn',
      // 可以捲嘅區域（`.view` 有 overflow-y:auto）**一定要** focus 得到，否則鍵盤用家
      // 捲唔到內容 —— axe 本身有條規則（scrollable-region-focusable）就係噉要求。
      // 所以放行 `role="region"` + tabIndex（landmark role 係正確做法，唔係走後門）。
      'jsx-a11y/no-noninteractive-tabindex': ['error', { roles: ['region'], tags: [] }],
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      // 大細聲：`any` 唔准，但測試 fixture 例外（下面覆蓋）
      '@typescript-eslint/no-explicit-any': 'error',
      '@typescript-eslint/no-unused-vars': ['error', { argsIgnorePattern: '^_' }],
    },
  },
  { files: ['tests/**/*.ts'], rules: { '@typescript-eslint/no-explicit-any': 'off' } },
)
