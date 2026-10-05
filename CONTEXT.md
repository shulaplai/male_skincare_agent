# SkinCoach

單一用戶、local-first 嘅男士護膚教練。呢個 context 存在嘅理由：將「用戶今日皮膚點」變成機器讀得嘅每日紀錄，再用一個唔可以亂講嘢嘅 agent 回答佢。

呢份係**詞彙表**，唔係 spec、唔係設計文件、唔係實作筆記。實作睇 `AGENTS.md` 同 `docs/architecture.md`；決定嘅理由睇 `docs/adr/`。

## 皮膚紀錄（data truth）

**Body part（部位）**：
用戶關心嘅一塊皮膚範圍（面部、背部、手腳…）。每個部位有自己嘅紀錄、記憶同時間線。
_Avoid_: area、region、zone、皮膚部位（用「部位」就夠）

**Conversation**：
一個 body part 嘅容器，亦係 UI 上面嗰條對話。**一個 conversation 就係一個 body part** —— 呢兩個詞喺呢個 domain 係同一樣嘢，唔係兩層。
_Avoid_: thread、session、chat room、部位對話（講緊個 entity 時用 Conversation）

**Entry（紀錄）**：
一日、一個 body part 嘅結構化讀數：`attributes`、`note`、`diet`、`products`、`photos`。係**機器食嗰份真相**。
_Avoid_: day record、check-in record、日記（「日記」係 UI 講法）、log

**Chat message（對話訊息）**：
真係顯示喺對話入面嘅一個 turn，包括 agent 回覆、附帶嘅事件 chip、錯誤狀態。係**顯示用嗰份真相**。
_Avoid_: turn、bubble（bubble 淨係指視覺）、message record

**Check-in（打卡）**：
一個 user turn，而且**帶皮膚證據**（有觀察到皮膚，或者有相／片）。只有 check-in 會寫 Entry。
_Avoid_: report、submission、打卡紀錄

**Attribute**：
固定六個之一（`acne`／`oiliness`／`redness`／`dryness`／`pores`／`texture`），每個 0–3 severity。change detect、persist、timeline、memory 全部只認佢。
_Avoid_: 指標（指標係 Metric）、field、dimension、feature

**Severity**：
一個 attribute 由 0（正常）到 3（嚴重）嘅讀數。**唔係分數** —— 冇加總、冇平均、冇「整體膚況」。
_Avoid_: score、膚況分數、rating、grade

**Metric（指標）**：
一次分析入面，agent 自己寫嘅自由文字觀察（`{key, value, dir}`）。**顯示用**，唔會餵入 change detect／memory／timeline。
_Avoid_: attribute、measurement、stat

**Anchor（基準）**：
最新一日同「上次／約 1 個月前／約 3 個月前」嘅逐 attribute 比較。
_Avoid_: baseline（baseline 指第一個 Entry 嘅讀數）、snapshot、reference point

**Timeline event（時間線事件）**：
一件有日期嘅事（食咗辣、開始用某產品、AI 偵測到一個明顯變化），用嚟解釋皮膚點解變。
_Avoid_: 事件（同 detected event 撞）、log entry、history item

**Correlation**：
「某個原因 → 某個 attribute 變化」嘅觀察，由 timeline 統計出嚟。**唔係因果宣稱**。
_Avoid_: causation、cause、insight（correlation 唔係 memory）

## 記憶（Insight）

**Insight（記憶）**：
agent 對呢個用戶嘅一句斷言，有 kind、tag、direction、confidence。
_Avoid_: memory item、note、finding、fact（fact 係其中一個 kind）

**Kind**：`fact`（用戶真係咁講過）／`derived`（由讀數推導出嚟）／`preference`（低頻出現嘅偏好）。
_Avoid_: `pref`、`inferred`、`stated`、`derived fact`

**Direction**：`problem`（severity ≥ 2）／`normal`（≤ 1）。reconcile 靠 tag + direction，唔靠文字。
_Avoid_: polarity、sign、trend

**Scope**：`conversation`（只關乎一個 body part）／`global`（全身性，例如飲食）。
_Avoid_: local／global 混用；`local` 喺呢個 repo 係指已移除嘅「本地模式」
_Avoid_: 全局（UI 標籤可以，講 entity 用 global）

**Supersede**：
一條新 insight 令舊嗰條唔再有效，但**唔會刪**舊嗰條 —— 用戶要睇得到自己嘅記憶點變。
_Avoid_: delete、overwrite、replace、invalidate

**Decay／expiry**：
`derived` insight 有 30 日後過期。過期嘅唔會再出現喺任何讀取路徑。
_Avoid_: TTL、expire（動詞可以，講個機制用 decay）

**Confidence**：
0–1，由 0.60 起步、每次 reinforce +0.05、上限 0.97。**唔係準確度、唔係機率**。
_Avoid_: score、certainty、probability、accuracy

## Agent

**Consult（問教練）**：
由一個 user turn 到一條教練回覆嘅完整一次運行。
_Avoid_: request、chat、query、consultation

**Analysis**：
`analyze` 階段嘅結構化輸出：`summary`、`metrics`、`attributes`、`tool_calls`、`observes_skin`。
_Avoid_: reading、assessment、diagnosis（呢個 app 唔診斷）

**observes_skin**：
呢個 turn 有冇皮膚證據。**係**寫唔寫 Entry 嘅閘，而且**唔會**俾 `advise` 見到（model 會將欄位名照讀返俾用戶）。
_Avoid_: has_skin、skin_seen、checkin_flag

