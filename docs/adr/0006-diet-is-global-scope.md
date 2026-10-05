# 飲食事件係 global scope，唔屬於任何部位

用戶確認嘅 `diet` 事件寫入 `conversation_id = NULL` 嘅 timeline row，而唔係嗰個部位嘅 timeline。每個 conversation 嘅 `/summary` 會將 global 事件 merge 入自己嘅時間線（UI 標 🌐）。

**Considered options**：diet 當一般事件、寫入當時嗰個 conversation —— 拒絕，因為飲食唔係局部嘅：用戶喺「面部」度講食咗辣，之後問「背部」時，背部嘅 correlation detector 一定都要見到嗰件事，否則「食辣 → 爆瘡」呢個核心賣點只會喺一半部位成立。

**Consequences**：`Insight`／`TimelineEvent` 嘅 conversation FK 必須可以係 NULL，即係 schema 上面容許「全身性」嘅 row。呢個要 SQLite 做 table rebuild 才改得到（`ADD COLUMN` 表達唔到），所以 `init_db()` 有一支 rebuild 路徑。搵 diet 事件一定要包 `IS NULL`，唔係就會靜靜漏。
