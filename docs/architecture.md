# Architecture — SkinCoach

呢份記錄**每個技術決定嘅「點解」**，係面試被問到時照住講嘅談資。舊 SKINFILE 嘅 DECISIONS.md（`archive/skinfile/DECISIONS.md`）仍值得睇，啲概念（memory 衰減、model tiering、prefix caching、vision 降級）喺度升級重用。

---

## 1. 核心命題：點解唔係「包層 API 嘅 chatbot」

一句公式：

> **Product = 確定性骨架 + 型別合約 + Tool whitelist + Guardrail + Eval 門檻**；LLM 只做「模糊嗰層」。

LLM 係**一個組件**，唔係**個 product**。下面每一層都係「點控制個 agent」嘅具體答案。

| 層 | 點控制 | 結果 |
|---|---|---|
| LangGraph state graph | 每條 edge、每個 node 都係你自己嘅 code，checkpoint 你自己揀 | agent 嘅「流程」係確定性、可 debug |
| Pydantic 型別合約 | 所有 LLM 輸出強制 fit schema（JSON mode），唔俾 free text | 前端 render 到、可以 trace、可以 eval |
| Tool whitelist | agent 只可 call 你定義嘅 `@tool`（查產品/日記/知識庫），冇任意外部 URL/代碼 | 唔會越權 |
| Guardrail | 硬規則唔經 LLM：唔診斷/唔開藥/唔俾劑量；嚴重情況強制轉介皮膚科；每答 disclaimer | 安全，唔係靠 prompt 祈求 |
| Eval 門檻 | 每改 prompt 過 golden set + LLM-as-judge，CI 綠先 merge | 唔會靜靜哋變差 |

## 2. Agent 流程（LangGraph）

```
用戶影相/打卡（相永遠儲喺本地；授權先上雲分析，用完即棄）
   ▼
node1 視覺分析   vision model（可降級純文字，fallback chain）
   ▼
node2 讀長期記憶  facts / derived / preferences（30日衰減 + 矛盾 versioning）
   ▼
node3 檢索知識庫  sqlite-vec（中英美容 PDF 語料）
   ▼
node4 揀工具     whitelist：查產品 / 查日記 / 查知識庫
   ▼
node5 生成建議   強制 Pydantic schema
   ▼
node6 寫入日記 + 更新記憶（重複證據升 confidence、矛盾就 supersede 留歷史）
```

## 3. 點解 LangGraph，唔係 Pydantic AI？

- 要練／展示嘅正正係「**自己控制 agent**」。LangGraph 俾你擁有 state graph 每一條 edge，唔係黑盒。
- **長期記憶** = LangGraph `checkpointer` + 自己嘅 SQLite（日記、timeline、memory 規則），呢個係自定義 logic，唔係 framework 幫你慳嗰 part。
- LangGraph 喺 CV 值錢、生態大、可視化好；Pydantic AI 輕但「故事」冇咁完整。

## 4. Local-first + opt-in 雲分析（Privacy 決策）

- 相 + 日記**永遠**留喺用戶機（SQLite + file system）。
- 雲分析係 **opt-in**：用戶主動授權先送相上雲，分析完相即棄、雲唔留底。
- 「純本地模式」開關 → 全行 Ollama（vision + text），相一次都唔離開部機。
- 面試講法：「local-first 係產品價值，唔係技術潔癖；opt-in 雲分析係成本／質素嘅 tradeoff，我將『儲存』同『分析』拆開做兩個獨立決策。」

## 5. 長期記憶（沿用 SKINFILE 概念，落咗 SQLite）

| 類型 | 例子 | 生命週期 |
|---|---|---|
| facts | entries、相 | 永久（受容量限制） |
| derived | 「T 字位偏油」confidence 0.82 | 30 日 expiry 衰減；再評估可延長/升 confidence |
| preferences | 「鍾意清爽質地」 | 穩定 |

- 矛盾：新結論 tag 唔同 → 舊標 `supersededBy`，新 `version+1`，歷史保留。
- 一致：confidence 向新高靠攏（cap 0.97）、expiry 延長。

## 6. 向量庫：點解 SQLite + cosine，唔係 Qdrant/pgvector？

- local-first 優先 → **SQLite `chunks` 表 + Python cosine，零額外 infra、零 native 依賴**。
- 語料規模（幾十～幾百份文件、幾千 chunks）用 Python cosine 係 instant；未到需要獨立向量庫。
- 抽象層隔開 `add_chunks` / `search`，之後換 **sqlite-vec / pgvector** 唔使改上層。
- Embedding 用 **fastembed**（ONNX、無 torch、多語言 MiniLM），模型 cache 指去 workspace；測試用 dependency-free 嘅 hashing embedder。
- 面試講法：「我唔係為用而用向量庫；SQLite + cosine 夠用、可測試；接口抽象咗，升級路徑清楚。」

## 7. Model Tiering（沿用 + 擴充）

| 任務 | model | 理由 |
|---|---|---|
| 視覺分析 | strong vision（雲）／本地 Qwen-VL | 深度、一次性 |
| 建議生成 | strong text | 深度 |
| 記憶更新 / insight 擷取 | fast text | 高頻、機械化 |
| Embedding | 本地 fastembed（ONNX、多語言 MiniLM） | 離線、免費、無 torch |

## 8. 安全 guardrail（health-adjacent 必答題）

護膚建議係 health-adjacent，production 一定要：
1. 硬規則（deterministic，唔經 LLM）：唔診斷疾病、唔開藥、唔俾劑量。
2. 高危信號（持續出血 / 突然大面積爛面 / 長期潰瘍）→ 強制轉介皮膚科醫生，唔俾護膚建議。
3. 每個 AI 建議帶 disclaimer。
4. Eval 有「安全」維度評分（LLM-as-judge）。

## 9. 香港直連 provider（沿用 SKINFILE 實測）

OpenAI 官方 API 香港 403；production 後端係 server-to-server（冇 CORS 問題，比純前端闊鬆），但都預設用香港直連得嘅 provider：Anthropic / DeepSeek / Gemini / OpenRouter 等。詳細見舊 `archive/skinfile/DECISIONS.md` §9。

## 10. 前端設計方向（已鎖定）

- **主界面：教練對話優先（chat-first）** —— 對話係主角，右側 panel 放「皮膚指數 + AI 記憶 + 因果時間線」。
- **多部位對話**：一個對話 = 一個身體部位（面部／頭皮／背部／手腳…）。default 得一個「面部皮膚」對話，用戶可開新對話；**每個部位有獨立嘅日記、記憶、時間線、皮膚指數**。
- **數據面板保留**（方向 02 嗰啲）：皮膚指數、油光／泛紅／暗瘡指標、sparkline、before/after、因果時間線 —— 全部照做，只係收埋喺 chat 側邊，唔做主角。
- 呢個設計對應到 **數據層**（Phase 1）嘅影響：所有 record（entries／photos／insights／timeline）都要加 `body_part` 維度；一個 user 多個 conversation/部位。
