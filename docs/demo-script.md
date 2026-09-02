# SkinCoach Demo Video 劇本（~2.5 分鐘）

> 面試用：一邊 screen record 一邊跟住講。目標係喺 3 分鐘內展示「呢個係控制緊嘅 AI agent，唔係包層 API 嘅 chatbot」。

## 0:00–0:20 開場：一個痛點

**字卡**：「ChatGPT 唔記得你上個月張相。」

旁白：「ChatGPT 俾你一次性護膚建議，但唔會記得你上個月塊面係點。SkinCoach 係一個 local-first 嘅 AI 皮膚教練：影相 → AI 分析 → 對話追問 → 長期記憶 → 幾個月後可以 trace 返『因為咩原因令皮膚變』。」

## 0:20–0:50 影相 + local-first

**畫面**：撳輸入欄左邊「影相/加相」掣。

旁白：「相永遠儲喺你自己部機（SQLite + file）；你授權先會上雲分析、用完即棄，仲有個『本地/雲』開關。呢個係 local-first 設計——儲存同分析係兩個獨立決策。」

## 0:50–1:20 對話 = 多步 agent

**畫面**：打字「下巴爆瘡好油，點算？」撳發送，等回覆。

旁白：「撳發送之後，背後係一個 LangGraph state graph 行 5 個 node：分析 → 揀工具 → 生成建議 → guardrail → 寫入日記。每個 node、每條 edge 都係我自己寫嘅 code，LLM 只喺『分析』同『生成建議』兩個模糊層出現。」

**畫面**：指住回覆入面嘅「Agent 分析」卡（metrics + 建議）。

## 1:20–1:50 長期記憶 + 因果時間線

**畫面**：指住右邊「AI 記得你」panel（confidence bar）同「因果時間線」。

旁白：「佢會記住『T 字位偏油』（confidence 0.82），呢啲係推導記憶、30 日會過期；新證據同舊結論矛盾會 version 覆蓋、留歷史。右邊時間線 trace 返『食辣 → 爆瘡』嘅因果。呢啲規則全部係 deterministic code，唔係靠 prompt 祈求。」

## 1:50–2:10 多部位對話 + 數據

**畫面**：撳「＋新增部位對話」開「腳部皮膚」。

旁白：「一個對話 = 一個身體部位，各自有獨立日記、記憶、時間線、皮膚指數。方向 02 嗰啲數據（指數、sparkline、指標）全部收埋喺側邊 panel。」

## 2:10–2:30 Guardrail + Eval

**畫面**：切返面部，打「塊面突然大面積爛晒好痛」→ show 紅旗 banner「建議轉介皮膚科醫生」。再開 terminal show `python -m eval.run_eval --fake`。

旁白：「護膚係 health-adjacent，所以有硬 guardrail：唔診斷、唔開藥、紅旗強制轉介、每答帶 disclaimer。質素靠 eval harness——RAG recall + agent golden scenarios，5 個 recall 場景＋3 個 agent 場景全綠，仲有 60 個 unit test；eval 入咗 CI，FAIL 唔可以 merge。」

## 2:30 收尾

旁白：「一句總結：Product = 確定性骨架 + 型別合約 + Tool whitelist + Guardrail + Eval 門檻。LLM 只做模糊嗰層，其餘全部係自己控制嘅 code。呢個先叫 AI Agent product。」
