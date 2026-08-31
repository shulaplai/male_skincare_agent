# AGENTS.md — 畀 AI Agent 開發 SKINFILE 嘅指引

呢個檔案係畀（人類同 AI）開發者睇嘅工作指引。跟住佢嚟改 code，可以減少破壞同走冤枉路。

## 常用命令

```bash
npm run dev          # Vite dev server（http://localhost:5173）
npm run typecheck    # tsc -b（一定要過先算完成）
npm run build        # typecheck + vite build
npm run eval         # eval harness（parser 測試唔使 key；LLM 測試要 SKINFILE_API_KEY）
```

## 目錄結構速覽

| 路徑 | 內容 | 注意 |
|---|---|---|
| `src/lib/types.ts` | 所有資料型別 | 改 schema 要同步改 `storage.ts` 嘅 normalize 同 `demoData.ts` |
| `src/lib/storage.ts` | localStorage（`skinfiledb:v1`） | **唔好喺 view 直接讀 localStorage**，要用 `store.ts` |
| `src/lib/store.ts` | React store（`useDb` / `useSettings`） | 狀態更新一定要經 `mutateDb`，先會通知 UI |
| `src/lib/memory.ts` | Memory 規則（三類／衰減／矛盾） | 核心邏輯，改動要有測試意識（eval 可擴展） |
| `src/lib/ai.ts` | API 呼叫（視覺／串流／JSON mode） | **唔好喺呢度寫 prompt**；prompt 喺 `prompts.ts` |
| `src/lib/prompts.ts` | 所有 prompt + JSON parser | **要保持純函數**（eval runner 會 import）——唔可以依賴 DOM/localStorage |
| `src/lib/services.ts` | 操作層（runConsult / runCheckin / runProgress） | views 只應該 call 呢層 |
| `src/views/*` | 頁面 | 唔好放業務邏輯，淨係 UI＋call services |
| `eval/` | 評估 harness | `run-eval.ts` 用 tsx 跑，可 import `src/lib/prompts` |

## 設計約定

1. **純函數層**：`prompts.ts` / `memory.ts` / `date.ts` 唔可以有 browser API 依賴（`prompts.ts` 會被 `eval/run-eval.ts` 喺 Node 直接 import）。要用 `crypto.randomUUID` 就經 `types.ts` 嘅 `uid()`。
2. **儲存 schema 係 versioned**：改資料結構時，`storage.ts` 嘅 `normalize()` 要兼容舊資料；唔好靜靜哋改 key 名。
3. **相片一定要壓縮先入 storage**：用 `compressImage`（max 1024px、JPEG q0.78）；quota 爆咗要 catch `StorageError` 並提示用戶。
4. **AI 錯誤要有用戶可讀訊息**：用 `AiError.code`（auth/not-found/image-not-supported/rate-limit/server/network/bad-request），唔好直接拋 raw error。
5. **新功能要過 eval**：涉及 prompt／parser 改動時，喺 `eval/scenarios.json` 加對應場景，或者至少確認 `npm run eval` 嘅 parser 測試仲係全綠。
6. **無 key 都要用得**：所有 AI 功能要有「AI 未設定」狀態；手動功能（紀錄、時間線、對比）永遠可用。

## 點樣加一個新功能（範例）

1. `types.ts` 加型別 → 2. `storage.ts` normalize 支援 → 3. `prompts.ts` 加 prompt builder（保持純）→ 4. `services.ts` 加操作 → 5. view 接入 `mutateDb` → 6. eval 加場景 → 7. `npm run typecheck && npm run build`

## 陷阱

- `useSyncExternalStore` 嘅 db 係**單一來源**；唔好喺 component 內維護第二份 db 副本。
- `services.ts` 嘅 streaming callback 用 local accumulator 儲全文，**唔好依賴 closure 入面嘅 state**（會 stale）。
- `CheckIn` 一日一條 entry（按 `date` upsert）；改呢個邏輯要同時睇 `Dashboard` 嘅 `todayEntry`。
- Demo 相係 canvas 生成，**唔好**喺 demo data 度放真人相。
