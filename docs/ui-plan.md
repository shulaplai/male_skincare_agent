# 手機版 UI／UX 大執 — 審計 + 計劃（2026-10-01）

> 狀態：**計劃，未開工**。呢份文件係「睇完再逐項批」用。
> 所有數字都係真瀏覽器（Chromium，390×844，dsf=2/3）量出嚟；script 喺 `/tmp/skc-trial/y1_ui_audit.py`
> 同 `y3_contrast.py`，可以隨時重跑。

## 0. 一句總結

功能上冇問題，但**冇 design token、冇元件層、冇量度門檻**，所以「細微嘅一致感」一直靠人眼，
每次改都係打補丁（`index.css` 而家 2,800 行、585 條 rule、**911 個 raw `px` 值**、0 個
`:focus-visible`、0 個 `prefers-reduced-motion`）。要「靚啲」唔係換色，係**加一層系統 + 一個可以
量度嘅門檻**，之後每次改都有 regression 網。

---

## 1. 審計（量到嘅嘢，唔係感覺）

### 1.1 觸控目標太細（WCAG 2.5.8 要求 ≥24×24；Apple HIG 建議 ≥44×44）

| 元素 | 實測 | 出現位置 | 嚴重度 |
|---|---|---|---|
| `.switch` 切換部位 ▾ | **78×22** | 每個 screen 頂部（4 個 shell 都有） | ⚠️ 低於 WCAG 24px |
| `.link-btn` ✎ 改筆記 / 🗑 刪除 | **49×20** / **42×20** | 記錄、進度 | ⚠️ 低於 WCAG 24px |
| `.btn.ghost.small` 測試連線 / ＋新增部位 | 62×22 / 354×22 | 設定 | ⚠️ 高 22px |
| `.theme` 日／夜 | 34×34 | 全部 | 低於 HIG |
| `.iconbtn` 相機 | 42×42 | 對話 composer | 低於 HIG |
| `.reveal` 「顯示」相片 | 72×36 | 對話（blur 相） | 低於 HIG |
| 指南 TOC chips | 149×35 | 指南 | 低於 HIG |
| 記憶／相關性 `.x` | 348×34（但**撳嘅字好細**） | 進度 | 中 |

### 1.2 字太細（每個 scene 都有 12 個 <12px 嘅文字節點）

9.5px：`.meta`（「你 · 18:00」對話時間）、`.k`（卡片 label）、tab bar label；
8.5px：`confidence 0.75`、記憶 tag；10px：`.entry-date`、`Theme`；
11px：attribute chips、`disclaimer`、`.delta`。手機上 9.5px ≈ 肉眼極限。

### 1.3 對比度不足（僅計實色背景；gradient 已剔除，避免假警報）

| 元素 | 實測對比 | 要求 | px |
|---|---|---|---|
| `.meta` 對話時間「你 · 18:00」 | **1.19** | 4.5 | 9.5 |
| `.advice li .n` 建議步驟編號 | **1.00** | 4.5 | 11 |
| `.meta`（教練）/ `.disclaimer` | 2.22 | 4.5 | 9.5–11 |
| `.v bad` / `.v good` 指標值 | 2.55 / 2.86 | 3（大字） | 18 |
| `.k` 指標 label / `.tl` tab label | 3.1 | 4.5 | 9.5–11 |
| `.entry-date` / `.pct` | 2.22 | 4.5 | 8.5–10 |
| `.link-btn`（改筆記／刪除） | 3.29 | 4.5 | 12 |
| `.src agent`「AI 偵測」 | 1.91 | 4.5 | 10 |

（`.mob-cta` 白字**冇**問題 —— 佢係 gradient 底，第一版 script 誤報 1.1，已修正量法。）

### 1.4 CSS／工程體質

