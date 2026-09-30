# 商品推介／商品評估 —— 預備文件（**未執行**）

> 狀態：**設計已定，一行 code 都未改**。呢份文件係「預備定要解決」，等你想落手嗰陣可以照住做。
> 寫喺度嘅每個「現況」都係實際 grep／跑過，唔係估。冇改過嘅行會寫明「未改」。
> 相關 open items：`docs/open-findings.md`（S1／S2 出處）、status-vs-claims #25（UI 結構，同本文件無關）。

## 0. 已定決策（2026-09，用戶決定）

| 決定 | 內容 |
|---|---|
| **推介粒度** | **只出成份 ＋ 規格**，唔出品牌。例：「搵一支 2% 水楊酸 BHA 精華」＋「乾燥或者泛紅時改用 10% 杜鵰花酸」。**唔建商品目錄。** |
| **成份表來源** | **用戶自己貼**（INCI 文字）。唔上網抓 —— 見 §1 架構約束。 |
| **商品審核／上架批准** | 唔做（唔需要人手 curate 商品庫）。 |
| **Pi agent** | 唔理住（唔關本文件事）。 |
| **S1／S2** | 先預備，唔執行。 |
| **D1 處方分類機制** | **唔用處方黑名單做主要機制**。核心檢查改為 **coverage matching**：「我推薦你嘅成份，呢支產品有冇齊？」理由見 §3.5（corpus 自己證明「成份 → 處方」分唔清） |
| **D1 推介層次** | **主選 ＋ 次選**兩層，俾用戶自己揀。主選＝最多證據嘅成熟成份；次選＝特殊情況（乾燥／泛紅）改用嘅替代成份 |
| **D2 規則表正確性** | ✅ **已對 corpus 驗證**（§3.2a），揭發兩個 gap，兩個都補 |
| **D3 verdict** | 啱：只出 `good / caution / avoid / insufficient_info`，**唔出分數、唔出價錢比較** |
| **D4 成份清單** | **≥200 個**，由中國《已使用化妝品原料目錄》(IECIC) 揀。⚠️ corpus 撐唔到（`incidecoder.com` 只有 8 個）。**唔可以手寫**，見 §6 |
| **D5 語言** | 英文 INCI 同中文都收；**回答時盡量用對應中文名**（所以每個成份都要有 zh display name） |

---

## 1. 架構約束（唔可以繞）

`docs/architecture.md:19` 同 `docs/blog-post.md:86` 明文：

> Tool whitelist｜agent 只可 call whitelist 工具（`get_skin_profile`/`get_recent_entries`/`search_knowledge`），**冇任意外部 URL／代碼**｜唔會越權
>
> **冇任意外部 URL、冇代碼執行。呢個係「agent 唔會越權」嘅結構性保證 —— 唔係靠 system prompt 講「你唔好亂咁嚟」。**

推論（呢三點決定咗整個設計）：

1. **唔可以 fetch 商品頁／成份表／價錢。** → 成份表必須用戶輸入。
2. **唔可以加一個「web search」tool 去查商品。** → 唔講品牌，只講成份／類別。
3. **任何「成份 → 適唔適合」嘅判斷，都要係我哋自己嘅 code／資料**，唔可以叫 LLM 自由回憶（咁就變咗幻覺來源）。

---

## 2. 現況（已 grep 驗證）

### 2.1 「唔會推介商品」唔係一條寫死嘅規則

grep `prompts.py` / `guardrails.py` / 全部 `docs/` —— **冇任何地方禁止推介商品**。
`ADVISE_SYSTEM`（`app/agent/prompts.py:33-44`）只寫「唔開藥、唔俾劑量、唔診斷疾病」。

所以係 **emergent（冇渠道）**，唔係 policy：

| 原因 | 實際情況 |
|---|---|
| RAG corpus 冇**商品目錄** | 生產 corpus 係成份／臨床知識，唔係可查嘅商品庫。真 DB 有 **3220 chunks**：`coolsis.cool-style.com.tw`（248）、`PMC12936241`（83）、`dermnetnz.org`（73）＋多篇 PMC 論文。committed 種子係 `backend/corpus/`（`zh_skincare_basics.txt` ＋ `zh_sources_curated.txt` ＋ `sources.txt` 來源清單）；大 corpus 喺 gitignored `data/corpus/`（2 個 PMC XML）。**冇價錢、冇庫存、冇商品 id**，而且 §1 話咗唔可以 fetch 新嘢 |
| 冇 tool 回商品 | `tools.WHITELIST` 只有 3 個 |
| Prompt 冇叫佢推介 | `ADVISE_SYSTEM` 冇提 |
| 結構上冇能力 | §1 |

**結論：加推介唔需要拆任何 guardrail。**

### 2.2 `products` table 有兩個欄位係死嘅

```python
# app/models.py:162-177
class Product(Base):
    id, conversation_id, name
    category:    Mapped[str]  = ... default="其他"   # :175
    ingredients: Mapped[list] = ... default=list      # :176  ["水楊酸", ...]
```

