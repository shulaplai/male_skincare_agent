# 技術 Blog 大綱：《點樣控制一個 AI Agent，而唔係俾佢控制你》

> 對應 repo 嘅真實實作。每個 section 都係「點解」＋「點做」＋「tradeoff」，照住可以寫成一篇 2000–3000 字嘅 blog。

## 0. TL;DR

一句公式：**Product = 確定性骨架 + 型別合約 + Tool whitelist + Guardrail + Eval 門檻**；LLM 只做「模糊嗰層」。

## 1. 背景：點解「包層 API」唔夠

- chatbot（包層 API）＝ 薄薄哋 call OpenAI/DeepSeek，冇狀態、冇合約、冇質素門檻。
- 一個真 agent product 要：跨時間記憶、可 trace、安全、可 eval。
- SkinCoach 個痛點：ChatGPT 唔記得你上個月張相；我哋要跨時間閉環。

## 2. 架構總覽（一張圖）

```
React (frontend) ──/api──> FastAPI ──> LangGraph agent
                                   ├─ SQLite (memory/entries/photos)
                                   ├─ RAG (SQLite chunks + fastembed)
                                   └─ guardrail (deterministic)
```

## 3. 控制點一：State Graph —— 每一條 edge 都係你嘅 code

- LangGraph `StateGraph`，5 個 node：analyze → tools → advise → guardrail → persist。
- LLM 只喺 `analyze` 同 `advise` 出現；工具分派、guardrail、persist 全部 deterministic。
- 面試講法：state graph 係「流程係你擁有」；黑盒框架幫你慳嘅，正正係你想練嗰 part。

## 4. 控制點二：型別合約（Pydantic）

- `SkinAnalysis` / `Advice` 強制 JSON schema；LLM 輸出唔 fit 就 fail，唔會漏 free text 出嚟。
- 好處：前端 render 到、persist 寫到、eval 測到。

## 5. 控制點三：長期記憶係 deterministic

- 三類記憶：fact（ground truth）／derived（AI 推論，30 日衰減）／preference（穩定）。
- 矛盾 → `superseded_by` + version+1 留歷史；一致 → confidence 升 + expiry 延長。
- 重點：衰減同矛盾係 code，唔係 prompt 祈求。

## 6. 控制點四：Tool whitelist

- agent 只可 call `get_skin_profile` / `get_recent_entries` / `search_knowledge`，未知工具名直接 ignore。
- 冇任意外部 URL、冇代碼執行。

## 7. 控制點五：Guardrail（health-adjacent）

- 硬規則：唔診斷、唔開藥、唔俾劑量；紅旗（大面積爛面/潰瘍/出血）強制轉介；每答 disclaimer。
- 安全唔應該靠 model 聽話，要靠 model 冇得揀。

## 8. 控制點六：Eval 門檻

- RAG recall@k（golden queries）＋ agent golden scenarios ＋ LLM-as-judge（具體性/相關性/安全）。
- 改 prompt 要過 eval；CI 跑綠先 merge。

## 9. Local-first 決策

- 相留用戶機，opt-in 雲分析；儲存同分析係兩個獨立決策。

## 10. 教訓 + 下一步

- 教訓：vector DB 唔使急住上，SQLite + cosine 夠用（抽象層留升級路）。
- 下一步：真 vision model 接相分析、多用戶 auth、Postgres+pgvector 升級。