**Advice**：
`advise` 階段嘅輸出：`reply`（用戶真係睇到嘅正文）、`items`（編號建議）、`disclaimer`、`detected_events`。
_Avoid_: answer、response、recommendation、建議（items 係「建議步驟」，reply 係「回覆」）

**Escalate／轉介**：
deterministic guardrail 判定呢個 turn 要見醫生，所以將回覆換成轉介訊息。**唔係**「agent 覺得嚴重」。
_Avoid_: urgent、dangerous、refer（動詞）、警告

**Guardrail**：
**程式碼**（唔係 prompt）對輸出嘅硬性檢查：醫療主張、劑量、處方成份。
_Avoid_: filter、safety net、moderation、政策

**Trace**：
每個 node 留低嘅 `{node, ms, detail}` 紀錄，解釋答案係點嚟。
_Avoid_: log（log 係 `runs.jsonl`）、debug info、telemetry

**Detected event（自報事件）**：
agent 喺對話入面留意到、**等用戶確認**嘅事：`diet`／`product_start`／`product_stop`。確認之前乜都唔會寫。
_Avoid_: 自動記錄、auto event、inferred event、event（同 timeline event 撞）

**Self-report**：
用戶確認 detected event 之後，由嗰件事件寫入 Entry／timeline／products 嘅動作。
_Avoid_: confirm、apply（`apply_events` 係函數名，唔好當概念）

## 相、片、產品

**Photo（皮膚相）**：
一張上載嘅相。送去分析之前要過 consent。**永遠先模糊顯示**。
_Avoid_: selfie、image、upload、截圖

**Clip（皮膚影片）**：
用戶上載嘅**一條片**。抽格係 backstage 實作，用戶**永遠唔應該**知道「抽咗幾多張」、「格數」、「壓縮」。
_Avoid_: video（`Video` 係 DB model 同名，但對用戶講嘅一定係「片」）、frame、抽格、6 張相

**Product（產品）**：
用戶確認開始／停用嘅一支產品，有自己嘅 `products` row 同一條 fact insight。
_Avoid_: item、SKU、商品（UI 可以用「產品」）

**Ingredient（成份）**：
產品標籤上面一個 INCI 名。字典係**有引文嘅 seed**，唔係完成品；唔可以手寫。
_Avoid_: chemical、active、成分（同一樣嘢，統一寫「成份」）

**Verdict**：`good`／`caution`／`avoid`／`insufficient_info` —— 成份對得上用戶 profile 嘅程度。
_Avoid_: score、rating、grade、result

**Trigger**：
推薦規則要求嘅最低 severity（例如暗瘡 ≥2 才推某成份）。
_Avoid_: threshold、condition、rule（rule 係整條規則）

**Consent（同意）**：
相**可唔可以送去雲端分析**。同「相喺螢幕度畀邊個睇到」（BlurPhoto）係兩件唔同嘅事，兩樣都要。
_Avoid_: permission、privacy setting、opt-in

## 驗證

**Scenario**：
一個 eval case：一句 user text ＋ 期望行為（`expect_escalate`／`expect_contains`／`expect_tool`）。每個 scenario 一定要行自己一個新 conversation。
_Avoid_: test case、fixture（fixture 係 UI 測試嗰套）、example

**Gate**：
一個令 eval **exit code 非 0** 嘅檢查。印得出嚟但唔 gate 嘅數字唔算 gate。
_Avoid_: check、assertion、threshold

**Golden corpus**：
committed、細細份、用嚟量檢索嘅語料。真 corpus 唔會入 repo。
_Avoid_: test corpus、sample data、語料（講 eval 嗰份時用 golden corpus）

**FakeLLM／確定性核心**：
FakeLLM 令 harness 離線行到，但佢**唔會讀 prompt** —— 所以「`--fake` 綠」證明唔到 model 行為。
_Avoid_: mock（mock 係 pytest 手法）、stub LLM、offline mode

**Judge**：
LLM-as-judge 評分（具體性／相關性／安全）。**唔係 gate**，但會印落報告。
_Avoid_: evaluator、grader、評分器

## 介面結構

**Layout（結構）**：
四套整體排法之一：`chat`／`journal`／`dash`／`mobile`。用戶揀邊套，唔係 agent 揀。
_Avoid_: theme（theme 係日／夜）、design、skin、版式

**Shell**：
渲染某一套 layout 嘅 component。`layout-<id>` 係 app 上嘅 class；`shell-*` 係 shell 內部嘅容器，兩者唔可以同名。
_Avoid_: layout component、frame、wrapper

**Scene**：
一個**真 page**（`home`／`chat`／`records`／`progress`／`settings`／`guide`），寫入 URL。唔係 component state。
_Avoid_: view（`View` 係舊 type，同 `ShellScene` 重疊，新 code 用 ShellScene）、screen、tab、頁面（講 URL 參數時用 scene）

**Tab**：
底部／頂部 bar 上面嘅 scene 入口。**`guide` 冇 tab 但一樣係 scene** —— 「有冇 tab」唔等於「係唔係 page」。
_Avoid_: nav item、menu entry、button

## 呢個 domain 唔存在嘅嘢（唔好用）

- **本地模式／local mode**：2026-10-01 移除。任何地方見到呢個詞都係殘留（仲有一句喺 `consent_off` 分支嘅 prompt 度）。
- **整體膚況分數**：app 冇呢個概念。`mobile` home 個環形進度係「今日記低咗幾個指標（0–6）」，唔係分數。設計樣板入面嗰個「膚況 2/3」係樣板自己發明。
- **診斷／diagnosis**：呢個 app 唔診斷，只做日常護理建議；醫療問題一律轉介。
- **抽格／格數／幾張相**：backstage 實作，唔可以 leak 俾用戶。