`_get_or_create_product`（`app/self_report.py:46`）**只寫 `name`**。
全 repo grep `ingredients` / `.category`：除咗 `models.py` 個定義，**冇任何地方寫入過** → 永遠 `"其他"` 同 `[]`。

**再加一件實測到嘅事**：真 DB（`backend/data/skincoach.db`）嘅 `products` **有 0 行** ——
```
products rows: 0        with ingredients: 0
```
即係連「用戶講自己用緊咩產品」呢條路，喺你真 data 上都未行過一次。所以 `ingredients` / `category` 唔止係「冇 code 寫」，係**完全未 exercise 過**。

`:163` 個 docstring 自己寫住 `Q28: name + category + optional key ingredients` —— **呢個 feature 就係嗰兩個欄位本來設計嚟做嘅事**。

### 2.3 現有產品資料流（已經通）

```
用戶講「開始用 X」→ agent 提 detected_event → 用戶撳 ✅ 記低
  → Product row（name only）                    self_report.py:46
  → Entry.products 引用 id                      self_report.py:137-140
  → tools.get_recent_entries 將 id resolve 返名  tools.py:56-67
  → correlation.py 用 first-use date 做 cause    correlation.py:218-225
  → preferences.py ≥3 日 → preference insight    preferences.py:115-117
```

**「你自己用緊嘅產品」已打通。缺嘅只有「未買嘅產品」。**

### 2.4 一件唔可以撞嘅事

`Entry` 係每日皮膚狀態（data truth）。`change detect`（`attributes.build_change_lines`）、timeline、`/summary.anchors` **全部靠 `Entry` 對歷史做 diff**。
→ **商品評估絕對唔可以寫 `Entry`。** 否則用戶問一句「呢支精華得唔得」就會多一日紀錄，污染 6-attribute 時間線。

`correlation.py:218` 同 `preferences.py:117` 都只認「被 `Entry.products` 引用過」嘅 product，所以評估結果就算落入 `products` 都唔會變 cause；但為免日後有人改咗嗰個條件，**v1 索性唔寫 `products`**（見 §3.4）。

---

## 3. Feature 設計

### 3.1 兩個功能，兩條路

| # | 功能 | 行邊條路 |
|---|---|---|
| F1 | Agent **主動**推介（成份／類別層面） | 加落現有 `advise` 嘅 prompt ＋ 一個新 tool 提供候選成份 → **仍然行 `graph.py` 5-node pipeline** |
| F2 | 用戶**貼商品**俾 AI 評估 | **新 endpoint，唔行 graph pipeline** |

F2 唔行 graph 係硬性要求：`graph.py` 最後一定 `persist`，會寫 `Entry`（§2.4）。

### 3.2 F1：成份／類別層面推介

**做法**：新增 deterministic 函數 `suggest_actives(attributes, insights) -> list[ActiveSuggestion]`，
由 6-attribute profile ＋ 記憶推導出「應該搵咩成份」，再交去 prompt 俾 `advise` 寫成廣東話。

**唔係 LLM 自由發揮** —— 候選成份由 code 揀，LLM 只負責措辭。呢個跟 doctrine #1／#2。

規則表（**已對 corpus 驗證** — 見 §3.2a）

| 條件（來自 `Entry.attributes`） | 建議成份類別 | 理由（寫入 prompt） |
|---|---|---|
| `acne >= 2` | 水楊酸（BHA）／菸鹼醯胺 | 針對毛孔阻塞同油脂 |
| `oiliness >= 2` | 菸鹼醯胺／水楊酸 | 控油、調節皮脂 |
| `dryness >= 2` | 神經醯胺／玻尿酸／甘油 | 補水修復屏障 |
| `redness >= 2` | 積雪草／泛醇（B5）／避免高濃度酸 | 舒緩 |
| `pores >= 2` | 菸鹼醯胺／視黃醇（**非處方濃度**） | 毛孔外觀 |
| `texture >= 2` | 溫和果酸（AHA）／尿素 | 角質代謝 |
| **`dryness >= 2` 同時 `acne >= 2`** | **警告**：唔好同時上高濃度酸，分開早晚或隔日 | 兩個 rule 衝突 → 必須有衝突處理 |
| 已有 `product_use:*` fact 含同類成份 | **唔好再推同一類**（改為提醒疊加風險） | 用 `insights` 嘅 `tag="product_use:..."` |

**衝突處理係必要嘅，唔係 optional** —— 冇佢就會同時叫一個又乾又爆瘡嘅人上酸同補水，而用戶會照做。

### 3.2a 規則表：corpus 驗證結果（**已做**，揭發兩個 gap）

原本上面張表係我寫嘅護膚常識、**冇來源**。用戶要求（D2）對 corpus 驗，我實際抽咗原文。

#### corpus 覆蓋度（真 DB 3220 chunks，grep 實測）

