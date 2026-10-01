# §07 實驗索引同思考題

> 全部實驗：**FakeLLM ＋ 臨時 SQLite**，零 API 費用、零真 data 風險。
> 每個 lab 都會印「呢個 lab 示範咩 → 步驟 → 真輸出 → 你應該留意」。

## 跑法

```bash
./backend/.venv/bin/python learn/labs/lab03_agent_loop.py       # 由 repo root
# 或者
cd backend && ./.venv/bin/python ../learn/labs/lab03_agent_loop.py
```

想睇 app 內部 log（教學輸出會被蓋住）：`VERBOSE=1 ./backend/.venv/bin/python learn/labs/lab03_agent_loop.py`

---

## lab01 — 一個 LLM call 由頭到尾

**示範**：LLM 喺 code 入面唔係魔法，係一個 method。
**你會見到**：`structured(system, user, schema)` 簽名、真 prompt 內容、FakeLLM 回傳嘅物件、
`get_llm('text')` 回 `OpenAICompatLLM`（因為你有 key，但實驗用 FakeLLM）。
**思考題**
1. 邊一行 code 係真正「打去 model」？其餘係準備工作？
2. `get_llm()` 回真 adapter 嘅話，`FakeLLM` 喺 production 幾時會出現？（提示：冇 key 時）

---

## lab02 — Pydantic 合約擋咩

**示範**：LLM 出錯格式會被擋。
**你會見到**：`severity: 5`（超出 0–3）同亂 key 都會拋 `ValidationError`。
**思考題**
1. 如果冇 schema，呢個錯誤會喺邊度爆？（答：可能係幾層之後，而且已經寫入 DB）
2. `SkinAnalysis` 嘅 field description 係邊個睇？（答：model 自己 —— 所以係 prompt 一部分）

---

## lab03 — ⭐ 5 個 node 逐步（最核心）

**示範**：一次 consult 嘅完整思考過程。
**你會見到**：每一站吐 delta、真 trace（ms + detail）、DB 寫咗幾多行。
**思考題**
1. 邊啲站係 LLM、邊啲係 code？如果 model 換咗，邊啲站嘅行為會變？
2. `advise.detail.tool_rows = 0` 代表咩？呢個時候應唔應該信回覆？
3. 為咩 `trace` 用 reducer 而唔係普通 list？（提示：每個 node 只 append 自己嗰行）

---

## lab04 — ⭐ Embedding：hash vs 真 model

**示範**：唔係所有 vector 都識語意。
**你會見到**：同一組句子，hash embedder 同真 MiniLM 嘅相似度**反轉**
（暗瘡↔出油：0.067 vs 0.738）。
**思考題**
1. 為咩 hash embedder 會覺得「暗瘡」似「防曬」多過「出油」？（提示：字元重疊）
2. 384 維 vs 128 維唔可以混 —— `_cosine` 用 `zip()` 會點？（提示：靜靜只比前綴）

---

## lab05 — RAG：檢索 → 入 prompt

**示範**：chunk → embed → 檢索 → 塞入 prompt。
**你會見到**：`retrieve()`（純語意）同 `search_hybrid()`（加關鍵詞 re-rank）嘅分數分別；
空語料庫回 `[]`。
**思考題**
1. 為咩 runtime 用 hybrid，而 eval 用純語意做基準？（提示：基準要穩定）
2. `rows = 0` 嘅話，agent 會唔會停？（答：唔會，佢照答 —— 但就係「憑空答」，所以 trace 要睇）

---

## lab06 — Tool whitelist

**示範**：model 要求工具 vs 程式執行 —— 兩件事。
**你會見到**：`run_tool('hack_the_planet')` 回 `error='unknown tool (not in whitelist)'`，
但**唔會**執行任何嘢。
**思考題**
1. 為咩唔直接用 provider 嘅 function calling？（提示：換 provider、thinking mode 限制）
2. 加一個新工具要改幾多個位？（提示：`AGENTS.md` 話三處要同步）

---

## lab07 — Guardrail（確定性安全）

**示範**：安全規則寫成 code。
**你會見到**：同一句「每日口服抗生素 50mg」放喺 `reply` 或 `items` 都會被換成轉介句；
而紅旗（大面積潰爛）**只設 flag、唔改寫**。
**思考題**
1. 邊啲保證係 code、邊啲係 prompt？（呢條係本課程最重要嘅一題）
2. `MEDICAL_TERMS` 唔可以有 bare `"mg"` —— 為咩？（提示：substring 會喺任何英文字中間命中）
3. 想連紅旗都硬改寫文案，要改邊個檔邊一行？（習題見 `exercises.md`）

---

## lab08 — ⭐ Persist 閘門

**示範**：為咩問產品唔會變成「一日皮膚數據」。
**你會見到**：`observes_skin=False` → `entry_written=False` 但 `ChatMessage` 照寫；
`observes_skin=True` → Entry + 3 條 insights。
**思考題**
1. 為咩 ChatMessage 照寫而 Entry 唔寫？（提示：display truth vs data truth）
2. 如果閘門寫錯（例如用關鍵詞猜），最壞情況會點？（提示：假「改善」被永久凍結）

---

## lab09 — FakeLLM vs 真 LLM（可選）

**示範**：adapter pattern；同埋「假嘅驗證唔到真行為」。
**你會見到**：唔加 `--real` 就只印會送咩出去；加 `--real` 就真跑一次（會用你嘅額度）。
**思考題**
1. 為咩 `eval --fake` 全綠都唔代表 model 行為正確？
2. 如果你轉用本機 Ollama／llama.cpp，要改邊幾個檔？（答：`llm.py` 加 adapter + `config.py`）

---

## lab10 — ⭐ 自己寫一個 eval（配課程 §06）

**示範**：eval 由邊幾件砌成、點加一條檢查、同埋「個檢查識唔識紅」。
**你會見到**：真 recall@3／MRR（語意 0.90 vs hybrid 1.00）、4 個 scenario 嘅評分、
你自己加嘅三條好規則全綠、一條太嚴嘅規則全紅，同埋**反轉條件之後全部變紅**。
**思考題**
1. 為咩「反轉條件一定要紅」係寫 eval 唯一唔可以省嘅一步？
2. `--fake` 驗到「管道」、`--real` 驗「文筆」—— 咁 `judge.py` 喺邊一層？為咩佢唔可以做 gate？
3. 你條規則紅咗，你點分「產品有問題」同「我要求太嚴」？（提示：睇 FakeLLM 係唔係常數）

---

## 習題（`exercises.md`）

四個由淺入深嘅改動練習：
1. 改一句 prompt，令回覆短啲（睇 `tests/test_prompt_*.py` 有冇爆）
2. 加一個新 tool（`get_product_history`）到 whitelist + prompt + schema
3. 將 guardrail 嘅紅旗變成「硬改寫文案」（要加 test）
4. 唔用 framework，親手寫一個 30 行 agent 做對照
