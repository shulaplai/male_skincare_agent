# 用戶試用報告（2026-09-30）

> 做法：**唔睇 code、以普通用戶身份**由零行一次完整流程（首次開啟 → 打卡 → 影相／片 → 雲端
> vision → 記憶／時間線 → 商品評估 → 指南 → 設定／匯出／刪除 → 四套 layout → 手機窄屏），
> 逐格紀錄「通過／失敗＋證據」。同一批 claim 對照 `docs/status-vs-claims.md`。
> 全部經真瀏覽器（headless Chromium 1280×900 及 390／760／761px）、真 LLM、真 DB。
>
> 相關：`docs/open-findings.md`（前兩輪審計）、`docs/user-notes.md`（你自己試用時撞到嘅問題就寫落嗰度）、`docs/demo-script.md`（demo 流程）。

---

## 0. 試用環境（可審計）

| 項目 | 值 |
|---|---|
| 試用對象 | **工作樹**（唔係 HEAD）：`42b4ccc` + 53 個未 commit 檔案，`git status --porcelain` md5 `e9f6225f9b32d97fcc6ff0a1bf8f5027`（試用開始時） |
| 真 DB | `backend/data/skincoach.db`，md5 `40823465d6041edf11c05a44f07d88b9`（**全程冇被試用 backend 打開過**；備份 `skincoach.db.bak` md5 相同） |
| 試用 DB | `/tmp/skc-trial/trial.db`（獨立）＋ data dir `/tmp/skc-trial/data` |
| Backend | `:8001`（`SKINCOACH_DATABASE_URL`／`DATA_DIR`／`RUN_LOG_PATH` 全部 override 去 `/tmp`） |
| Frontend | `:5173` Vite（**冇改過** `vite.config.ts`，所以試用 backend 一定要佔 8001） |
| 真 LLM | 14 次 consult（其中 **2 次**有 vision）；每次 generate 4–5.5 秒，`analyze` node 平均 ~2.4 秒 |
| 素材 | 用戶提供 6 張 WhatsApp 相（1536×2048、EXIF 0 tags）＋ 1 條 12.43 秒片（478×850、30fps、2.5MB）；合成樣本另計（見 §5） |
| 證據 | 截圖 `/tmp/skc-trial/shots/*.png`、run log `/tmp/skc-trial/runs.jsonl`、逐步 JSON `/tmp/skc-trial/p*_out.json` |

試用期間**冇改過** `.env`、`archive/skinfile/`、DB schema、API response shape。

---

## 1. 一句總結

**核心 agent 比預期紮實**：真 vision、consent gate、Entry 閘門、4 個 guardrail case、
影片抽格／壓縮／上限、四套 layout、空態誠實度 —— 全部實測通過，冇一個係「文件講得靚」。

**但有三個 P1 係用戶一用就撞到**：桌面對話一長（≈5 條訊息）**輸入框跌出畫面 10,000px**；
**iPhone 預設嘅 HEIC 相上載直接 500**；**第一次純文字打卡，教練會講「呢張相已經幫你建立咗
baseline」（用戶根本冇俾相）**。三個都已修＋驗證。

**之後用戶真係用手機連上嚟用，即刻撞到第四個 P1**（**手機版對話完全 scroll 唔到、輸入框唔喺畫面**，
§3 P1-4）—— 同 P1-1 同一個 CSS family，已修＋重新驗證。**教訓**：上一輪「窄屏實測通過」只量咗
page 層同 2 條訊息嘅短 thread，唔夠。**

另外兩個 P2 唔應該由我單方面決定，所以**冇改**：**同日 Entry 會被後一條含糊訊息整條覆蓋**
（實測 acne 2→1、oiliness 1→0，再連鎖到 memory 同商品評估 good→caution）；**偵測到嘅
「我留意到…✅ 記低」chips reload 就消失**（diet 事件永遠確認唔到 → 因果時間線餵唔到料）。

---

## 2. 實測通過（每個都有證據，唔係「應該冇問題」）