| 成份 | chunks | | 成份 | chunks |
|---|---|---|---|---|
| 視黃醇**類**（retinol／retinoid／tretinoin） | 422 | | 玻尿酸 hyaluronic | 168 |
| 菸鹼醯胺 niacinamide | 243 | | 神經醯胺 ceramide | 147 |
| 水楊酸 salicylic | 213 | | 甘油 glycerin | 66 |
| 果酸**類**（AHA／glycolic／lactic） | 212 | | 尿素 urea | 55 |
| 泛醇 B5 | 34 | | 積雪草 centella | 30 |

（數字係「提及過呢個成份」嘅 chunk 數，用中英＋俗名多個 pattern 查；**可重現指令喺附錄**。注意視黃醇類 422 同果酸類 212 係**一類**而唔係單一成份 —— 兩者都包含處方級別嘅成員，`422` 亦包含 `tretinoin`。）

`incidecoder.com` 係成份字典，但**只有 8 個**：`Salicylic Acid`、`Niacinamide`、`Retinol`、`Panthenol`、`Hyaluronic Acid`、`Alpha-Arbutin`、`Azelaic Acid`、`Glycerin`。

#### ⚠️ Gap 1：漏咗 azelaic acid

`incidecoder.com :: Azelaic Acid` 原文：

> "especially useful for **acne-prone or rosacea-prone** skin types (in concentration 10% and up)"
> "Anti-inflammatory effect → **Anti-rosacea, anti-acne**"

原表 `redness >= 2` 寫「積雪草／泛醇」，但 corpus 有明確記載、專治 rosacea 嘅係 **杜鵰花酸 azelaic acid** → **已補**。

#### ⚠️ Gap 2：完全冇「色素／暗瘡印」維度

`incidecoder.com :: Alpha-Arbutin` 原文：

> "just like its sibling, alpha-arbutin is also a **skin-brightening, depigmenting agent**"

而 corpus 另有 `Melasma (facial pigmentation)`、`Postinflammatory hyperpigmentation`、`Acne Scarring` 三個 dermnetnz 頁。
→ 一個爆完瘡留印嘅用戶，原表一句都答唔到。**已補**。

#### 修訂後嘅規則表（**主選／次選兩層**）

| 條件（`Entry.attributes`） | **主選**（成熟、證據最多） | **次選**（特殊情況改呢個） | corpus 根據 |
|---|---|---|---|
| `acne >= 2` | 水楊酸 BHA | 杜鵰花酸（同時泛紅時） | incidecoder ×2、dermnetnz `Acne` |
| `oiliness >= 2` | 菸鹼醯胺 | 水楊酸 | incidecoder `Niacinamide`、dermnetnz `Sebum` |
| `dryness >= 2` | 神經醯胺 | 玻尿酸／甘油 | incidecoder `Glycerin`、dermnetnz `Dry Skin`／`Skin barrier function` |
| `redness >= 2` | **杜鵰花酸**（← 已補） | 泛醇 B5／積雪草；**避免高濃度酸** | incidecoder `Azelaic Acid`、dermnetnz `Rosacea` |
| `pores >= 2` | 菸鹼醯胺 | 視黃醇（低濃度起步） | incidecoder `Niacinamide`／`Retinol` |
| `texture >= 2` | 溫和果酸 AHA | 尿素 | incidecoder `Salicylic Acid`（BHA 對照）、dermnetnz `Acne Scarring` |
| **`pigmentation`**（← **新維度**） | **α-熊果素 alpha-arbutin** | 杜鵰花酸／傳明酸 tranexamic acid | incidecoder `Alpha-Arbutin`、dermnetnz `Melasma`／`PIH` |
| `dryness >= 2` ＋ `acne >= 2` | **警告**：唔好同時上高濃度酸，分早晚或隔日 | — | 兩個 rule 衝突 → 必須有衝突處理 |
| 已有 `product_use:*` fact 含同類成份 | **唔好再推同一類**，改為提醒疊加風險 | — | `insights` 嘅 `tag="product_use:…"` |

⚠️ **`pigmentation` 唔喺現有 6-attribute schema 內**（`acne/oiliness/redness/dryness/pores/texture`）。跟 doctrine #2，**唔可以自己加第七個 attribute**。三個做法：

1. 由 `Entry.note` 做 keyword 偵測（「留印」「色素」「印」）→ 有提到才觸發
2. 用戶主動講（F2 request 加可選字段）
3. 當「未支援維度」，唔理

**建議 (1)＋(2) 並用，(3) 唔接受** —— 唔做就會對「爆完瘡留印」呢個男士最常見嘅困擾失明。

⚠️ **呢張表係 general cosmetic knowledge，唔係醫療指引。** 每條都有 corpus 引文支持，但 corpus 本身係網頁／論文摘要，唔係臨床指引。UI 一定要出免責聲明（`guardrails.DEFAULT_DISCLAIMER` 已有）。

### 3.3 F2：用戶貼商品評估

**Request**（新 endpoint，照抄 `/facts` 個 pattern，`app/main.py:165`）：

