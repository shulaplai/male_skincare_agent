# UX／UI 審計（第二輪，2026-10-05）

> 方法：用真 app（`uvicorn :8001` ＋ Vite `:5173`，即係**用戶自己嗰個 DB**）做只讀探測 ——
> iPhone 390×844（dsf 3、`is_mobile`）同桌面 1280×900，`Playwright` 收集 console／
> 失敗請求／幾何尺寸；另加 `backend/data/runs.jsonl` 嘅真實延遲統計。
> 所有數字都係量出嚟嘅，唔係估計。**唔會**喺探測期間發送任何訊息或改動真 data。

## 0. 基準（修之前）

| 項目 | 量到 |
|---|---|
| console error／page error／失敗請求 | 0／0／0（兩個 viewport、全部 6 個 scene） |
| 橫向溢出 | 0 |
| 手機 < 12px 文字 | 5（全部係 `--f-tab: 11px` 底部 tab label，已批） |
| 手機 < 44px 撳得到嘅嘢 | 0 |
| `axe` WCAG 2.1 AA | 淺／暗各 0 violations |
| `/api/consult` 真實延遲（5 次） | 中位 **5.46 s**、最慢 **7.36 s**（`analyze` 中位 2.56 s、`advise` 2.88 s） |

即係表面乾淨。**問題全部喺「量度方法睇唔到」嘅地方**，呢個係本輪最大教訓。

## 1. P0 —— 皮膚相冇模糊（私隱）

`AGENTS.md` 明文寫住「相片一律先模糊（`components/BlurPhoto.tsx`）……皮膚相係自拍，
`<img>` 直接出清等於行過嘅人一眼睇晒」。但實際只有 `Chat.tsx` 用 `BlurPhoto`，
另外三個地方係裸 `<img>`：

| 檔案 | 位置 | 後果 |
|---|---|---|
| `RecordsView.tsx:153` | 「記錄」tab | 14 張自拍全清、82px 格 |
| `MobileHome.tsx:178` | 「今日」tab（**手機一開就見到**） | 14 張自拍全清、98px 格 |
| `JournalHome.tsx:111` | 桌面日記 feed | 14 張自拍全清，而且包 `<a href="/api/photos/…" target="_blank">` → **撳一下就喺新 tab 開原圖**，繞過 Lightbox |

量到（修之前）：

```
home(手機):            imgs=14  blurred=0  wrapped=0  inAnchor=14
records(手機):         imgs=14  blurred=0  wrapped=0  inAnchor=0
journal(桌面 1280):    imgs=14  blurred=0  wrapped=0  inAnchor=14
→ 42 張相、0 張模糊、`getComputedStyle(img).filter === 'none'`
```

獨立視覺覆核（modlens）：*「sharp, clearly recognizable photos of a person's face …
not blurred or obscured … no 顯示 button」*。

**修法**：`BlurPhoto` 加 `grid` variant；三個 caller 一律改用；`JournalHome` 拆走
`<a target="_blank">`；`×` 由 `<i onClick>` 改真 `<button>`（44px hit area，視覺上
仍然係 18px 圓點）。修完：`42 張相、42 張 blurred、42 張 wrapped、0 個 anchor`。

## 2. P0 —— 「匯出數據」等於壞（唯一嘅備份路徑）

`export_zip()` 對 `data_dir` 做 `rglob`，而 fastembed 嘅 ONNX model cache 就住喺
`data/` 入面（`SKINCOACH_EMBEDDER_CACHE_DIR=./data/.fastembed-cache`，另外仲有一份
`.hf-cache`）。