| 測咩 | 實測結果 |
|---|---|
| **真 vision**（雲 ON ＋ 用戶真相） | `vision_used: true`、`vision_reason: "used"`、`images_loaded 1`、badge「👁 已睇相分析（雲端）」；回覆內容對得上相（T 字位油光、下巴／人中幾粒、鼻翼毛孔）并引用記憶 |
| **本地優先**（雲 OFF ＋ 有相） | `consent_off`、`vision_attempted: false`、`images_loaded 0` → **相真係冇送出**；UI 出 warn chip |
| **Entry 閘門**（T1–T5） | 產品問題／routine 問題 → `entry_written: false`、`insights_created: 0`，唔會用全 0 覆蓋當日讀數 |
| **Guardrail 4/4** | 紅旗（大面積爛／膿水）→ `escalate` banner ＋ 只叫睇醫生、零產品建議；「每日口服抗生素 50mg」→ **`reply` 同 `items` 兩邊都被換成轉介句**；問診斷 → 唔診斷＋轉介；貼 `Tretinoin` 成份表 → 硬停（`forced_by_product_eval`） |
| **影片** | 12.43 秒片 → **6 格**；12 秒**定鏡**片 → **1 格** ＋ 警告文案；21 秒 → 422「21.0 秒超過 20 秒上限」；62MB 4K → 自動壓縮 61MB→5MB、仍然是 6 格；>100MB → **413 加可讀建議**（「…改返 1080p／30fps 或者剪短啲」）；壓縮片檔名 `<id>.c.mp4` 之後**刪得乾淨**（`files_removed: 7`） |
| **RAG** | `search_knowledge` 有跑、回 3 rows（要真 embedder；見 §5 註） |
| **商品評估（chat 內）** | 貼真 INCI → 結構判斷命中、`recognised: 5`、verdict 由程式算、`reply` 完全跟程式事實；tretinoin → 硬停 |
| **四套 layout** | Settings 揀結構即時生效＋`localStorage` persist；`?layout=` preview 生效，preview 期間喺 Settings 揀結構會**清走 URL 參數**（同文件一致）；760px→mobile、761px→desktop |
| **窄屏** | 390／760px：`scrollWidth == innerWidth`（無橫向溢出）、底部 tab bar 齊、只喺窄屏 16px 輸入（防 iOS zoom）；journal／dash／mobile **頁面層**冇縱向溢出。⚠️ **更正（P1-4）**：呢一列只量咗 page 層，而且當時 thread 只有 2 條訊息 —— 用手機同 6 條訊息（4,166px）再量就揭到 chat scene 嘅 `.thread` 完全冇得 scroll、輸入框喺 3,400px 以下。**「冇溢出」唔等於「撳得到」。** |
| **空態誠實度** | 全部「未有指標／未有記憶／未有事件」；指南用 3 個「未加圖片」佔位、**0 張假圖**；冇 demo 數混入 |
| **匯出** | zip 有 19 張相 ＋ 3 條片；**default config 下亦有 `skincoach.db`**（實測） |
| **刪除** | entry／insight／相／conversation 都刪 row ＋ file；`delete_conversation` 會連未 attach 嘅抽格都清（`files_removed: 7`） |
| **Console** | 正常操作 0 console error、0 warning |

---

## 3. P1（阻斷／明顯，已修）

### P1-1 桌面對話一長，輸入框跌出畫面 ~10,000px ⭐最嚴重

**重現**：桌面 1280×900，同一個 conversation 傾到 26 條訊息 → 量到
`document.scrollingElement.scrollHeight = 10771`、`innerHeight = 900`、`.compose` bottom = 10771。
即係**成頁 scroll、input 沉到最底**，sidebar 同右欄（記憶／時間線）跟住整頁捲走；
`.thread` 有 `overflow-y: auto` 但**永遠唔會自己 scroll**。

**機制**：`.app` 係 grid（`240px 1fr 330px` ＋ `height: 100dvh`），但三個 child
（`.side`／`main.chat`／`.right`）嘅 `min-height` 都係 `auto`（grid item 預設），所以內容一過
一個畫面，**implicit row 就跟住長**（`grid-template-rows: 10771px`）。journal／dash 用
`.shell-main`（有 `min-height: 0`）所以冇事 —— 得 chat shell 中招。**唔係工作樹 regression**：
`git show HEAD:frontend/src/index.css` 嘅 `.app` 一模一樣（`.chat` 亦只有 `min-width: 0`）。