```
POST /api/conversations/{cid}/products/evaluate
{
  "name": "某 BHA 精華",              # 可空
  "ingredients_text": "Water, Salicylic Acid 2%, Niacinamide, ...",  # 用戶貼，INCI 原文
  "category": "精華"                  # 可空
}
```

**流程**（全部 deterministic 先，LLM 最後）：

```
1. 解析成份文字          → ingredients.py: parse_ingredients(text) -> [CanonicalIngredient]
2. 處方／醫療成份檢查     → 命中 → **拒絕 + 轉介，唔交去 LLM**（見 §3.5）
3. 對比用戶 profile      → attributes × 規則表（同一張表，反向用）
4. 對比用戶記憶          → insights（已知敏感／偏好／fact）
5. 對比用戶現用產品      → products × Entry.products（成份疊加）
6. 砌 ProductVerdict      → { worth_buying: bool|null, suitability, conflicts[], missing[], unknown[] }
7. LLM 只負責將 6 寫成廣東話敘述
```

**Response**：

```json
{
  "name": "某 BHA 精華",
  "recognised": ["水楊酸", "菸鹼醯胺"],
  "unknown": ["SomeTradeName"],
  "verdict": "caution",
  "reasons": [
    {"kind": "duplicate_active", "text": "你已經用緊「水楊酸 toner」，再加一支會過度去角質"},
    {"kind": "profile_conflict", "text": "你乾燥 1，建議一星期 2–3 次、之後補保濕"}
  ],
  "narrative": "…（LLM 寫，經 guardrail）…",
  "disclaimer": "…"
}
```

`verdict ∈ { good | caution | avoid | insufficient_info }`。

### 3.4 新資產：`backend/app/agent/ingredients.py`（純函數）

跟 doctrine #6（`prompts.py`／`attributes.py`／`memory.py` 唔可以有 DB／DOM 依賴，eval 直接 import）：

```python
def parse_ingredients(text: str) -> list[CanonicalIngredient]   # 拆 INCI、去重、正規化
def canonical(name: str) -> str | None                          # Salicylic Acid / 水楊酸 / BHA → salicylic_acid
def display_zh(key: str) -> str                                 # → 「水楊酸」（D5：回答盡量用中文）
def is_recognised(key: str) -> bool
```

**為咩要「正規化」**（唔係 nice-to-have，係功能能否成立嘅前提）：
- 用戶可能打中文（「水楊酸」）或者英文（`Salicylic Acid`）或者俗名（`BHA`）
- 同一成份有多個 INCI 寫法
- 「有冇呢個成份」要答得準，就一定要收斂到一個 canonical key

#### 成份清單：≥200 個，來源係 IECIC（D4/D5）

| 項目 | 決定 |
|---|---|
| 數量 | **≥200** |
| 來源 | **中國《已使用化妝品原料目錄》(IECIC)** —— 官方 ＋ **有官方中文名**（啱 D5） |
| 每個 entry 要有 | `canonical_key`、**英文 INCI**、**中文官方名**、`role`（active / emollient / preservative / fragrance / …）、`aliases`（俗名，如 BHA） |
| 影響範圍 | 只覆蓋功能性成份 ＋ 常見基質；**唔會**覆蓋 IECIC 全部（約 8,800 個） |

⚠️ **三個硬性事實**：

1. **corpus 撐唔起 200。** 實測：`incidecoder.com` 只有 **8 個**成份。所以呢 200 個**一定**要外部來源。
2. **我唔可以手寫。** 手寫 200 個成份名（連中文名）＝ 憑空造事實，正正就係你自己審計捉到嘅問題。要由 IECIC 抽，並且**喺檔頭標明版本同來源**。
3. **呢一步需要你／我落手拎 IECIC 資料。** 我喺呢個環境冇 IECIC 檔案，亦唔應該隨便上網抓一個來源不明嘅版本。→ 見 §6 D4。

**`unknown` 成份 → 必須講「我唔認識呢個成份」**，唔可以猜。誠實性要求（doctrine #10 同精神一致）。

### 3.5 唔用處方分類做主要機制（D1）—— 改為 **coverage matching**

我原本設計係「`prescription` 黑名單 → 拒絕／轉介」。**呢個設計係抓錯軸**，而證據係 corpus 自己講嘅：

`incidecoder.com :: Azelaic Acid` 原文：

> "It is **a prescription drug in the US** but can be **freely purchased in the EU** in an up to 10% concentration"
> "**15% is the standard prescription strength dose** for rosacea treatment"

**同一個成份：≤10% 唔使處方、15% 係處方，而且按地區唔同。** 所以「邊個成份算處方」唔係成份層面嘅問題，而係**濃度 ＋ 地區**問題 —— 一個 `Literal["active","prescription"]` 標籤根本表達唔到。

→ **改為 coverage matching**（用戶決定 D1）：