| | 修之前 | 修之後 |
|---|---|---|
| 入 archive 嘅檔案 | 71 個、**1070.5 MB** | 29 個、113.8 MB |
| 其中 model cache | **962 MB（90%）**：`.hf-cache` 481 MB ＋ `.fastembed-cache` 481 MB（同一個 235 MB blob ×2） | 0 |
| 壓縮後 zip | ~953 MB | **66.1 MB** |
| `GET /api/export` | **45 s 0 bytes（timeout）**；放長到 50.5 s 先返齊 | **5.6 s** |
| 峰值記憶體 | ~1 GB（`io.BytesIO` 建好再被 `getvalue()` 複製一次） | 持平（temp file 串流，1 MB 一 chunk） |

ONNX 權重壓唔縮（實測 deflate ratio 0.92、21.6 MB/s），所以 50 s 全部係白做嘅 CPU。

**修法**：`EXPORT_SKIP_DIRS`（`.fastembed-cache`、`.hf-cache`、`__pycache__`、`.cache`）
＋ `iter_export_zip()` 串流；route 改 `StreamingResponse`。加 2 個 test（plant 一個假
cache 落 `tmp_path`，同串流 chunk 要一致）。

**點解舊 test 捉唔到**：`test_export.py` 三個 test 都係
`monkeypatch.setattr(settings.data_dir, str(tmp_path))` —— `tmp_path` 係乾淨嘅空目錄，
`rglob` 瞬間行完。其中一個 test 嘅 docstring 仲**明文寫住**「walks the whole data dir
with `rglob`」，即係知道個行為，但冇人喺 fixture 放一個 cache 落去。

> ⚠️ 順帶：`skincoach.db.bak`（35.7 MB，舊快照）仍然喺 archive 入面，佔 66 MB 嘅一半。
> 佢係真 user data（有人刻意留嘅備份），所以**冇**排除，但你知就得。

## 3. P1 —— 桌面版導覽唔入 URL（reload／上一頁／深層連結全失效）

`ChatShell`（闊屏 default 結構）係四個 shell 之中**唯一**仲用 `useState` 存 scene 嗰個。

量到（修之前，1280×900）：

| 動作 | 結果 |
|---|---|
| 撳「皮膚記錄」 | URL 仍然係 `/`；**reload 之後跌返對話**（text 4023 vs 580） |
| 撳「進度追蹤」／「設定」 | 同上（887 / 1119 → 4023） |
| 撳完設定再撳瀏覽器「上一頁」 | 去咗一個**舊嘅** `?scene=guide`，唔係上一頁 |
| `?scene=guide` 直接開 | 完全冇反應（DOM 同對話頁一模一樣，4023） |
| `modlens` | `?scene=guide` deep link 之前 = 假 |

**修法**：`ChatShell` 改用 `useSceneRoute(CHAT_TABS)`（＋ `CHAT_VIEWS` 過濾 `home`，
唔係嘅話 `?scene=home` 會 render 一片空白）。修完四個 nav 全部：URL 變、
reload 保持、Back 真係返上一頁、`?scene=guide` 出到指南（3806）。

## 4. P1 —— 純鍵盤用戶完全用唔到

實測 Tab 40 次，**一次都去唔到** nav（教練對話／皮膚記錄／進度追蹤／護膚指南／設定）。
原因：`Sidebar` 同 `ShellTop` 嘅 `<a>` **冇 `href`** —— 冇 href 嘅 `<a>` 唔入 tab order、
唔會被讀成 link。同一類問題散落全 app：`<span onClick>`／`<i onClick>`／`<div onClick>`
共 **17 處**（自己寫嘅 regex 掃 `src/**/*.tsx`，唔靠 eslint）。

最嚴重嗰幾個：
- `Chat.tsx:369` composer 嘅**影相／錄片掣**（手機主要動作）係 `<span>`；
- `Chat.tsx:290` ＋ `ShellTop.tsx:31`「切換部位 ▾」係 `<span>` → **轉唔到部位**；
- `Chat.tsx:415/427`、`RecordsView.tsx:154`、`JournalHome.tsx:113`、`blocks.tsx:73`、
  `RightPanel.tsx:172`、`Sidebar.tsx:68/69` 嘅「刪除／改名／移除」全部係 `<i onClick>`；