| 指標 | 實測 | 問題 |
|---|---|---|
| `px` 硬值 | **911 個** | 冇 spacing／type scale，所以「點解呢度 13px 嗰度 12.5px」冇答案 |
| CSS variables | 47 個 | 顏色有 token，**尺寸冇** |
| rules | 585（2,800 行單檔） | 冇元件邊界，只能靠 selector 疊 |
| `:focus-visible` | **0** | keyboard／switch access 完全冇 focus 提示 |
| `prefers-reduced-motion` | **0**（13 transitions + 5 keyframes） | 關唔到動畫 |
| `<h1>` | 每屏 **2 個**，之後直接跳 `<h4>` | heading 階層斷（a11y） |
| `aria-live` | 0 | 「教練諗緊…」／錯誤唔會讀出嚟 |
| 原生對話框 | `window.alert` / `window.prompt` 仍在（改名／刪除／錯誤） | 手機上樣衰、阻塞，而且 in-app browser 會封 `prompt()` |

### 1.5 一致性（用戶講嘅「細微改變」）

- 同一個「刪除」動作有 3 種樣：`.link-btn danger`、`.x`、`.btn.ghost.small`。
- UI chrome 仲有 emoji 做 icon（ShellTop 狀態、chip 🍜/🧴、layout picker、指南 TOC ☀️🔢🧴）——
  同底部 tab bar 一模一樣嘅問題（字形大細／基線唔一致）。**底部已經換走，其他地方未。**
- 空態／載入態只有文字（「載入中…」），冇 skeleton；刪除冇 optimistic update；冇 error boundary。

---

## 2. 計劃（四階段，每階段獨立可批）

### Phase 0 — 量度工具（約一個 session，唔改任何 UI）

裝一個**前端檢查 script**，令之後每一步都有網：

| 工具 | 做咩 | 指令 |
|---|---|---|
| `@playwright/test` | 4 套 layout × 6 個 scene × 關鍵狀態嘅 **visual snapshot**（含 390／768／1280 三個闊度） | `npm i -D @playwright/test` |
| `@axe-core/playwright` | 每個 scene 跑 WCAG 2.1 AA（`violations` 當 gate） | `npm i -D @axe-core/playwright` |
| `eslint` + `@typescript-eslint` + `eslint-plugin-jsx-a11y` + `eslint-plugin-react-hooks` | 未命名 button、alt、hook 依賴問題 | `npm i -D eslint typescript-eslint eslint-plugin-jsx-a11y eslint-plugin-react-hooks` |
| `prettier` | 排版一致（而家冇） | `npm i -D prettier` |
| `stylelint` + `stylelint-config-standard` + `stylelint-declaration-strict-value` | **禁 raw hex／raw px**（逼用 token）—— 就係 911 個 px 值嘅解藥 | `npm i -D stylelint stylelint-config-standard stylelint-declaration-strict-value` |
| `@lhci/cli`（可選） | 手機 viewport 嘅 perf／a11y budget | `npm i -D @lhci/cli` |

新 script：`npm run ui:check` = typecheck ＋ snapshot ＋ axe ＋ stylelint。
**呢一步等於拍板 issue #12（frontend 冇 test harness）**，所以要你批。

### Phase 1 — Design token ＋ 基礎元件（唔改版面，只係換底層）

1. `src/styles/tokens.css`：spacing（4/8/12/16/24/32）、radius（10/14/18/999）、
   type scale（**最小 12px**、body 14–15、標題 19/24）、tap target 44、動效時長（120/200/320ms）。
2. `src/components/ui/`：`Button`（primary／ghost／danger／icon）、`Chip`、`Sheet`（底部彈出，
   取代 `window.prompt`）、`Toast`（取代 `window.alert`）、`Icon`（**一個 icon set = Lucide**，
   取代 UI chrome 嘅 emoji，同 tab bar 一致）、`Skeleton`、`Field`。
3. 全域：`:focus-visible` ring、`@media (prefers-reduced-motion: reduce)`、heading 階層修正、
   `.status` 之類嘅 `font-size: 0` hack 改成真元素。
4. 驗收：Phase 0 嘅 snapshot 要**有更新但只限預期嘅**（token 化唔應該改外觀；有改就要逐個講點解）。

### Phase 2 — 手機 UX 修正（用戶感受得到嘅嗰批）

