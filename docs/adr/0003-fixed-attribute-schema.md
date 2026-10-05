# 皮膚讀數用固定六個 attribute，LLM 唔可以自創

皮膚狀態只有六個 key（`acne`／`oiliness`／`redness`／`dryness`／`pores`／`texture`）× 0–3 severity，全部由 `attributes.py` 定義。change detect、persist、timeline、memory、correlation 一律只食呢六個。加 attribute 係改 schema（要 versioned），唔係叫 model 自由發揮。

**Considered options**：讓 model 自由描述皮膚、再抽取 —— 拒絕，因為「今日塊面有啲嚡」同「今日塊面少少乾」會被當成兩個唔同嘅嘢，trend 就永遠畫唔到。

**Consequences**：同一個分析入面仲有一個 **`Metric`** 欄位（model 自己寫嘅自由文字觀察）。佢係**顯示用**，唔會餵入任何確定性路徑。呢個係刻意嘅逃生口：唔想為咗一個講唔清嘅觀察而擴 schema，但代價係一個 object 入面有兩套「皮膚而家點」嘅表示，而只有一套係 load-bearing。CONTEXT.md 有明確標示。
