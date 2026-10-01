# §00 心智模型：Agent 同普通 backend 有咩分別？

> 你已經識寫 API。呢章用你識嘅嘢做對照，建立「agent 係咩」嘅第一印象。

## 1. 普通 backend

```
HTTP request → 你寫嘅邏輯（確定性）→ HTTP response
```

同一組 input，永遠同一組 output。**你控制每一行。**

## 2. 加咗 LLM 之後

```
HTTP request → 砌 prompt → LLM（非確定性）→ 文字 → 你嘅邏輯 → HTTP response
```

多咗一個**唔確定**嘅中間人。佢唔識你嘅型別、唔知你嘅 DB、每次可能答得唔同。
所以你嘅工作由「寫邏輯」變成**「寫邏輯 ＋ 管住一個唔聽話嘅拍檔」**。

## 3. 咩時候叫做「agent」

當 LLM **唔止答一次**，而係可以「要求」你嘅程式做嘢（用工具），你再將結果餵返佢 ——
呢個 loop 就係 agent。SkinCoach 嘅 loop 有五站（§04 詳細講）：

```
                 ┌──────────────────────────────────────────┐
用戶訊息 ──► ① analyze（LLM 睇字/睇相 → 結構化分析）        │
                 │    ↓ tool_calls: ["get_skin_profile"]  │
            ② tools（普通 Python：查 DB／查語料庫）         │
                 │    ↓ 工具結果                          │
            ③ advise（LLM 寫回覆，帶住工具結果）            │
                 │    ↓                                   │
            ④ guardrail（普通 Python：安全規則硬檢查）      │
                 │    ↓                                   │
            ⑤ persist（普通 Python：寫 Entry／記憶／時間線）│
                 └──────────────────────────────────────────┘
                        ↑ 只有 ①③ 係 LLM，②④⑤ 全部係 code
```

⭐ **呢個課程最重要嘅一句**：
> **Agent = 一個 LLM 加一圈你自己寫嘅、確定性嘅骨架。**

骨架就係 §01 講嘅「harness」。

## 4. SkinCoach 三個「真相來源」

初學者最易混淆嘅位。同一個對話，資料其實住喺三個地方：

| 住邊 | 係咩 | 邊個食 |
|---|---|---|
| `entries`／`insights`／`timeline_events`（SQLite） | **data truth**：結構化讀數、長期記憶 | 程式（改變偵測、相關性、記憶 decay） |
| `chat_messages` | **display truth**：用戶睇到嘅對話氣泡 | 前端 reload |
| `data/runs.jsonl` + `state["trace"]` | **observability**：每個 node 做咗咩、幾多 ms | 你（debug） |

`AGENTS.md` 約定 #5 就係講「Entry 同 ChatMessage 分家」——因為兩者需求唔同：
一個要餵程式，一個要餵眼睛。混埋一齊，就會出現「為咗靚而寫假數據」呢類災難。

## 5. 「AI 會唔會亂講嘢？」— 呢個 repo 嘅答案

| 風險 | 對策（唔係靠 prompt 許願） |
|---|---|
| 亂出格式 | Pydantic schema 強制（§02） |
| 亂建議醫療 | `guardrails.py` deterministic 硬檢查（§04） |
| 亂記數據 | `persist` 閘門（lab08） |
| 亂識別成份 | 字典 + 引文，唔准 model 自己判（`ingredients.py`） |
| 靜靜壞掉 | trace + eval + 273 個 test |

## 6. 落手之前：跑一次

```bash
./backend/.venv/bin/python learn/labs/lab03_agent_loop.py
```

你會見到五站逐站吐出「更新咗咩 state」，同埋一個 trace 表。睇完你就會明白
§04 要講嘅嘢 —— **唔好只讀，跑佢**。

## 本章重點（背落嚟）

1. Agent = LLM ＋ 你寫嘅確定性骨架。LLM 只佔兩站。
2. 非確定性要**包住**，唔係「求佢乖」。
3. 同一個對話有三份記錄（data／display／trace），各有用途。
