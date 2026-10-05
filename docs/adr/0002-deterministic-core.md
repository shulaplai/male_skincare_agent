# 確定性嘅核心行先，LLM 只做模糊層

guardrail、change detect、timeline 寫入、memory decay／reconcile **全部係程式碼**，唔係叫 prompt 求 model 合作。LLM 只出現喺兩個位：睇相／文字出結構化分析，同埋寫建議正文。

**Considered options**：靠 prompt 叫 model「唔好講藥物劑量」、「記得同上次比較」—— 拒絕，因為冇任何方法可以量度 prompt 嘅遵從率，而呢個 app 有安全後果（醫療主張）。guardrail 一定要係可以寫 unit test 嘅嘢。

**Consequences**：`apply_guardrails` 同 eval 嘅安全檢查必須共用同一份實作 —— 兩邊各寫一次就一定會分岔，而分岔過一次（兩個 caller 都只掃 `items` 唔掃 `reply`，所以互相照唔到，危險句照出）。同理，推薦規則只有一份（`recommend.RULES`），指南同 agent 都由佢生成，唔可能唔一致。