1. 觸控目標全部 ≥44×44（`.switch`、`.link-btn`、`.btn.ghost.small`、`.reveal`、`.x`、TOC chips）。
2. 文字下限 12px：`.meta` 12、`.k` 12、`.entry-date` 12、`.pct` 12、tab label 11（加 icon 已足夠辨認）。
3. 對比度：`--muted` 由 3.0 拉到 ≥4.5（對話時間、disclaimer、link-btn、指標值），
   步驟編號 `.n` 換深色底或深色字（而家 1.0 = 睇唔到）。
4. 對話：`aria-live` 播「教練諗緊…」；送出後 optimistic 顯示；錯誤 inline 而唔係 `alert`。
5. 記錄／設定：改名／新增部位／刪除 → **bottom sheet ＋ inline 確認**（取代 `prompt`/`alert`）。
6. 載入：每個 scene 出 skeleton（唔係「載入中…」）；空態統一一個空態元件。
7. 動效：tab 切換加 120ms cross-fade、訊息入場收短、sheet 用 spring；
   全部跟 `prefers-reduced-motion`。

### Phase 3 — Polish（靚）

1. 相片：撳開全螢幕 viewer（而家只係原地解除模糊），支援 pinch／swipe。
2. 鍵盤感知 composer：`visualViewport` 令 iOS 鍵盤彈出時 composer 貼住鍵盤（唔會浮中間）。
3. 暗色模式全面覆核（有 `data-theme` 但未逐屏驗過）。
4. 橫向（landscape）＋平板／桌面間距覆核。
5. 微互動：tab active indicator 滑動、卡片 hover／press 狀態、pull-to-refresh（記錄 feed）。
6. 連續性：`localStorage` 記住每個 tab 嘅 scroll 位置（page 系統已經有 URL，順手做）。

---

## 3. 可以裝嘅 skill／工具（你問嘅）

### 3.1 Skill（我 session 已經有嘅，唔使裝）

| Skill | 安裝量 | 用途 |
|---|---|---|
| `anthropics/skills@frontend-design` | 940.1K | 起介面／視覺方向（Phase 1–3 主用） |
| `vercel-labs/agent-skills@web-design-guidelines` | 686.3K | 逐條對 Web Interface Guidelines（Phase 2 驗收） |
| `vercel-labs/agent-skills@vercel-react-best-practices` | — | React 效能／模式（元件重構時） |

### 3.2 值得另外裝嘅 skill

| Skill | 安裝量 | 點解 | 指令 |
|---|---|---|---|
| `emilkowalski/skills@review-animations` | 191.2K | 作者就係 Sonner／Vaul 作者，專審動效細節（Phase 2/3） | `npx skills add emilkowalski/skills@review-animations -g -y` |
| `mattpocock/skills@design-an-interface` | 217.1K | 由 interface 角度設計／評審畫面 | `npx skills add mattpocock/skills@design-an-interface -g -y` |
| `arvindrk/extract-design-system@extract-design-system` | 129.7K | 由現有 CSS 抽 token（Phase 1 一次過） | `npx skills add arvindrk/extract-design-system@extract-design-system -g -y` |

> ⚠️ 唔建議：`leonxlnx/taste-skill@redesign-existing-projects`（394.6K installs 但作者／repo 冇
> 可信背景，而且「重新設計」同我哋要嘅「保留 feature parity」方向相反）。
> Playwright 相關 skill（`playwright-visual-testing` 1.3K installs 等）安裝量太低，
> 直接裝 `@playwright/test` 更實際。

### 3.3 我 session 已經有嘅**量度**工具（唔使裝，但係今次審計嘅關鍵）

- Playwright（Python，喺 `backend/.venv`）→ 量 box／tap target／font-size／overflow／hover／wheel。
- `vision_pixel_diff` → 改前改後像素對比（唔靠肉眼）。
- `vision_colors` → 抽真實 palette（核對 token 同設計）。
- `vision_detect` / `vision_ground` → 列元件位置、驗「icon 同文字對齊」。
- `webapp-testing` skill（已裝喺 `~/.agents/skills`）→ 瀏覽器互動測試流程。
- 環境注意：`~/.npm` 有 root-owned 檔案，`npx -y` 要 `npm_config_cache=/tmp/npmcache-npx`。

---

## 4. 驗收門檻（做完點算「好」）