- `JournalHome.tsx` 個 drawer 冇 `role="dialog"`、冇 Esc、閂唔到。

**點解 axe 綠燈**：axe 冇規則要求 `<a onClick>`／`<span onClick>` 要 focusable。
「0 violations」唔等於「用得到」。

**修法**：
- nav／scene tabs → 真 `<a href>`（`sceneHref()` 產生，同 `go()` 寫入嘅 URL 一致；
  `linkClick()` 保留 Cmd／中鍵開新 tab）；
- 下拉 → 新 `components/ui/BodyPartMenu.tsx`（兩個 caller 共用一份，唔再一人一份）；
- 其餘 `<span>`／`<i>` → 真 `<button>` ＋ `aria-label`；
- drawer 加 `role="dialog"`／`aria-modal`／Esc／真閂掣，背景改用真 `<button>` backdrop
  （同 `ui/Sheet.tsx` 同一招）；
- `ui/Sheet.tsx` 加 focus trap（之前 Tab 會行到 `.scrim` 後面被蓋住嘅控制項）。

修完 Tab order（實測）：
`新增對話 → 對話行 → 改名／刪除對話 → 新增部位對話 → 5 個 nav link → 切換部位 →
主題 → 顯示相片 → 影相／錄片 → 輸入框（有 aria-label）→ 發送 → 6 個刪除記憶`。

`eslint` 由 1 error / 6 warnings → **0 error / 2 warnings**（兩條係舊有 `useMemo` deps）。

## 5. P1 —— 加到 iPhone 主畫面完全冇做

`frontend/index.html` 之前冇 manifest、冇 favicon、冇 apple-touch-icon、
冇 theme-color、冇 description。對一個**手機為主**嘅 app 具體後果：
「加入主畫面」用網站截圖做 icon，而且一開係 Safari（有網址欄）。

量到（修之前）：`manifest:false icon:false appleTouch:false themeColor:null`。

**修法**：
- `frontend/public/manifest.json`（`display: standalone`、portrait、`theme_color`）
- 4 個 PNG（`icon-192`、`icon-512`、`apple-touch-icon` 180、`favicon` 64）
  —— 由 `frontend/scripts/generate_icons.py` 用 Pillow 產生（**唔係**手畫 binary，
  顏色跟 `--accent-deep` / `--bg` token）。幾何實測：水滴 252×321、左右 padding
  對稱 130/130、maskable 安全圈 203.3 < 204.8 → **唔會被裁**。
- `apple-mobile-web-app-capable`（iOS 唔用 manifest 決定 icon／standalone，
  只認 `apple-touch-icon` 同呢個 meta，兩套都要）
- `theme-color`：兩個帶 `media` 嘅 tag（首屏未載 JS 用）＋ `index.html` inline
  script 同 `theme.tsx` 跟 `data-theme` 更新（實測暗色 → `#1c1419`，
  切回淺色 → `#faf3f0`）
- `color-scheme: light` / `[data-theme='dark'] { color-scheme: dark }`
  （之前 `getComputedStyle(html).colorScheme === 'normal'` → 暗色模式捲軸同
  native 控制項仍然係白色）
- `touch-action: manipulation`（去雙擊縮放嘅 300ms 延遲）＋
  `-webkit-tap-highlight-color: transparent`（之前係 WebKit 預設藍
  `rgba(51,181,229,0.4)`，同玫瑰／米色系撞）

## 6. 最重要：gate 本身嘅盲點

呢輪所有 P0／P1 都係**通過咗全部 gate** 之後出街嘅。逐個講點解：

