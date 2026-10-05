# 只有帶皮膚證據嘅 turn 才寫 `Entry`

一個 turn 要寫 `Entry`，必須觀察到皮膚（model 判 `observes_skin`）或者真係睇過相。單純問一句產品問題、講兩句生活嘢，只會寫 `ChatMessage`。

**Considered options**：每個 turn 都當打卡（原本嘅行為）—— **實際撞過而且後果嚴重**：分析 prompt 規定「未提及嘅 attribute 一律畀 0」，所以問一句產品問題就會用全 0 覆蓋當日讀數；而且因為「一日只准一個 agent event」，嗰個假「改善」會被永久凍結，真打卡之後都改唔返。

**Consequences**：`observes_skin` 呢個欄位**唔可以**漏入 `advise` 嘅 prompt —— 真 model 會將欄位名照讀返俾用戶（「分析顯示 observes_skin=false」），而且會將「唔係打卡」誤讀成「睇唔到皮膚」而叫用戶補相、完全冇答佢問嘅問題。冇過閘嘅 turn 要喺 trace 留 `entry_written: false`。

**⚠️ 已知缺口**：呢個閘只擋「完全唔觀察皮膚」嘅訊息。一條**部分觀察**嘅訊息（「尋晚打邊爐，今朝爆多兩粒」）仍然會覆寫當日其他讀數 —— 見 [issue #21](https://github.com/shulaplai/male_skincare_agent/issues/21)，未決定合併語意。