1. `npm run ui:check` 綠：typecheck ＋ snapshot（0 意外 diff）＋ axe（0 violation）＋ stylelint（0 raw hex/px）。
2. 量度到位：**冇任何 tap target <44×44**、**冇任何文字 <12px**、**冇任何文字 <4.5:1（大字 <3:1）**。
3. 四套 shell × 6 個 scene 喺 390／768／1280 都有 snapshot，改動一定要連 snapshot 一齊 commit。
4. 唔可以違反 AGENTS.md 約定：唔加 demo 數、四個 shell feature parity、
   `resolveLayout` 仲係唯一真源、consent gate 照樣 server-side。

## 5. 決定記錄（2026-10-01，用戶逐項批）

| # | 決定 | 用戶選擇 | 影響 |
|---|---|---|---|
| 1 | Phase 0 量度工具（＝拍板 issue #12） | **批，用戶自己裝**（`@playwright/test`、`@axe-core/playwright`、eslint 系、prettier、stylelint 系） | `frontend/package.json` 多 ~8 個 devDependency；runtime 依賴不變（React + Vite）；要 `npx playwright install chromium` |
| 2 | Icon 統一 | **全部換 Lucide**（連 UI chrome 嘅 emoji，25–30 個位） | `defs.ts` 嘅 `icon` 由 emoji string 改成 key；`ICONS` registry 同 `navIcons.tsx` 同源；句子內嘅 `→ ↑ ↓` 唔換 |
| 3 | 動效 | **保守：120–200ms fade／slide**，全部跟 `prefers-reduced-motion` | 唔加 tab indicator 滑動、唔加 sheet 揈走手勢（少兩個低階機掉 frame 位） |
| 4 | Sheet／Toast | **自己寫**（約 120–150 行），唔裝 `sonner`／`vaul` | runtime 依賴仍然係 2 個 |
| 5 | 字級 | **完整 scale**：最小 12px；tab label 9.5→11px；對話時間 9.5→12px；confidence 8.5→12px；chips／disclaimer 11→12px；對話正文 14.5→15px | tab bar 高 54→約 58px；一屏少一條訊息 |

### 已寫好嘅 Phase 0 交付（等用戶裝完依賴就可以跑）

| 檔案 | 做咩 |
|---|---|
| `frontend/tests/ui/fixtures.ts` | deterministic API fixture（攔截 `/api/**`，唔讀真 DB、唔會 commit 到真相）。⚠️ 註明 Playwright route 係**反轉** match：catch-all 要最先註冊 |
| `frontend/tests/ui/snapshots.spec.ts` | 4 layout × 6 scene ＋ 長 thread ＋ 760/761 斷點 snapshot |
| `frontend/tests/ui/a11y.spec.ts` | axe WCAG 2.1 AA，未修問題要明文寫入 `KNOWN`（唔准靜靜 skip） |
| `frontend/playwright.config.ts` | 390／768／1280 三個 project；Vite 自己起喺 :5180（唔撞 :5173／:5174） |
| `frontend/eslint.config.js` | flat config ＋ `jsx-a11y`（icon-only 按鈕冇 accessible name 會即刻被抓） |
| `frontend/stylelint.config.mjs` | Phase 0 只禁 raw hex（raw px 留到 Phase 1 有 token 之後）—— 一次過禁會 900 個 error，冇人睇得清 diff |
| `frontend/.prettierrc.json` ＋ `.prettierignore` | 排版一致（未加入 `ui:check`，避免一次過 reformat 成個 repo） |
| `package.json` | `npm run ui:check`（typecheck ＋ lint ＋ stylelint ＋ playwright）／`ui:update`／`lint:fix`／`format` |

### Phase 0 完成報告（2026-10-01）

- **依賴**：`eslint` 要 pin `^9`（`eslint@10` 同 `eslint-plugin-jsx-a11y` 唔相容，第一次裝就係噉失敗）。
- **Gate**：`npm run ui:check` = typecheck ＋ eslint（0 error／47 warning）＋ stylelint（0 error／113 warning）
  ＋ Playwright **37 tests**（31 snapshot ＋ 6 axe）。**連跑兩次都綠**。