```
用戶貼嘅產品成份   ∩   我哋為佢推薦嘅成份
        ↓
  verdict = good         （推薦嘅成份齊）
  verdict = caution      （有齊但有衝突：濃度、疊加、乾燥）
  verdict = avoid        （同已知敏感／禁忌衝突）
  verdict = insufficient_info（認唔到／冇推薦可比對）
```

而「危險成份」嘅角色**降級為輔助旗標**，唔係主判準：

| 檢查 | 做法 | 出事時 |
|---|---|---|
| 我認識嘅成份？ | `canonical()` 認唔認到 | 認唔到 → 入 `unknown[]`，**唔猜** |
| 有冇齊推薦嘅成份？ | coverage matching | 冇齊 → 講清楚差邊個（呢個就係「值唔值得買」嘅主要答案） |
| 有冇明確禁忌？ | 一個**窄**名單（`tretinoin`／`isotretinoin`／處方級類固醇／口服抗生素） | `verdict: "avoid"` ＋ `ESCALATION_MESSAGE`，**唔交去 LLM** |
| 濃度寫明咗？ | 由用戶貼嘅文字抽 `10%` / `2%` | 抽到 → 可以講「15% 通常要醫生開」（corpus 有寫）；抽唔到 → 唔假設 |
| 同現用產品疊加？ | §3.7 | 出 `duplicate_active` 警告 |

**窄名單同 IECIC 嘅關係**：IECIC 係「已使用化妝品原料」目錄 → **處方藥成份根本唔會出現喺 IECIC**。所以：
- 喺 IECIC **裡面** → 化妝品級，可以做 coverage matching
- 喺 IECIC **以外** ＋ 認唔到 → `unknown`，誠實講唔識
- 喺 IECIC **以外** ＋ 命中窄禁忌名單 → `avoid` ＋ 轉介

咁就唔需要我自己去判斷「邊個成份係處方」（避免 §6 D1 嗰個我唔應該決定嘅問題）—— 用「有冇喺 IECIC」做代理指標。**呢個係 IECIC 做來源嘅額外好處。**

### 3.6 F2 唔做嘅嘢

- **唔寫 `Entry`**（§2.4）
- **唔寫 `products`**：`products` 係「用戶有嘅產品」，一支問過但冇買嘅唔應該入去。v1 **零持久化**（純函數 + 即時回）。
  - 升級路徑（v1.1，唔做）：新表 `product_evaluations` 存歷史，等用戶可以翻查「我上次問過呢支」。
- **唔存「評估分數」**：冇可信嘅評分模型，唔造一個出嚟。
- 相反：**當用戶真係開始用**（`product_start`）→ `_get_or_create_product` 可以順手把評估時已解析嘅 `ingredients` / `category` 帶入 → **`Product.ingredients` 同 `category` 終於有值**。呢個係唯一需要改 `self_report.py` 嘅位。

### 3.7 F2 需要嘅既有產品成份

「同現用產品疊加」需要**現用產品嘅成份**，但 §2.2 已證實係**全部空**。兩個做法：

| 做法 | 評估 |
|---|---|
| (a) 叫用戶補貼現用產品成份 | 麻煩，會 drop-off |
| **(b) 由產品名做 deterministic keyword 匹配**（`水楊酸 toner` → `salicylic_acid`） | ✔ **v1 用呢個**。即時可用、零用戶負擔、可測。名字認唔到就當「未知」，唔猜 |

升級：用戶每次評估之後真係開始用嗰陣，順手把已解析成份寫入 `Product.ingredients` → 之後 (b) 自動變準。

---

## 4. 前置工作：S1（**呢個 feature 嘅 blocker**，唔係獨立 item）

**為何係 blocker**：商品評價正正係最易講出醫療宣稱嘅場景（「呢支可以醫暗瘡」「含 2% 水楊酸，每日搽」）。

### 4.1 現況（已實測）

`apply_guardrails` 只掃 `items`，`check_safety` 一樣，但**用戶淨係睇 `reply`**（`frontend/src/App.tsx:158`：`text: res.advice.reply || res.analysis.summary`）。

實測（`app/agent/guardrails.py` ＋ `eval/safety.py` 直接 call）：

```
情況一：醫療詞喺 items
  escalate: True   items: [ESCALATION_MESSAGE]   reply: 照做就得。            violations: []

情況二：同一句放喺 reply（items 乾淨）
  escalate: False  items: ['保持清潔','做好保濕']
  reply: 「建議你每日口服抗生素 50mg，連續兩星期就會好。」                  violations: []   ← 冇嘢攔到
```

### 4.2 要改嘅精確位置（**未改**）

| 檔 | 行 | 改動 |
|---|---|---|
| `app/agent/guardrails.py` | `:55-58` | 掃描由 `" ".join(items)` 改為 `" ".join([advice.reply, *items])`；命中時 **`reply` 亦要換成 `ESCALATION_MESSAGE`** |
| `app/agent/guardrails.py` | `:61` | `model_copy(update={...})` 加 `"reply": reply` |
| `eval/safety.py` | `:11` | `contains_any(" ".join(advice.items), MEDICAL_TERMS)` → 一樣包含 `advice.reply` |

