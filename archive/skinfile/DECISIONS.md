# DECISIONS.md — 技術選型討論（同埋面試談資）

呢份文件記錄 SKINFILE 每個技術決定嘅「點解係佢，唔係 X／Y／Z」。面試被問到時，照住講。

---

## 1. 點解 localStorage，唔用 Postgres／Supabase？

**決定**：單用戶、單機示範 → localStorage（versioned schema `skinfiledb:v1`）＋ module-level cache。

**點解唔係**：
- **Postgres／Supabase**：多人共用、跨裝置先需要。而家係純前端 demo，加後端會引入 auth、部署、維護成本，但冇用戶要多人。
- 知道個 tradeoff：localStorage 得 ~5MB，所以相片一定要 client-side 壓縮（canvas resize 1024px + JPEG q0.78）；多人版嘅遷移路徑係：storage 抽象層照舊，換 implementation 做 Postgres＋`pgvector` 就得。

**面試講法**：「我用 localStorage 係因為產品階段係單機 demo；但 storage 係抽象咗嘅，`normalize()` 保證 schema migration，多人版可以換後端而唔使改 views。我知 PostgreSQL + pgvector 喺好多場景可以替代獨立向量庫，所以唔會一嚟就上向量庫。」

## 2. 點解冇用向量庫／RAG？

**決定**：唔用。冇知識庫語料，唔值得。

**原因**（借 Claude Code 嘅經驗）：Claude Code 用 grep 而唔係 RAG，因為對**結構化、規模細**嘅資料嚟講，grep／關鍵字過濾又快又準又唔使 embed；RAG 嘅收益要喺「語料大到 grep 唔掂」嗰陣先浮現。SKINFILE 嘅「知識」係用戶自己嘅紀錄（~幾十條 entries），直接全文注入 prompt 已經得，仲可以控制順序做 prefix caching。

**如果真係要加知識庫**（例如成分百科）：我會用 Postgres + pgvector（一個 database 搞掂，唔使多一個 infra），embed 用 API 生成；但而家係負債唔係資產。

## 3. 點解單 Agent，唔用多 Agent？

**決定**：單 Agent（一個 system prompt＋三種任務 prompt），配合**結構化 JSON 介面**（進度評估）同**獨立細 call**（insight 擷取）。

**點解唔係多 Agent**：
- 任務可以拆成三個清楚 prompt（諮詢／check-in 回應／進度評估），單 Agent 已經做得好；
- 多 Agent 嘅收益（context 隔離、分工）喺呢個規模未出現；但**已經有「偽多 Agent」**：進度評估同 insight 擷取係獨立 call，各自有 system prompt，main response 失敗唔會拖冧 memory 更新。
- **乜嘢情況下會轉多 Agent**：當「每週計劃生成」同「每日回應」要各自長期 context（plan 要睇全歷史，daily 只要近 7 日）時，可以拆 Planner／Advisor 兩個 agent 共用 memory store。

**面試講法**：「我唔係為咗 show off 而用多 Agent。我嘅原則係：任務要喺 context 使用模式上真係唔同，先值得拆。SKINFILE 而家嘅 context 模式好一致，所以單 Agent＋結構化介面係最慳；我留低咗拆法：Planner 睇全歷史、Advisor 睇近 7 日，share 同一個 memory。」

## 4. Prefix caching 友善嘅 prompt 設計

**點解**：DeepSeek／OpenAI 都對「相同 prefix」做 KV cache，命中就慳錢慳 latency；prompt 設計可以主動配合。

**做法**（`prompts.ts` 有註釋）：
- 順序固定：`system prompt` → 目標／偏好（穩定）→ 推導結論（半穩定）→ **每次變動嘅紀錄摘要放最後**；
- `buildMemoryContext()` 輸出順序：偏好 → derived insights → recent entries；
- 所以同一用戶連續 check-in，前面幾百 token 完全一樣，API 可以 cache。

**面試講法**：「我將『用戶會變嘅嘢』（紀錄）放 prompt 尾，『唔會變嘅嘢』（system＋目標＋偏好）放頭，令到同一用戶嘅連續請求 prefix 重複，食到 provider 嘅 prefix caching。呢個對 DeepSeek 特別重要，因為佢哋 cache 命中率直接反映喺成本。」

## 5. 模型分級（Model Tiering）

**決定**：
| 任務 | 預設 model | 理由 |
|---|---|---|
| AI 諮詢（睇相＋詳細建議） | `gpt-4o`（strong） | 一次性、要深度 |
| Check-in 回應 | `gpt-4o-mini`（fast） | 高頻、短回應 |
| 進度評估（JSON） | `gpt-4o-mini`（fast） | 結構化、唔使深度 |
| Insight 擷取 | `gpt-4o-mini`（fast） | 最平，失敗唔影響主流程 |

Settings 頁每個任務可以獨立換 model。

**面試講法**：「我用平快 model 做高頻同機械化任務（擷取、評估），用強 model 做一次性深度任務（諮詢）。成本結構唔同，質素要求唔同，唔應該全部用同一個 model。」

## 6. Memory 系統設計（核心 Agent 知識）

**三類記憶**（`memory.ts`）：