- **Snapshot baseline**：31 張、3.4MB、1x CSS 像素（`tests/ui/__screenshots__/`，要 commit）。
  包括 P1-4 長 thread 回歸網、760/761 斷點（實測 760 = `layout-mobile`、761 = `layout-chat`）、影片上載（唔漏「抽格」字眼）。
- **axe baseline（真問題，Phase 2 修完要清空）**：
  - `color-contrast`：5 個 scene 共 **70 個節點**，全部來自 4 個 token —— `--faint` 1.91–2.22、`--muted` 3.10–3.29、
    `--accent-deep` 3.86、`--good` 3.41。
  - `scrollable-region-focusable`：`main.view` 可以捲但冇 focusable 內容（鍵盤捲唔到）。
- **順手修好嘅真 bug（唔係測試問題）**：
  1. `index.css` 有一個**孤兒 `}`**（我之前刪死 CSS 留低）→ stylelint 一開就 syntax error。
  2. `Chat.tsx` 冇喺 **webfont 載入完**重新 pin 到底 → 真用戶 reload 後條 thread 未必貼住最新一句（同時令 snapshot flaky）。
  3. `Sidebar.tsx` 有個 `<label>` 冇綁 control（axe 會報）→ 改做 `<span>`。
- **`npm run ui:test` 嘅環境**：Vite 自己起喺 **:5180**，唔會撞你手上嘅 :5173／:5174。

---

## 7. Phase 1–3 完成報告（2026-10-01）

`npm run ui:check` 綠：**51 個 Playwright test**（41 snapshot ＋ axe 淺／暗 12 ＋ 互動 5）＋ eslint 0 error ＋ stylelint 0 error。

| 指標 | 之前 | 之後 |
|---|---|---|
| axe violation（淺色） | 70 contrast ＋ 1 focusable | **0** |
| axe violation（暗色） | 冇測過 | **0**（新增 12 個 case） |
| 觸控目標 < 44px | 8 類（最細 **16×16**） | **0** |
| 文字 < 12px | 每屏 12 個 | **0**（tab label 11px 係核准例外） |
| `:focus-visible` | **0 條 rule** | 6 條 ＋ 可捲區域 focus 得到 |
| `prefers-reduced-motion` | **0** | 1（全域 rule） |
| 未定義 CSS 變數（`--bg2`／`--ink`） | 8 處 | **0** |
| `window.prompt/confirm/alert` | 7 處 | **0** |
| CSS var 數量 | 47 | 76 |
| stylelint warning | 113 | 67 |
| 前端 test | 0（冇 harness） | 51 |

**新增**：`components/ui/EmptyState.tsx`（統一空態：icon ＋ 一句；`blocks`／`ProgressView`／`RecordsView`／`RightPanel`／`DashHome` 共 11 處）、、`components/Icon.tsx`（Lucide registry，35 個 icon，navIcons 變成 thin wrapper）、`components/ui/{Sheet,Confirm,Toast,Skeleton,Lightbox}.tsx`、`hooks/useViewportHeight.ts`（iOS 鍵盤：`--vvh`）。

**過程中捉到嘅真 bug**（唔止改色）：
1. `.switch`（切換部位）**完全冇 CSS rule** → 高度跟 line-height = 22px。
2. `.attach .x`（移除相片）實際 **16×16** → 視覺 24px、撳得到 44×44（`::after` 撐開）。
3. `.link-btn` 有**重複 `padding: 0`** 抵銷咗內距（「改筆記」一直逼住個字）。
4. 建議步驟編號對比度 **1.0:1**（等於睇唔到）→ 5.67:1。
5. **`--bg2`／`--ink` 從來冇定義過** → 暗色模式淺底淺字（`.chip.neutral` 1.03:1）。
6. 手機用 `font-size: 0` 收埋「Agent 在線」 → 改 `.sr-only`。
7. stylelint 捉到我自己整嘅 4 個重複宣告。

