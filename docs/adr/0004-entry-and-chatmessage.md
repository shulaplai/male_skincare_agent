# `Entry` 同 `ChatMessage` 係兩份唔同嘅真相，唔可以合併

`Entry` 係每日結構化摘要（機器食嗰份），`ChatMessage` 係對話 turn（reload 之後顯示嗰份）。同一個 user turn 會同時產生兩者，但兩者嘅生命週期、可否刪、可否改都唔同。

**Considered options**：只留 ChatMessage、讀嘅時候即時砌出每日摘要 —— 拒絕，因為摘要嘅語意（合併、decay、supersede）需要穩定嘅 id 同可查嘅欄位，冇得靠 render 時重算。只留 Entry、對話由 Entry 反推 —— 拒絕，因為用戶睇到嘅係對話，包括 agent 犯錯同被轉介嗰幾條，反推唔到。

**Consequences**：兩者會短暫唔一致（例如 consult 失敗時只有 ChatMessage）。呢個係預期之內，唔應該試圖用 transaction 夾硬綁埋一齊。