**已修**（`frontend/src/index.css`）：`.app > * { min-height: 0; }`。
**驗證**：同一個 26 訊息 conversation → `scrollHeight = 900 = innerHeight`、`appRows = 900px`、
三個 child `min-height: 0px`、`composerInView: true`，`.thread` 內部 scroll
（scrollHeight 8532 vs clientHeight 747）。截圖 `p7-fix-desktop.png`。

> 觸發門檻實測：注入氣泡 3 個仍 OK（doc 900），5 個 → doc 995、composer 出畫面。
> 即係**傾兩三個來回就會開始**，唔係極端情況。

### P1-2 iPhone 預設 HEIC 相上載 → HTTP 500

**重現**：用 `sips -s format heic` 由用戶相造一個真 HEIC，經 UI 上載 →
**HTTP 500 `Internal Server Error`**，composer 顯示「✗ 上傳失敗：HTTP 500」。
同樣情況：非圖檔改名 `.jpg` → 500；0 byte → 500。（後端冇 `pillow-heif`，`PIL.Image.open`
拋 `UnidentifiedImageError` → 冇人接 → 500；而 **HEIC 係 iPhone 相機預設格式**。）

**已修**（`app/photo.py` 加 `UnreadableImage`；`app/main.py` 接住 → **415**）：

> 呢個檔案唔係我讀得到嘅圖片格式。如果係 iPhone 相簿嘅 HEIC／HEIF，可以先喺「設定 → 相機 → 格式」揀「最相容」（會存成 JPG），或者分享張相做 JPG 再上載。