**刻意唔做（要記住，唔係漏咗）**：
- **冇做獨立 `Button`／`Chip` component**：`.btn`／`.chip` 已經 token 化，而 axe／stylelint／snapshot 三個 gate 已經封住「44px、對比度、focus」呢幾樣真正會錯嘅嘢；四個 shell 加起上嚟 ~40 個 button，包成 component 係純機械改動、冇用戶可見好處。
- **body-part 頭像 emoji（🧔／🧴）留低**：嗰個係 DB **資料**（每個對話唔同），唔係 chrome；要換就要 migration。
- **句子入面嘅 `→ ↑ ↓`** 當排版符號，唔換 icon。
- **Lightbox 唔做 pinch-zoom**：瀏覽器本身有 page zoom，自己實作會搶咗佢。

**Phase 3 覆核**：暗色 5 個 scene 有 snapshot ＋ axe 暗色全綠；橫向 844×390（`.compose` 仍喺畫面、冇橫向溢出）；平板 768×1024；760/761 斷點。

---

## 6. 樣板（2026-10-01 交；2026-10-05 用戶批准「照住做」）

**狀態**：批咗。用戶 2026-10-05 揀咗「照住 `design/mobile-v2-round1.html` 做」，
所以呢個檔案由「等批」變成**視覺參考**；Phase 1–3 嘅改動（tokens／元件／icon sweep／
字級／對比度／tap target／sheet／toast／skeleton／相片 viewer）已經按佢落地，
打後改手機版 UI 就照住佢，唔好再另開一套視覺語言。

**睇法**：`open design/mobile-v2-round1.html`（單一檔案、self-contained；只 serve `design/` 唔好喺 repo root serve）。
係**設計樣板**唔係 app：假數據、唔喺 Vite build 範圍。

11 個框，每個下面有「改咗咩」：

| 框 | 內容 | 主要改動 |
|---|---|---|
| ① 今日 | home | 環形數字 9.5→12px；卡片標題用新 `--accent-deep`（3.52→4.61:1）；「全部」由細字 link → 44px 按鈕 |
| ② 對話 | chat | 時間 9.5→12px（1.19→5.06:1）；自己嗰邊靠右 84%；步驟編號 1.0→5.5:1；相先模糊＋顯示；影片中性 chip；圓形箭嘴發送；輸入 16px |
| ③ 記錄 | records | 改筆記／刪除由 49×20 → 44px 高按鈕（原本低過 WCAG 24）；日期 10→12px；emoji → Lucide |
| ④ 進度 | progress | `--muted`／`--good`／`--warn` 全部換合規色；`AI 偵測` 1.91→5.06:1；🌐 → globe icon |
| ⑤ 設定 | settings | 改名／刪除／新增全部 44px；改用 bottom sheet |
| ⑥ 指南 | guide | TOC chip 35→44px；卡頭 emoji → icon；警告色 5.0:1 |
| ⑦ 狀態 | 載入／空態／錯誤 | skeleton 取代「載入中…」；空態有 icon＋行動掣；錯誤 inline chip |
| ⑧ 改名 Sheet | modal | 200ms slide、跟 reduced-motion；取代 `window.prompt`（iOS 連續彈會被封） |
| ⑨ Toast | 提示 | 取代 `window.alert`，附「復原」 |
| ⑩ 影片上載 | clip | 見你條片＋真進度條；唔會出抽格縮圖、唔提「抽咗 6 張相／壓縮」 |
| ⑪ 暗色 | dark tokens | `--faint` 2.82→5.20:1、`--muted` 5.90→7.79:1、`--accent-deep` 4.90→7.14:1 |

**樣板自己做錯過嘅嘢（已修，順手記錄）**：`--text` 係喺 `.phone` 上覆寫，如果我淨係喺 `body` 設 `color`，
暗色框會繼承 body 計好嘅淺色值 → 深字襯深底。所以 `color: var(--text)` 一定要喺同一個 scope 宣告。
（實作時對應嘅風險：`[data-theme=dark]` 喺 `<html>` 而 app 用 `var()` — 冇呢個問題，但換 token 時要逐屏睇。）

**批咗之後**：Phase 1（token ＋ 元件 ＋ icon sweep）→ Phase 2（字級／對比度／tap target／sheet／toast／skeleton）→ Phase 3（相片 viewer、鍵盤感知、暗色覆核），
每步都要 `npm run ui:check` 綠 ＋ snapshot diff 逐個解釋。
