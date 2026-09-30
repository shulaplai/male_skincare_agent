# 用戶筆記（自己撞到嘅問題）

> 用途：**你**試用嘅時候撞到啲唔對路嘅嘢，就喺呢度加一格。一格 = 一件事，唔使寫得靚，
> 但一定要有「做咗咩」同「實際發生咩」。之後我可以逐條查、變成 GitHub issue、或者直接修。
> 最後更新：（你寫嘅時候自己填）

## 三個地方嘅分工（唔好重複）

| 文件 | 住咩 |
|---|---|
| **呢份 `docs/user-notes.md`** | 你（用戶）自己撞到嘅嘢，未查、未分類 |
| `docs/user-trial-findings.md` | 我試用完嘅報告（已查、有證據、已分類 P1/P2/P3） |
| `docs/open-findings.md` | 審計之後嘅交收清單（已修／要你決定／環境限制） |
| GitHub issues | **要你決定方向**嘅嘢（`gh issue list`；第三輪試用開咗 #21–#24） |

## 快速環境

```bash
# backend（一定要喺 backend/ 度行；.env 由 CWD 讀）
cd backend && ./.venv/bin/python -m uvicorn app.main:app --reload --port 8001

# 想 embedder 唔會靜靜降級做 128 維（macOS 會清 temp dir）就加呢兩個 var：
SKINCOACH_EMBEDDER_CACHE_DIR=./data/.fastembed-cache HF_HOME=./data/.hf-cache \
  ./.venv/bin/python -m uvicorn app.main:app --reload --port 8001

# frontend（另開一個 terminal；:5173 proxy /api + /health → :8001）
cd frontend && npm run dev
```

開 http://localhost:5173 。**相永遠留喺你部機**；只有 conversation 開咗 ☁️ 雲分析，相才會送去
`deepseek-v4-flash-vision-exp`。

## 撞到問題就複製呢格

```markdown
### YYYY-MM-DD 一句講清楚咩事
- **我做咗咩**：（逐步，例如「桌面 1280px，同一個對話連續傾 6 條訊息」）
- **預期**：（例如「輸入框一直在畫面底部」）
- **實際發生**：（例如「要 scroll 成頁才見到輸入框」）
- **邊度**：layout（chat／journal／dash／mobile）、寬度 px、機／browser
- **截圖／證據**：路徑或者貼上嚟（`/tmp/…png`、console 訊息、run log 行）
- **嚴重度（我估）**：阻斷／好煩／少少
- **可重現？**：每次／試過一次／唔確定
```

---

## 示範（可以刪）

### 2026-09-30 出咗「🍜 ✅ 記低」chip 之後，reload 就冇咗
- **我做咗咩**：打「尋晚打邊爐食咗辣底」，等教練回覆，見到 chip，未撳就 reload 頁面
- **預期**：reload 之後仲可以撳「✅ 記低」
- **實際發生**：chip 完全消失，事件永遠記唔到（timeline 一直冇嗰條）
- **邊度**：chat layout、1280px、Chrome
- **截圖／證據**：`/tmp/skc-trial/shots/p2b-after-reload.png`；run log `detected_events: 1`
- **嚴重度（我估）**：好煩（因為「食辣 → 爆瘡」係我買呢個 app 嘅原因）
- **可重現？**：每次

> 呢條已經係 issue [#22](https://github.com/shulaplai/male_skincare_agent/issues/22)（未修，等你決定保存方式）。

---

## 已知、未修嘅問題（想試到嘅話，跟住做）

| 想試 | 步驟 | 而家狀態 |
|---|---|---|
| 同日讀數被覆蓋 | 同一日先打「下巴爆咗兩粒，T 字位好油」，再打多條含糊啲嘅（例如「今朝好似爆多咗」）→ 睇右欄指標由 2 變 1 | 未修 [#21](https://github.com/shulaplai/male_skincare_agent/issues/21) |
| 事件 chip 消失 | 打「尋晚食咗辣底」→ 出 chip → **reload** | 未修 [#22](https://github.com/shulaplai/male_skincare_agent/issues/22) |
| 相檔殘留 | 揀一張相（唔好送出）→ 撳 × → 睇 `backend/data/photos/` 多咗一個檔案但 UI 永遠見唔到 | 未修 [#23](https://github.com/shulaplai/male_skincare_agent/issues/23) |
| iPhone HEIC | 由 iPhone 相簿直接上載（唔經 WhatsApp） | 已修成可讀 415；原生支援未做 [#24](https://github.com/shulaplai/male_skincare_agent/issues/24) |
| 刪 entry 之後有爛圖 | 喺「記錄」刪某一日 → 返對話睇，嗰日嘅相會變 404 空框 | 未修（報告 P3-2） |

## 想變 issue 或者叫我做

- 直接喺 chat 話我知「user-notes 第 N 格幫我開 issue」就可以（我會跟 `docs/agents/issue-tracker.md`
  用 `gh` 開，唔會自己改方向）。
- 或者你自己開：
  ```bash
  gh issue create --title "一句標題" --body-file <(sed -n '/### /,$p' docs/user-notes.md)
  ```
- 交俾我之前，如果想確認係唔係 code 問題：`cd backend && ./.venv/bin/python -m pytest -q`（應該全綠）
  同 `./.venv/bin/python scripts/trace_consult.py --text "你打嗰句"`（會印 5 個 node 嘅 trace，
  用 temp DB + FakeLLM，安全、唔會掂你真 data）。