### 4.3 要加嘅 test（`backend/tests/`）

1. `test_medical_term_in_reply_escalates` —— reply 含「口服抗生素」→ `escalate is True`、`reply == ESCALATION_MESSAGE`
2. `test_medical_term_in_reply_is_flagged_by_safety_check` —— `check_safety` 回 `["advice_mentions_medical_term"]`
3. `test_clean_reply_still_passes` —— 乾淨 reply 唔可以有 false positive（回歸保護）
4. `test_medical_term_in_items_still_escalates` —— 原本行為唔可以爛

### 4.4 驗證方法

```bash
cd backend
./.venv/bin/python -m pytest -q                    # 77 → 81 passed
./.venv/bin/python -m eval.run_eval --fake         # exit 0
# mutation check：把 :56 改返只掃 items，上面 test 1/2 必須 FAIL（唔係綠）
```

### 4.5 ⚠️ S1 修完會**放大** S8

`contains_any` 係 `t in text`（substring，`guardrails.py:41-43`），而 `MEDICAL_TERMS`（`:26-38`）包含 **`"mg"`**。
現在只掃 `items`（短）；S1 修完會連 `reply`（2–5 句長文）一齊掃 → **false positive 面積擴大**。

**所以 S1 同 S8 應該同一個 PR 做**：`MEDICAL_TERMS` 移走 `"mg"`，或者 `contains_any` 加 word boundary（中英混合要小心：中文冇 space）。
驗證：加 test 斷言一段包含 "…mg…" 但冇醫療宣稱嘅回覆**唔會**被 escalate。

---

## 5. 順手：S2（eval scenario 互相污染）

### 5.1 現況（已實測）

`run_agent_eval`（`eval/agent_eval.py:14-25`）三個 scenario **共用同一個 `conversation_id`**，而 graph **會 persist**：

| # | scenario | first_checkin | insights | max_conf | recent_msgs | tool_rows |
|---|---|---|---|---|---|---|
| 1 | acne_normal | **True** | 3 | 0.600 | 0 | 3 |
| 2 | dry_normal | False | 3 | **0.650** | 2 | 6 |
| 3 | red_flag | False | 3 | **0.700** | 4 | 6 |

→ 加／刪／重排一個 scenario 會改動其他 scenario 嘅結果。用 `FakeLLM`（輸出常數）PASS/FAIL 唔會翻，所以 CI 永遠綠。

### 5.2 要改嘅精確位置（**未改**）

| 檔 | 行 | 改動 |
|---|---|---|
| `eval/agent_eval.py` | `:19` | 參數由 `conversation_id: str` 改為 `session_factory`（或者一個 `make_conversation: Callable[[], str]`） |
| `eval/agent_eval.py` | `:21-25` | loop 內每個 scenario 開新 conversation，再 `graph.invoke` |
| `eval/agent_eval.py` | `:25` | invoke state 加 `"cloud_analysis": False`，**同 production 一致**（`service.py:90` 有傳，eval 冇傳 → 初始 state shape 唔同，順手修 S3） |
| `eval/run_eval.py` | `:95` | 跟住改 call |

### 5.3 已驗證：修法安全

我實際跑過模擬（每 scenario 新 conversation）：

```
現況:   3/3 PASS      修法後: 3/3 PASS      gate 結果有冇變: 冇變（安全）
修法後每個 scenario: first_checkin=True, insights=3, tools={get_skin_profile: 0, search_knowledge: 3}
```

### 5.4 ⚠️ 修法有代價：會失去一個（意外嘅）覆蓋

修法前 scenario 2／3 嘅 `get_skin_profile` 回 **3 rows** —— 嗰啲 rows 係 scenario 1 洩漏過去嘅。
修法後所有 scenario 都 **0 rows**，因為全部係新 conversation。

即係：**「coach 有既有記憶」嗰條路，而家係靠意外先被行到，冇任何 `expect_tool` 斷言佢。**
所以 S2 嘅完整修法係**兩步**：

1. 每 scenario 新 conversation（消除次序依賴）
2. **加一個 scenario** 明確 seed 先（先寫 2–3 日 Entry ＋ insights），再 `expect_tool: get_skin_profile` —— 咁「有記憶」嗰條路才有真覆蓋

只做第 1 步 = 由「污染」變成「少測一條路」。要兩步一齊。

