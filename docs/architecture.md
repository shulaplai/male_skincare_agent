# Architecture — SkinCoach

> 呢份記錄**每個技術決定嘅「點解」**，係面試被問到時照住講嘅談資。**實施現況同 docs claim 嘅對照睇 `status-vs-claims.md`（live）**；呢份文件描述已實現嘅設計，唔再包含「打算做但未做」嘅字眼。舊 SKINFILE 嘅 DECISIONS.md（`archive/skinfile/DECISIONS.md`）仍值得睇（博物館）。

---

## 1. 核心命題：點解唔係「包層 API 嘅 chatbot」

一句公式：

> **Product = 確定性骨架 + 型別合約 + Tool whitelist + Guardrail + Eval 門檻**；LLM 只做「模糊嗰層」。

LLM 係**一個組件**，唔係**個 product**。下面每一層都係「點控制個 agent」嘅具體答案。

| 層 | 點控制 | 結果 |
|---|---|---|
| LangGraph state graph | 每條 edge、每個 node 都係你自己嘅 code（5 nodes 線性 flow） | agent 嘅「流程」係確定性、可 debug |
| Pydantic 型別合約 | 所有 LLM 輸出強制 fit schema（`SkinAnalysis` 含固定 attributes、`Advice`），唔俾 free text | 前端 render 到、可以 trace、可以 eval |
| Tool whitelist | agent 只可 call whitelist 工具（`get_skin_profile`/`get_recent_entries`/`search_knowledge`），冇任意外部 URL/代碼 | 唔會越權 |
| Guardrail | 硬規則唔經 LLM：唔診斷/唔開藥/唔俾劑量；紅旗詞強制轉介皮膚科；每答自動加 disclaimer | 安全，唔係靠 prompt 祈求 |
| Eval 門檻 | agent golden scenarios + RAG recall 入 CI（`--fake` deterministic），FAIL 唔准 merge | 唔會靜靜哋變差 |

## 2. Agent 流程（LangGraph，5 nodes 線性）

```
用戶影相/打字（相儲喺本地；conversation 開咗「雲分析」先送相上雲）
   ▼
analyze   「而家」張相 → vision model（deepseek-v4-flash-vision-exp，consent off / 冇相 → 純文字降級）
   ▼
tools     執行 analysis 揀嘅 whitelist 工具（讀 memory / 讀日記 / 檢索知識庫）
          + load 最近 10 條 chat messages 做 context
   ▼
advise    text model（deepseek-v4-flash）出 Advice：reply 正文（2–5 句解釋）+ items（行動點）
   ▼
guardrail deterministic：紅旗 → 轉介；藥物/劑量詞 → 收起建議；自動 disclaimer
   ▼
persist   upsert 當日 Entry（attributes/metrics/photos）+ code 對歷史 diff 寫 timeline event
          + 更新 memory + 寫 ChatMessage（reload 唔清空）
```

**LLM 只出現喺 `analyze`（出結構化分析）同 `advise`（出建議正文）兩個模糊層**；工具分派、guardrail、change detect、timeline、persist 全部係 deterministic code。變化 detect（上次／~1M／~3M）係 code 對歷史 severity 做 diff（`app/agent/attributes.py`），唔會送多張相俾 model。

## 3. 點解 LangGraph，唔係 Pydantic AI？

- 要練／展示嘅正正係「**自己控制 agent**」。LangGraph 俾你擁有 state graph 每一條 edge，唔係黑盒。
- **長期記憶唔用 checkpointer**：每次 consult 係 stateless，靠 SQLite（Entry/memory/`chat_messages`）+ 最近 N 條 messages 做 context —— 效果一樣、code 全自家、token 可控。跨日記憶靠 structured insights（帶 confidence/expiry），唔靠 raw conversation。
- LangGraph 喺 CV 值錢、生態大、可視化好；Pydantic AI 輕但「故事」冇咁完整。

## 4. Local-first + opt-in 雲分析（Privacy 決策）

- 相 + 日記**永遠**留喺用戶部機（SQLite + file system）。
- 雲分析係 **opt-in**：每個 conversation 一個「雲分析」開關（`cloud_analysis`，default 由 `SKINCOACH_CLOUD_ANALYSIS_DEFAULT` 控制，product default = off）。off 時相唔會離開部機：agent 行純文字分析，prompt 會同 model 講明「有相但睇唔到」，UI 標「未睇相」。
- 冇 API key 時行 **FakeLLM**（deterministic 罐頭輸出，成個 graph 跑得通）—— 唔係 Ollama。
- 面試講法：「local-first 係產品價值；opt-in 雲分析係成本／質素嘅 tradeoff，我將『儲存』同『分析』拆開做兩個獨立決策，consent 係 code gate 唔係靠 prompt。」