| 盲點 | 證據 |
|---|---|
| **Snapshot 睇唔到 blur** | fixture 嗰張假相係低對比漸變（67 色、channel std ≈ 10），`blur(15px)` 只改到平均 **3.2/255**，低過 Playwright 門檻 |
| **Fixture 根本冇相** | `SUMMARY.entries[].photos` 係 `[]` —— 「記錄」／日記／今日三個 scene 喺 gate 眼入面從來冇相 |
| **Snapshot 會隨真實日期腐爛** | baseline 2026-10-01 影，當時 fixture 嗰日就係「今日」→ 出「今天」；10-05 再跑變「2026-10-01」→ 3 個 snapshot 無故紅燈（實測 `390-mobile-home` 日期字 ink 由 91px → 150px） |
| **axe 捉唔到「撳唔到」** | 冇規則要求 `<a onClick>`／`<span onClick>` focusable |
| **`test_export` 嘅 `tmp_path` 太乾淨** | 真 data dir 有 962 MB model cache，test 嗰個係空目錄 |
| **自己寫嘅量度漏 `<i>`／`<span>`** | 第一輪「0 個 < 44px tap target」係查 `button, a[href], input, …` —— `<i onClick>` 唔喺 selector 入面，所以完全冇量到 |
| **axe 捉唔到標題層級** | `a11y.spec.ts` 只 `withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa'])`，而 `heading-order` 係 axe 嘅 **best-practice** rule、唔在呢四個 tag 入面 → `ShellTop` 個 `<h1>` 之後直接 `<h3>`，12 條 axe test 一路綠燈 |

**修法（今輪一齊做）**：
1. `frontend/tests/ui/photos.spec.ts`（**新**，4 個 test）：直接斷言每個 scene
   每張相都有 `.photo.blurred` ancestor、`filter` 含 `blur`、**冇** anchor。
   已驗證**會紅**：暫時將 `RecordsView` 還原做裸 `<img>` → 即刻
   `Error: 有相冇經 BlurPhoto`，還原之後返綠。
2. fixture 假相換成 8px 棋盤格（3 色，模糊影響 **79/255**），
   `SUMMARY.entries[].photos` 加相。
3. `snapshots.spec.ts` 嘅 `settle()` 加 `page.clock.setFixedTime('2026-10-01T09:00+08:00')`
   —— 固定「今日」，timer 照跑（唔用 `clock.install()`，佢會停 timer）。
4. `export` 加 2 個 test，其中一個**刻意 plant** cache 目錄。
5. `a11y.spec.ts` 加「heading 層級」2 個 test（**唔靠 axe**，自己行 DOM）：
   桌面 1280×900 四個 shell × 六個 scene ＋ 手機 390×844 六個 scene，
   規則 = 第一個**可見** heading 要係 `h1`、之後每級最多深一級。
   已驗證**會紅**：未修之前 `chat` 結構嘅記錄／進度／設定／指南頁第一個 heading 係 `h2`。

## 7. 進度（2026-10-05 晚更新）

### 已修