**驗證**：同一個 HEIC → 415、UI 顯示上面嗰段可讀訊息。新 test：`tests/test_upload_errors.py`。
**未做**：原生食 HEIC（要新依賴 `pillow-heif`）→ issue [#24](https://github.com/shulaplai/male_skincare_agent/issues/24)。

### P1-3 首次**純文字**打卡，教練聲稱睇過相

**重現**：全新 conversation，第一條訊息係純文字（「今日下巴爆咗兩粒瘡，T字位好油」），
run log 記 `has_photo: false`、`vision_used: false`、`vision_reason: "no_photo"`，但回覆係：

> 「…呢張相已經幫你建立咗 baseline——之後每次影相，我都會同今日呢組數字比較…」

**成因唔係 model**：`prompts.build_advise_prompt` 嘅 `first_checkin` 分支無條件寫
「呢個係用戶嘅第一個紀錄／**第一次上載皮膚相**」＋「**呢張相**會成為佢嘅 baseline」，而
`first_checkin` 只代表「呢個對話未有 Entry」——純文字打卡一樣符合。呢個係已修 #15
（明明有相讀唔到卻講「本地模式」）嘅鏡像：兩者都係令 agent 對用戶自己 upload 嘅嘢講假話。

**已修**（`app/agent/prompts.py`）：由 `vision_reason` 決定措辭。無相版本明確寫
「佢冇俾相你睇…唔好講『呢張相』…唔好叫佢補相」；有相版本保留 baseline 講法。
**驗證**：同一個 scenario 再跑一次真 LLM → 「睇你今次打嘅文字，我讀到兩個訊號…」、
「我已經幫你建立咗今次嘅 baseline…之後你每次影相**或者打幾隻字**，我都會同今日比」、
badge「✍️ 文字分析（未睇相）」→ 假宣稱消失，相變成「將來可以」而唔係「已經」。
新 test：`tests/test_prompt_photo_claims.py`（兩個分支＋consent_off note）。

### P1-4 手機版對話 scene：完全 scroll 唔到、輸入框唔喺畫面（**用戶喺真手機上撞到**）

**重現**（390×844，`app layout-mobile`，真 thread 6 條訊息／內容 4,166px）：`.shell-scene`
clientHeight 736，但 `.chat` height **4237**；`.thread` clientHeight 4166 ＝ scrollHeight 4166
（`threadScrollable: 0`）、`.thread.scrollTop` 點寫都係 0；`.compose` top/bottom ＝ **4221/4292**
（viewport 844，即係喺 3,400px 以下）；`window.scrollY` 永遠 0，`.app.layout-mobile` 係
`overflow: hidden` ＋ `.app` `height: 100dvh` → **用戶唯一可以做嘅係睇住最舊嗰幾條訊息**：
向上冇得拉、向下冇得拉、打字框摸唔到。截圖 `m1-before.png`（modlens：「NO MESSAGE COMPOSER
IS VISIBLE … There is no text input field, no send button…」）。

**機制**：`.chat` 同時係兩種容器嘅 item —— `ChatShell`（桌面）同 `StandardShell`（journal／dash）
係 `.shell-chat`（**grid**），`MobileShell` 係 `.shell-scene`（**flex column**）。`.chat` 只有
`min-width: 0`，**冇 `min-height: 0`**，而兩個容器都會將 `min-height: auto` 解析成「內容高度」：

| 容器 | 量到 |
|---|---|
| `.shell-scene`（flex column，390 mobile） | `.chat` 4237px（scene 736px）→ `.thread` 冇 overflow |
| `.shell-chat`（grid，390 `?layout=journal`） | `gridTemplateRows: 4523.69px` → `.chat` 4524px、`.compose` top 4630 |

即係同 **P1-1 同一個 family**：P1-1 修嘅係 `.app` 嘅 grid children（`.side`／`.chat`／`.right`），
呢個係 `.chat` 自己喺再落一層嘅同一個問題。桌面 1280 實測冇事（`.chat` 900px ＝ row 高度、
`.thread` 內部 scroll）—— 所以呢個 bug **只喺窄屏／手機版出現**，而我上一輪試用冇抓到，係因為
當時 thread 仲短（2 條訊息）＋我只量咗 page 層（見 §2「窄屏」一列嘅更正）。

**已修**：
1. `frontend/src/index.css`：`.chat { min-height: 0 }`（base rule，兩個容器一齊修）；加上
   `.shell-scene > .view, .shell-scene > .chat { flex: 1 1 auto; min-height: 0 }`
   —— scene 嘅內容一定要「填滿 ＋ 准許縮細」。
2. `frontend/src/components/Chat.tsx`：**跟住最新一句**。`.thread` 係內部 scroll 容器（唔係 window
   scroll），以前 reload 完永遠停喺最舊一條。而家用 `useLayoutEffect`（換對話／有新訊息／發送中）
   ＋ `onScroll` 判斷「用戶係唔係仲跟住底部」＋ `<img onLoad>` 重新 pin（相係 async 載入，
   未 pin 之前 1280 實測 max 2429、載入完 3147）。用戶自己向上睇歷史時**唔會**被搶走位置。

**驗證**（`m2_after.py` 量 box chain ＋ 真 wheel gesture；`m4_mobile_send.py` 用手機 viewport 打字／發送，
`POST /api/consult` 用 mock intercept，**真 DB 完全冇寫入**）：

| 情境 | 修前 | 修後 |
|---|---|---|
| 390 mobile chat | scrollable 0、compose top 4221 | scrollable **3501**、compose 720–791、開喺最新一句；wheel 3501→2701→3501 |
| 390 `?layout=journal` chat | scrollable 0、compose top 4630 | scrollable **3865**、compose 765–844 |
| 390 `?layout=dash` chat | 同上 | scrollable **3865**、compose 765–844 |
| 1280 chat（桌面，本來 OK） | — | scrollable 3147、**冇回歸**（immediate 同 settled 都 3147） |
| 1280 `?layout=mobile` preview | 同 mobile 一樣壞 | scrollable 3430、compose 847–900 |
| 390 今日／記錄／進度／設定 | — | `scene.scrollH == clientH`，冇溢出、tab bar 齊 |
| 手機打字＋發送 | — | 打字入到、typing bubble 同回覆都 pin 到底（3678→3987）、console 0 error |
| 用戶向上睇歷史時有新訊息 | — | scrollTop 保持 2487（**唔會**被拉返底部）；自己一發送就跳返底部 |

截圖：`m2-chat.png`（修後手機版對話＋輸入框）、`m4-typing.png`、`m4-reply.png`、`m2-d1280-chat.png`。

---

## 4. P2（明顯磨擦／資料質量）

### P2-1 同日 Entry 被後一條含糊訊息整條覆蓋（**未修，要你決定**）

**實測鏈條**（trial DB，全部真 LLM）：

1. 「今日下巴爆咗兩粒瘡，T字位好油」→ Entry：`acne=2, oiliness=1`（+6 條 derived memory）。
2. 之後一條訊息「尋晚打邊爐食咗辣底，今朝**爆多咗兩粒**」→ `entry_reused: true`，但
   `graph.py:368-370` 係**整條覆寫**（`entry.note`／`metrics`／`attributes` = 今次 analyze 結果），
   而 ANALYZE 對「未提及嘅 attribute」一律畀 0 →
   結果 `{acne: 1, oiliness: 0, redness: 0, …}`、`note` 亦被換成呢句含糊訊息。
3. 連鎖：`/summary.anchors` 由 acne 2 變 1；6 條 memory 用**被抹低嘅數值**去 strengthen
   （`insights_strengthened: 6`）；**商品評估由 `good` 變 `caution`** —— 因為
   `recommend.TRIGGER_FLOOR = 2`，acne 跌到 1 → 冇 trigger → `matched: []`。
   我用純函數對照過：`{acne:2, oiliness:1}` → `good, matched ['水楊酸']`；
   `{acne:1}` → `caution, matched []`。同一支含 Niacinamide ＋ Salicylic Acid 嘅產品。

**點解唔自己修**：`observes_skin` 閘門只擋「完全唔觀察皮膚」嘅訊息；一條**部分觀察**嘅訊息
應該點同當日已有讀數合併（取 max？只覆蓋有講嘅 attribute？分早晚兩次紀錄？）係**產品語意決定**，
唔應該由 agent 揀。→ issue [#21](https://github.com/shulaplai/male_skincare_agent/issues/21)。

### P2-2 「我留意到…✅ 記低」chips reload 就冇（**未修，要你決定**）

**實測**：`RUN2`（含「食咗辣底」）trace `detected_events: 1`、UI 出 chip
「🍜 尋晚打邊爐食咗辣底 ✅ 記低」；撳「✅ 記低」→ timeline 1 條、`correlations.cause_episodes: 1` ✓。
但**reload 之後 `chips_after_reload: 0`** —— `App.tsx:165` 只由即時 response 拎 events，
`format.ts fromServerMessage` 唔會還原，server 亦冇保存 pending event。

**後果**：用戶一 reload／隔日再開／中途熄 app，嗰個事件就**永遠確認唔到**；timeline 同
correlation（產品核心賣點「食辣 → 爆瘡」）唔會累積。→ issue [#22](https://github.com/shulaplai/male_skincare_agent/issues/22)。

### P2-3 `成份係 Aqua, …` 令「水」變成認唔到（**已修**）

**實測**：用戶貼「呢支 toner 成份係 Aqua, Glycerin, Niacinamide, Salicylic Acid, …」→
`product_eval` 回 `recognised: 5, unknown: 1`，而教練同用戶講：

> 「成份表第一個係「Aqua」（水），係我程式未認得嘅寫法」

**成因**：`strip_list_marker` 只剝「成份」再 `lstrip("：:")`，所以廣東話自然寫法嘅「係」
黐住第一個成份 → token `係 Aqua`。舊 test 只蓋「成份：」（已修過嘅 case），冇蓋「成份係」。
**已修**（`app/agent/ingredients.py`）：剝完 marker 再剝連接詞（係／是／有／包括／包含／如下／為／
are／is／includes），只剝 CJK function word，所以唔會食到拉丁 INCI 名。
**驗證**：同一句 → `unknown: 0`。新 test 7 個變體 ＋ 一個「唔好誤食 Isopropyl」test。

### P2-4 雲 OFF 時回覆講成「系統讀唔到」

**實測**（雲分析 OFF、有相）：trace 正確（`consent_off`、`images_loaded 0`），但回覆係

> 「今次張相我系統讀唔到內容（**本地模式下載入唔到影像**），所以暫時冇得靠相做評估」

即係把**用戶自己嘅私隱設定**講成故障，亦冇叫用戶開 ☁️（用戶只會覺得 app 壞咗）。
**已修**（prompt 措辭）：同時列出「用『本地模式』解釋」＋「唔好講讀唔到／載入唔到」＋
「可以提佢撳 ☁️ 開雲分析」。新 test 封住。

---

## 5. P3（磨擦／次要）

| # | 觀察 | 狀態 |
|---|---|---|
| P3-1 | **上載完但冇送出嘅相永久殘留**：trial DB 一次試用就 15 個 orphan jpg（disk 有、`photos` 表冇 row，UI 亦冇任何方法刪）；repo 現有 `backend/data/photos` 都係同一形狀（6 個 orphan、`photos` 表 0 行）。用戶 attach 完再撳 ×／行開，檔案就永遠留喺機 | 未修（清理政策 → issue [#23](https://github.com/shulaplai/male_skincare_agent/issues/23)） |
| P3-2 | **刪 entry（連相）之後，對話歷史仲引用被刪嘅相** → 4 個 `GET /api/photos/<id>` 404、thread 出爛圖（`ChatMessage.payload.photos` 唔會跟住清） | 未修 |
| P3-3 | **多相上載只顯示第一張**：attach 2 張（UI 唔支援一次揀多個，`input` 冇 `multiple`）→ consult 收 2 張、`images_loaded: 2`、vision 兩張都睇到，但**用戶自己個 bubble 只 render `photos[0]`**，reload 後亦係（`App.tsx` / `format.ts`） | 未修 |
| P3-4 | 兩個相機圖示掣行為**完全一樣**（同一個 hidden file input，冇 `capture`）→ 手機上唔會直接開相機 | 未修 |
| P3-5 | 招呼語永遠係「早晨呀 ☀️」（實測 19:5x） | 未修 |
| P3-6 | send 緊嘅時候撳 Enter **靜靜被丟**（`submit()` early-return）：draft 留得住但冇任何提示；button 係「處理中…」（disabled） | 未修 |
| P3-7 | 影片格式錯 → 422 但 `detail` 塞咗**成個 ffmpeg banner（~1.6KB，含 build flags 同 server 路徑）**，UI 照 render 落 composer | **已修**（短訊息＋detail 入 log） |
| P3-8 | EXIF orientation 被丟：source 2048×1536 ＋ `orientation=6` → 存成 1024×768、EXIF 0，**讀返張相係側躺**（用 vision bridge 讀確認 ~90°），即用戶預覽同 vision 睇到嘅都係打側嘅面 | **已修**（`ImageOps.exif_transpose`）＋ test；⚠️ 未用真 iPhone 驗 |
| P3-9 | 匯出：DB 唔喺 `SKINCOACH_DATA_DIR` 之內就**唔會入 zip 亦冇警告**（我自己 trial config 就係咁；**default config 實測有 `skincoach.db`**）。匯入只有 API、冇 UI，而且 running server 匯入後要重啟才見到效果 | 未修（doc note） |
| P3-10 | 產品評估 `unknown` 比例高（seed 字典 31 個；真 INCI 表 20–40 項）—— 呢個係已知 D4，行為**老實**（照實講認唔到），唔算 bug | 已知 |

---

## 6. 已改嘅檔案同 gate

| 檔案 | 改咗咩 |
|---|---|
| `frontend/src/index.css` | `.app > * { min-height: 0 }`（P1-1，附註解寫明量到嘅數字）；`.chat { min-height: 0 }` ＋ `.shell-scene > .view, .shell-scene > .chat { flex: 1 1 auto; min-height: 0 }`（P1-4） |
| `frontend/src/components/Chat.tsx` | 跟住最新一句：`useLayoutEffect` ＋ `onScroll` pinned ＋ `<img onLoad>` 重新 pin（P1-4） |
| `backend/app/photo.py` | `UnreadableImage`；`compress_image` 加 `ImageOps.exif_transpose`（P1-2、P3-8） |
| `backend/app/main.py` | `/api/photos` 接 `UnreadableImage` → 415 ＋ 可讀廣東話訊息（P1-2） |
| `backend/app/video.py` | `UNREADABLE_CLIP` 短訊息；ffmpeg 全文入 log（P3-7，兩處 decode path） |
| `backend/app/agent/ingredients.py` | `_LIST_CONNECTORS`（P2-3） |
| `backend/app/agent/prompts.py` | `first_checkin` 由 `vision_reason` 決定措辭（P1-3）；consent_off note 講清「本地模式」＋點開 ☁️（P2-4） |
| `backend/tests/test_upload_errors.py`（新） | 非圖／截斷 JPEG／HEIC payload → 415；EXIF orientation；影片錯誤訊息長度同內容；API 層 422 detail 唔含 banner |
| `backend/tests/test_prompt_photo_claims.py`（新） | 純文字首次打卡唔可以宣稱有相、唔可以反過來講「睇唔到」；有相時保留 baseline；consent_off note 內容 |
| `backend/tests/test_ingredients.py` | ＋7 個 marker 變體 ＋1 個「唔好誤食拉丁成份」 |

**三個 gate（最後一次全部行過）**
- `./.venv/bin/python -m pytest -q` → **245 passed**（原 226，新增 19）
- `backend`：`./.venv/bin/python -m eval.run_eval --fake` → **exit 0**（RAG recall 100%／hybrid 100%／4 個 agent scenario PASS）
- `frontend`：`npm run typecheck` ✓、`npm run build` ✓

CSS 改動**冇**自動化測試（`frontend` 冇 test runner，#12 未決）→ 用真瀏覽器量度做證據（§3）。

---

## 7. 未能驗證（誠實列出）

1. **真 iPhone**：本機冇真機。HEIC 用 macOS 造嘅真 HEIC、EXIF 用合成 fixture（raw pixels 打側 ＋
   真 orientation tag）。**iOS 實機上 Safari 送出嚟嘅檔案係咩形態未驗**。
   （後補：用戶真係用 iPhone 連 LAN 用過 —— 唯一揭到嘅係 **P1-4 手機版對話 layout**，即係
   Safari／真機相容性冇爆新嘢；但 iOS 鍵盤彈出時 `100dvh` 嘅行為、同 Safari 送出嚟嘅相／片
   檔案形態，**到今日仍然未驗**。）
2. **真手機 4K 片**：62MB／106MB 樣本係用 bundled ffmpeg 由用戶條片合成（真 4K 未驗）；
   壓縮路徑本身有確定性測試。
3. **用戶素材係 WhatsApp 重壓版**（縮到 478×850、EXIF 已清）→ 覆蓋唔到「原檔直出」情境。
4. **未試**：Docker compose、真-embedder eval（0.22GB model）、import 完整還原時序、
   真 LLM-as-judge。
5. **True embedder 註**：今次 trial 一開始 fastembed 下載失敗（cache 寫唔到）→ 靜靜降級 128 維
   hash embedder；我改用 `SKINCOACH_EMBEDDER_CACHE_DIR` ＋ `HF_HOME` 指去可寫目錄之後行返
   384 維（`length(embedding)` 8299 vs 2551）。**RAG 質素相關嘅結論都係用 384 維行嘅**。
   順帶一提：降級係有 log 亦入 trace，但 `/api/settings` 唔會話你聽用緊邊個 embedder。
6. 我試用嘅係**未 commit 嘅工作樹**，唔係 HEAD。

## 8. 建議下一步

1. **即刻 merge 上面 7 個修復**（4 個 P1 全部係用戶一用就撞到）。
2. **處理已開嘅 4 個 issue**：[#21](https://github.com/shulaplai/male_skincare_agent/issues/21) 同日合併政策、[#22](https://github.com/shulaplai/male_skincare_agent/issues/22) chip 保存、[#23](https://github.com/shulaplai/male_skincare_agent/issues/23) orphan 清理、[#24](https://github.com/shulaplai/male_skincare_agent/issues/24) HEIC 原生支援 —— 全部係產品／依賴決定。
3. 想我再補：P3-2（刪 entry 連 chat 引用）、P3-3（多相顯示）、P3-5（時間招呼語）都可以即刻做。
4. 如果要寫入 demo video，**記得先修 P1-1**：demo 會傾好多條，舊 code 20 條訊息之後
   input 就唔喺畫面，screen record 會出事。用手機（或者窄屏）錄就更加要先修 **P1-4**。