## 5. 長期記憶（沿用 SKINFILE 概念，落咗 SQLite）

| 類型 | 例子 | 生命週期 |
|---|---|---|
| facts | entries、相 | 永久（受容量限制） |
| derived | 「T 字位偏油」confidence 0.82 | 30 日 expiry 衰減；再評估可延長/升 confidence |
| preferences | 「鍾意清爽質地」 | 穩定 |

- 矛盾：新結論同舊結論衝突 → 舊標 `superseded_by`，新 `version+1`，歷史保留。
- 一致：confidence 向新高靠攏（cap 0.97）、expiry 延長。
- **設計目標**：reconcile 按 **attribute tag + direction** 判斷「一致 vs 矛盾」（唔靠文字相同）—— 記憶系統嘅升級方向，實施狀態見 `status-vs-claims.md` #6（而家只寫 `derived/recent_status` 一條，confidence 累積未生效）。

## 6. 向量庫：點解 SQLite + cosine，唔係 Qdrant/pgvector？

- local-first 優先 → **SQLite `chunks` 表（JSON embedding）+ Python cosine，零額外 infra、零 native 依賴**。
- 語料規模（幾十～幾百份文件、幾千 chunks）用 Python cosine 係 instant；未到需要獨立向量庫。
- 抽象層隔開 `add_chunks` / `search`，之後換 **sqlite-vec / pgvector** 唔使改上層。
- Embedding 用 **fastembed**（ONNX、無 torch、多語言 MiniLM-L12-v2）；測試／CI 用 dependency-free 嘅 hashing embedder（`DeterministicEmbedder`）。
- Corpus：PDF/JATS XML/文字 → 抽 text → chunk → embed；**冇 OCR**（語料多數係 text，未需要）。
- 面試講法：「我唔係為用而用向量庫；SQLite + cosine 夠用、可測試；接口抽象咗，升級路徑清楚。」

## 7. Model Tiering（DeepSeek V4，HK 直連）

| 任務 | model | 理由 |
|---|---|---|
| 視覺分析（analyze） | `deepseek-v4-flash-vision-exp` | 一次性、要睇相；同 text 同價（image ≈384 tok） |
| 建議生成 / 正文（advise） | `deepseek-v4-flash` | 深度文字 |
| 記憶更新 | 同上（text model） | fast tier 未有第二個 model（memory rewrite 時再諗） |
| Embedding | 本地 fastembed MiniLM（ONNX） | 離線、免費、無 torch |

> DeepSeek V4 預設 thinking mode 會令強制 `tool_choice` 400 —— adapter 對 structured output 自動加 `thinking: {type: disabled}`（`llm.py`）。

## 8. 安全 guardrail（health-adjacent 必答題）

護膚建議係 health-adjacent，production 一定要：
1. 硬規則（deterministic，唔經 LLM）：唔診斷疾病、唔開藥、唔俾劑量。
2. 高危信號（大面積／潰瘍／流膿／持續出血…）→ 強制轉介皮膚科醫生，收起護膚建議。
3. 每個 AI 建議自動帶 disclaimer。
4. Eval 有「安全」維度（`safety.py` deterministic checks + 有 key 時 LLM-as-judge 三維評分）。

## 9. 香港直連 provider（2026 實測更新）

OpenAI 官方 API 香港仍然 403；**Anthropic 亦 403**（唔喺 supported regions）。後端係 server-to-server（冇 CORS 問題），實際用 **DeepSeek**（HK 直連 ✅，2026-08 起有 vision：`deepseek-v4-flash-vision-exp`）。其他 provider（Gemini／OpenRouter／DashScope Qwen／GLM）都係 OpenAI-compatible 形狀，換 base_url + key 就用到 `OpenAICompatLLM`。詳細背景見 `archive/skinfile/DECISIONS.md` §9（博物館）。

## 10. 前端設計方向（已鎖定＋已實現）

- **主界面：教練對話優先（chat-first）** —— 對話係主角，右側 panel 顯示**真實**皮膚指標、AI 記憶、因果時間線（live，冇 hardcode demo 分數）。
- **多部位對話**：一個對話 = 一個身體部位（面部／頭皮／背部／手腳…）。default 一個「面部皮膚」，用戶可開新對話；**每個部位有獨立 entries/photos/insights/timeline/messages**。global scope（全身性「因」）係設計方向（`Insight`/`TimelineEvent` 嘅 conversation FK 可 NULL），寫手未做（Layer 2）。
- **數據面板**：真實 per-attribute 0–3 趨勢、sparkline、AI 偵測 timeline —— 唔做 arbitary composite score（例如「78 分」）。
- **Chat 歷史**：`chat_messages` 持久化，reload 唔清空；每次 consult stateless + 最近 N 條 messages context。