### 5.5 驗證方法

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m eval.run_eval --fake
# 新 test：三個 scenario 嘅 first_checkin 全部 True（而家只有 #1）；
#         每個 scenario 之後 insights 數量一樣（唔再累加）
# 注意：真-LLM run 嘅輸出會變 → docs/eval-report-sample.md 要 re-baseline
```

---

## 6. 決定狀態（D1–D5 已答；剩低一個要動手拎資料）

| # | 事項 | 狀態 |
|---|---|---|
| **D1** | 邊啲成份算「處方」 | ✅ **已解 —— 而且係由 corpus 解決**。用一張處方黑名單做主要機制係錯軸（corpus：azelaic acid 同一個成份 ≤10% 免處方、15% 處方，按地區唔同）。改用 **IECIC 做代理指標**：喺 IECIC 內 = 化妝品級；唔喺 IECIC 內 ＋ 認唔到 = `unknown`（誠實講唔識）；唔喺 IECIC 內 ＋ 命中**窄**禁忌名單 = `avoid` ＋ 轉介。**咁就唔需要我自己判斷邊個成份係處方。** 見 §3.5 |
| **D2** | 規則表嘅醫學正確性 | ✅ **已做** —— 對 corpus 驗完，揭發兩個 gap（漏 azelaic acid、冇色素維度），兩個都補。見 §3.2a |
| **D3** | 「值得買」點定義 | ✅ 啱。只出 `good / caution / avoid / insufficient_info`，**唔出分數、唔出價錢** |
| **D4** | 成份清單 | ⚠️ **決定咗但未拎到資料**：≥200 個，來源 IECIC。**corpus 只有 8 個，撐唔起**。需要：<br>① IECIC 檔案（版本 ＋ 來源要寫入檔頭）<br>② 揀邊 200 個嘅**準則**（我建議：功能性成份全取 ＋ 常見基質／防腐／香料；唔覆蓋全部約 8,800 個）<br>③ 確認冇授權／版權問題 |
| **D5** | 英中混合 ＋ 中文輸出 | ✅ 兩者都收（要正規化表）；**每個成份要有 zh display name**，`display_zh()` 令回答用中文 |

### 仲要你決定嘅兩件事

| # | 事項 |
|---|---|
| **D6** | 「成熟／次要」我讀成「**主選／次選**」（主選＝證據最多嘅成熟成份；次選＝特殊情況改用）。如果你意思係「成熟產品」＝ for mature skin，咁就完全唔同，講一聲 |
| **D7** | **色素維度點入資料**（§3.2a）：(1) 由 `Entry.note` keyword 偵測 ＋ (2) F2 request 可選字段。跟 doctrine #2 唔可以加第七個 attribute。同意？ |

---

## 7. 做完之後點證明冇壞（驗證清單）

| 檢查 | 方法 | 期望 |
|---|---|---|
| 後端冇回歸 | `./.venv/bin/python -m pytest -q` | 77 → 81+ passed |
| eval gate 冇回歸 | `./.venv/bin/python -m eval.run_eval --fake` | exit 0 |
| **商品評估唔寫 Entry** | 呼叫 `/products/evaluate` 前後 `SELECT COUNT(*) FROM entries` | **一樣**（呢個係最重要嘅一條） |
| 商品評估唔寫 products | 前後 `SELECT COUNT(*) FROM products` | 一樣 |
| 處方成份會拒絕 | POST 含 `tretinoin` 嘅成份表 | `verdict == "avoid"` ＋ 轉介訊息，**冇 LLM narrative** |
| 未知成份唔會猜 | POST 含亂碼成份 | `unknown` 有佢，`verdict == "insufficient_info"` |
| 疊加檢查命中 | 先用「水楊酸 toner」，再評估一支含水楊酸嘅 | `reasons` 有 `duplicate_active` |
| S1 修好 | mutation：`guardrails.py:56` 改返只掃 items | 新 test **必須 FAIL** |
| S2 修好 | 三個 scenario 之後 insights 數一樣 | test 斷言 |
| 真 DB 冇被碰 | `md5 backend/data/skincoach.db` | 前後一樣（現值 `40823465d6041edf11c05a44f07d88b9`） |
| 前端 | `npm run typecheck` + `npm run build` | exit 0 |
| 文件 | `AGENTS.md` 加 `ingredients.py` 一行；`README.md` feature list；`status-vs-claims.md` 新 row（**要寫明驗證證據係咩，唔可以寫「✅ 真」就算**） | 對得上 code |

---

## 8. 建議次序

| 階段 | 內容 | 為何咁排 | 幾時可以做 |
|---|---|---|---|
| **1** | **S1 + S8 一個 PR** | 商品評價嘅安全前置。唔做就係喺一個已知漏嘅 guardrail 上面加一個高風險介面 | ✅ **即刻可以** — §4 已寫到「精確行號 ＋ 4 個 test ＋ mutation 驗證法」 |
| **2** | **S2 兩步**（新 conversation ＋ 加一個 seed 記憶嘅 scenario） | eval 有效性；唔做就冇辦法證明階段 4／5 冇壞。單做第一步 = 少測一條路（§5.4） | ✅ **即刻可以** — 修法已實測「gate 3/3 PASS 不變」 |
| **3a** | `ingredients.py` **解析框架** ＋ `display_zh()` ＋ unit test（清單留空） | 純函數、零副作用、最易驗 | ✅ 即刻可以 |
| **3b** | 填 **≥200 個 IECIC 成份** ＋ 中文名 | **D4 資料未到手** | ⚠️ **要你先提供／批核 IECIC 來源** |
| **4** | F2 `/products/evaluate` endpoint ＋ 前端輸入框 | 用戶可見價值最大 | 依賴 1＋2＋3a |
| **5** | F1 成份／類別推介（`advise` prompt ＋ 主選／次選） | 依賴 3 | 依賴 1＋2＋3a |

**階段 4 唔一定要等 3b**：`parse_ingredients` 認唔到嘅成份一律入 `unknown[]` 並誠實講「唔認識」——
即係成份清單由 8 個擴到 200 個，只係令覆蓋率上升，**唔會令功能唔成立**。所以 3a 完成就可以開 4。

## 9. 明確唔做

- ❌ 商品目錄／品牌資料庫（§0：只出成份＋規格）
- ❌ 上網抓商品頁／價錢／成份（違反 §1）
- ❌ 商品評分、價錢比較
- ❌ 「處方成份黑名單」做**主要**判準（§3.5：唔係成份層面嘅問題）
- ❌ **手寫** 200 個成份名（要由 IECIC 抽，唔可以憑空造）
- ❌ 加第七個 attribute 落 6-attribute schema（doctrine #2）
- ❌ 商品審核／上架批准流程（§0）
- ❌ 寫 `Entry`／`products`（v1）
- ❌ 換 agent framework（Pi 或任何其他；唔理住）
- ❌ 動 `archive/skinfile/`（博物館）

---

---

## 附錄：corpus 驗證用過嘅指令（**已實跑，可重現**）

```bash
cd backend