| 類型 | 例子 | 生命週期 |
|---|---|---|
| 事實型（facts） | check-in entries、相片 | 永久（受容量限制） |
| 推導型（derived） | 「T 字位偏油」confidence 0.82 | **30 日 expiry（衰減）**；再評估可延長／提升 confidence |
| 偏好型（preferences） | 「鍾意清爽質地」 | 穩定 |

**衰減（decay）**：`expiresAt = createdAt + 30d`；過期 insight 標 `expired`，唔會再當做事實注入 prompt，需要時由最新資料重推。

**矛盾處理（contradiction）**：新結論同 active 結論 tag 唔同（例如之前判斷「油性」，而家「乾性」）→ 舊 insight 標 `supersededBy = 新 id`，新 insight `version+1`，**歷史保留**（Progress 頁可以睇到 v1→v2 點變）。

**一致時**：confidence 向新高靠攏（`max(old, new, old+0.05)`，cap 0.97），expiry 延長 —— 即係「重複證據增強信心」。

**面試講法**：「事實型係 ground truth，推導型係 AI 嘅推論 —— 推論要過期，先唔會變成『假事實』累積落去。矛盾處理用 versioning：新證據覆蓋舊結論但留歷史，因為『點解會變』本身都係資訊。參考過 OpenAI／Claude／Hermes／OpenCode 嘅 memory 演進 —— 共通點係：分層（short/long-term）、要有寫入時機、要有失效機制，否則 memory 會毒化 context。」

## 7. 點解視覺分析要可降級？

DeepSeek 官方 API（`deepseek-chat`）暫時係純文字，唔支援 image input（呢個係 2025 年中嘅狀態，要睇官方 changelog 確認）。所以：
- Provider preset 分「支援視覺」同「純文字」；
- `modelLooksTextOnly()` 直接跳過送相；
- API 回 400 且訊息提到 image/vision → 自動重試純文字並標記 `vision: false`；
- UI 顯示「已睇相／純文字」徽章。

**面試講法**：「多模態能力唔係每個 provider 都有，我將『有冇相』同『model 支唔支援相』分開做決定，fallback chain 令 App 喺 OpenAI 同 DeepSeek 之間切換都唔會爆。」

## 8. 純前端嘅安全取捨

- API key 只存瀏覽器 localStorage —— 冇上傳任何 server，因為**冇 server**；
- 呢個係 demo 取捨：key 會暴露俾同一個 browser 嘅 script；正式產品應該用後端 proxy（例如 Next.js API route 或者 Cloudflare Worker）保存 key。
- 知道呢個限制，先係專業。

## 9. 香港直連嘅視覺 Model（2025 年中實測狀態）

**背景**：OpenAI 官方 API 明確唔支援香港地區（403 `unsupported_country_region_territory`），
所以 App 預設 preset 嘅 OpenAI 喺香港直連會撞牆。解法：用「香港直連＋支援視覺＋OpenAI-compatible」嘅 provider，
App 已經將佢哋加入 Settings 做 presets（連「香港直連」標記同 CORS 提示）。

| Provider | Base URL | 視覺 Model | 香港直連 | 瀏覽器 CORS |
|---|---|---|---|---|
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.5-flash` / `gemini-2.0-flash` | ✅ | ✅ 大概率（官方有 browser 例子） |
| OpenRouter | `https://openrouter.ai/api/v1` | `openai/gpt-4o`、`google/gemini-2.5-flash`… | ✅ | ✅ 設計上支援 client-side |
| 阿里雲百煉 Qwen-VL | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-vl-max` / `qwen-vl-plus` | ✅ | ⚠️ 要實測 |
| 智譜 GLM-4V | `https://open.bigmodel.cn/api/paas/v4` | `glm-4v-plus` | ✅ | ⚠️ 要實測 |
| SiliconFlow | `https://api.siliconflow.cn/v1` | `Qwen2.5-VL-72B` 等 | ✅ | ⚠️ 要實測 |
| DeepSeek | `https://api.deepseek.com/v1` | 純文字（`deepseek-chat`） | ✅ | ✅ |

**關鍵約束**：App 係瀏覽器直連，所以 provider 一定要開 CORS header —— 呢個係最大變數。
中國 provider（Qwen／GLM／SiliconFlow）多數只為 server-to-server 設計，未必開 CORS；
Settings 頁「測試連線」可以即刻驗證。如果撞 CORS，最平解法係 Cloudflare Worker 做 proxy
（免費、香港直連、幾行 code），或者直接改用 Gemini／OpenRouter。
就算用純文字 model，App 有內建降級（自動唔送相、改文字分析），唔會爆。

## 10. 參考資料（一手來源）

- DeepSeek API docs：https://api-docs.deepseek.com/（模型列表、JSON mode、prefix caching 講解）
- OpenAI vision guide：https://platform.openai.com/docs/guides/vision
- Gemini OpenAI 相容端點（官方）：https://ai.google.dev/gemini-api/docs/openai
- 阿里雲 Qwen-VL OpenAI 相容：https://help.aliyun.com/zh/model-studio/qwen-vl-compatible-with-openai
- SiliconFlow 多模態模型：https://docs.siliconflow.cn/cn/userguide/capabilities/multimodal-vision
- Anthropic Contextual Retrieval / Claude Code 點解用 grep：https://www.anthropic.com/news/contextual-retrieval
- Vercel React Best Practices：https://vercel.com/docs/performance/react-performance