| 項目 | 修咗咩 |
|---|---|
| 離線 retry | `api.ts` 加 `readableError()`：`TypeError`／`Failed to fetch` →「連唔到後端，檢查 network／backend 起咗未？」；其餘非中文 raw message 包成「系統出錯（…）」。`src/` 15 處 raw `.message` 全部改走。失敗氣泡加「重試」掣，重用原本 payload（唔會出多一條用戶訊息） |
| 失敗訊息保留 | 同一個 session 內：失敗嗰條 user 氣泡仍然喺 thread，錯誤氣泡有「重試」。⚠️ **reload 之後仍然冇** —— 失敗嗰次冇寫入 DB，要真保留就要將 user message 落地 |
| 時間感知問候 | `format.ts` 加 `greeting()`（5–12 早晨呀／12–18 午安／18–23 晚上好／其餘 夜深喇，配 sun／moon icon）。Snapshot 靠 `clock.setFixedTime('2026-10-01T09:00+08:00')` 固定喺「早晨呀」，所以冇 churn |
| `Intl.DateTimeFormat` | `format.ts` `hhmm()` 改用 `Intl.DateTimeFormat('zh-HK', { hour: '2-digit', minute: '2-digit', hour12: false })`。實測 local midnight 出 `00:00`（唔會 `24:00`），同手寫 `padStart` 逐個 case 一致 |
| 表格語意 | `ProgressView`／`DashHome` 基準比較表由 `div`／`span` 改成真 `<table>` + `<thead>` + `<th scope="col">`／`<th scope="row">`；`.anchor-table` 改 `border-collapse` 代替 flex gap（⛔️ 唔可以再喺 `tr`／`td` 加 `display:flex`，會連語意一齊拆）。量度：**362×70**（以前 flex **362×74**，差 2 條 2px gap）→ 5 個 snapshot 只係表格以下整體**上移 4px**（逐帶比對 MAE 0.00，冇其他像素變化） |
| 標題層級 | section 標題全部 `h3` → `h2`（DashHome 6／JournalHome 2／MobileHome 3／RightPanel 4／Sheet 1）、分析卡 `h4` → `h2`、ConsentGate `h2` → `h1`；`index.css` 8 個 selector 放寬成 `:is(h2,h3)`。chat 結構冇 `ShellTop`，所以 Sidebar 補一個 `sr-only` `h1`（每個 scene 一個） |
| 相縮圖 | `GET /api/photos/{id}?w=` 出縮圖（`photo.thumb_jpeg()`，Pillow `draft()` 唔解全張）。**實測真 data 14 張相：原檔 659.7 KB → `w=192` 118.7 KB（18.0%，省 82%）**；20 張相合計 899.7 KB → `w=192` 170.3 KB、`w=96` 66.4 KB。編碼中位 1.4 ms（w=96）～6.3 ms（w=336）。`w` 係 whitelist `(96, 192, 200, 264, 296, 336)`（其他 400、非整數 422）—— 收任意 int 就等於俾人叫 server 為每個數值重新解碼一次 1024px JPEG。縮圖回 `Cache-Control: private, max-age=604800, immutable` ＋ ETag，原檔路徑完全唔變（Lightbox 照攞原檔） |
| `loading="lazy"` ＋ 尺寸 | 格仔／日記相 `loading="lazy"` ＋ `decoding="async"`（對話氣泡唔 lazy：啱啱 send 完遲出會有「係唔係冇上載到」嘅錯覺）。**`width`/`height` 屬性唔需要**：`index.css` 每個相框都係固定 px ＋ `aspect-ratio: 3/4`，空間一早就留咗。實測（相延遲 1.5 s 先到、PerformanceObserver 收 layout-shift）：手機 home **0.0001**、records **0.00024**、journal **0.00029**、chat **0**（「良好」門檻 0.1） |
| 動效 | `.clip-bar i` 由動 `width` 改 `transform: scaleX()`（`Chat.tsx` 跟住改）、`.skel` 由動 `background-position` 改掃 `.skel::after` 嘅 `translateX`、6 處 `transition: 0.15s` 寫明真正變嘅 property |

### 仍然開住

| 項目 | 為咩 |
|---|---|
| `/api/consult` 串流 | 真實中位 **5.46 s**（最慢 7.36 s）先出第一個字。UI 已經老實講「約 5–10 秒」＋ `aria-live`，但 `graph.stream()` 同逐 node `trace` 已經喺度，串流係最大嘅體感槓桿。要改 API 形狀（SSE）＋前端，係一個獨立 project |

## 8. Gate 現況（修完）

```
backend:  ./.venv/bin/python -m pytest -q         → 289 passed
          ./.venv/bin/python -m eval.run_eval --fake → exit 0（4 scenario 全 PASS）
frontend: npm run ui:check                        → 57 passed
          （typecheck + eslint 0 error + stylelint 0 error + 40 snapshot + axe 12（淺/暗）
            + heading 層級 2 + 互動 5 + 相片模糊 5）
真 app:   iPhone 390×844 同桌面 1280×900 —— console 0 error、失敗請求 0、溢出 0、
          手機 < 44px 0 個、< 12px 只有已批嘅 11px tab label
```