# ① 成份覆蓋度（§3.2a 表格嘅數字來源）
#    ⚠️ 一定要用「中英＋俗名多個 pattern」—— 只用單一英文詞會得出完全唔同嘅數
#    （例：只查 'retinol' = 61，查整類 retinol/retinoid/tretinoin/視黃醇 = 422）
./.venv/bin/python - <<'PY'
import sqlite3
TERMS = {
    "水楊酸 salicylic": ["水楊酸", "salicylic", "BHA", "beta hydroxy"],
    "菸鹼醯胺 niacinamide": ["菸鹼醯胺", "菸鹼酰胺", "烟酰胺", "niacinamide", "nicotinamide", "vitamin b3"],
    "神經醯胺 ceramide": ["神經醯胺", "神经酰胺", "ceramide"],
    "玻尿酸 hyaluronic": ["玻尿酸", "透明質酸", "hyaluronic", "sodium hyaluronate"],
    "甘油 glycerin": ["甘油", "glycerin", "glycerol"],
    "積雪草 centella": ["積雪草", "centella", "cica", "madecassoside"],
    "泛醇 B5": ["泛醇", "panthenol", "維生素b5", "vitamin b5", "d-panthenol"],
    "視黃醇類 retinol/retinoid/tretinoin": ["視黃醇", "视黄醇", "a醇", "retinol", "retinoid", "維a酸", "tretinoin"],
    "果酸類 AHA/glycolic/lactic": ["果酸", "甘醇酸", "乳酸", "glycolic", "lactic acid", "AHA"],
    "尿素 urea": ["尿素", "urea"],
}
c = sqlite3.connect("data/skincoach.db")
for label, pats in TERMS.items():
    ids = set()
    for p in pats:
        ids.update(r[0] for r in c.execute(
            "select id from chunks where lower(text) like ?", (f"%{p.lower()}%",)))
    print(f"{label:40} {len(ids):>4}")
PY

# ② incidecoder 字典有幾大 → 答：8 個成份，撐唔起 200
./.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('data/skincoach.db')
print([r[0] for r in c.execute(\"select distinct title from chunks where source like '%incidecoder%'\")])"

# ③ azelaic / arbutin 散落幾多個唔同 title（證明唔止喺字典度）
./.venv/bin/python -c "
import sqlite3; c=sqlite3.connect('data/skincoach.db')
for kw in ['azelaic','arbutin']:
    print(kw, len(list(c.execute('select distinct title from chunks where lower(text) like ?', (f'%{kw}%',)))))"
```

**實測輸出（2026-09）**

| 檢查 | 結果 |
|---|---|
| 成份覆蓋度 | 見 §3.2a 表格（213／243／147／168／66／30／34／422／212／55） |
| `incidecoder.com` titles | `['Salicylic Acid','Niacinamide','Retinol','Panthenol','Hyaluronic Acid','Alpha-Arbutin','Azelaic Acid','Glycerin']` → **8 個** |
| `azelaic` 出現喺 | 63 個唔同 title |
| `arbutin` 出現喺 | 23 個唔同 title |
| 真 DB `products` | **0 行**（連 `ingredients` 都係 0） |

⚠️ **我第一版寫錯過呢個附錄**：只寫單一英文 pattern，跑出 `retinol 61`、`glycerin 39`、`centella 14`，
同 §3.2a 表格（`422`／`66`／`30`）對唔上 —— 即係一份**自己唔一致**嘅文件。已改成上面嘅多 pattern 版本並實跑核對。
