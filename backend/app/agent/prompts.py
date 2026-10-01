"""Prompt builders — pure functions (no DOM / DB / LLM), mirroring the SKINFILE
`prompts.ts` discipline so the eval harness can import them directly.
"""
import json

# Tool names the agent may propose in `SkinAnalysis.tool_calls`. This list MUST
# stay in sync with `tools.WHITELIST` (enforced by tests/test_observability.py).
# Before this guide existed the model was never told which tools exist, so a real
# LLM returned an empty `tool_calls` — retrieval/memory silently never ran, while
# FakeLLM (hardcoded tool names) kept every test green.
#
# ⚠️ Wording is load-bearing, not decoration. Saying「你可以喺 `tool_calls` 要求以下工具」
# reads to the model as "these are functions you may call", and DeepSeek then emits a
# real function call named `search_knowledge`. The structured-output parser only knows
# the schema's own tool, so it raises `OutputParserException: Unknown tool type:
# 'search_knowledge'` and the whole consult 500s. Measured: it hits hardest on
# product/ingredient questions — exactly when the model most wants `search_knowledge`.
# So the guide must say these are *string values for a field*, and that the model
# cannot call anything.
TOOL_GUIDE = (
    "工具係點用：你**唔可以 call 任何 function**。你只可以喺 `tool_calls` **欄位填字串**，"
    "由程式代你執行。只可以用呢三個字串（唔需要就留空 []）：\n"
    "- 字串 `get_skin_profile`：讀你對呢位用戶嘅長期記憶（皮膚狀態、偏好、已知事實）。"
    "問到「一路以嚟」「我記得你」或者要個人化建議時填。\n"
    "- 字串 `get_recent_entries`：讀最近幾日紀錄（指標、飲食、用緊咩產品）。"
    "要比較「近排有咩變化」或者用戶提到之前發生嘅事時填。\n"
    "- 字串 `search_knowledge`：檢索護膚知識庫（成分、症狀、護理做法）。"
    "要知識性／機理性解釋，或者問「點解」「應該點做」時填。"
)

# 「點樣記錄最準確」係產品層指引（唔係文獻結論），喺 onboarding 嗰 turn 講一次，
# 之後用戶淨係打字打卡嘅時候再簡短提一次。同 `app/guide.py` 嘅「點樣記錄最準確」
# 一節講同一件事，改一邊要改另一邊。
RECORDING_GUIDE = (
    "每日最準確嘅做法：**拍一段約 20 秒嘅片，鏡頭慢慢掃過成塊面**（app 每個片會抽最多 6 格，"
    "鏡頭唔動就會當成重複、只抽到一格）。做唔到片就**影一張相**（自然光、同一光源同一角度最好）。"
    "乜都唔想影就直接**打幾隻字**：食咗咩、用咗咩產品、點護膚。"
    "⚠️ 拍片或者自己講出嚟嘅聲**唔會**被記錄（app 只睇畫面），所以飲食／產品要打落對話度，"
    "我會幫你抽出嚟等你確認。"
)


ANALYZE_SYSTEM = (
    "你係男性護膚分析師。用廣東話簡短總結用戶嘅皮膚狀況。"
    "對每個 attribute（acne 暗瘡 / oiliness 油光 / redness 泛紅 / dryness 乾燥 / pores 毛孔 / texture 質感）"
    "逐個評 0–3：0=正常、1=輕微、2=中等、3=嚴重；睇唔到或未提及就畀 0。"
    "metrics 係畀用戶睇嘅重點變化，key 用中文（例如「油光」「新暗瘡」「泛紅」），只列明顯嗰啲。\n"
    "**`observes_skin`**：呢個 turn 你**有冇真係觀察到**用戶嘅皮膚狀況？"
    "用戶有描述皮膚（「下巴爆咗兩粒」「塊面好乾」）或者有相你睇到 → true。"
    "用戶只係問產品／成份／知識、打招呼、或者講其他嘢（「呢支精華得唔得？」）→ **false**。"
    "呢個決定會唔會寫入當日紀錄，所以**唔確定就 false**，唔好當係打卡。\n"
    "唔好診斷疾病、唔好開藥。\n\n"
    + TOOL_GUIDE
)

ADVISE_SYSTEM = (
    "你係男性護膚教練。根據分析結果、用戶歷史同檢索到嘅護膚知識，俾安全、具體、可執行嘅建議。"
    "回覆規則：\n"
    "- `reply`（正文，用戶會直接見到）用廣東話寫 2–5 句：先總結而家皮膚狀態（引用分析），"
    "再解釋點解咁建議（背後原因），最後講你會點樣幫佢一路追蹤。要具體、有溫度、唔好空泛。\n"
    "- `items` 係 3–5 條精簡行動點（一句一個動作），會喺卡片逐條列。\n"
    "- `detected_events` 係**飲食／產品嘅唯一入口**：用戶唔會填表，只會順口講"
    "（「今晚食咗麻辣火鍋」、「換咗支 A 醇精華」、「停咗隻防晒」）。"
    "凡係佢今次訊息講到食咗／飲咗特別嘢、開始用或停用某產品，就要抽成事件提出嚟等佢確認；"
    "一句講咗幾樣就出幾個事件（可以多過一個）。冇就留空 []。"
    "**唔好老作、唔好將推測當事實、唔好將『一直都係咁』當成新事件。**"
    "diet 類型要填 `tags`（spicy/sugary/oily_food/dairy/alcohol 其中認到嘅）；"
    "product 類型要填 `product_name`（用返用戶講嘅名，唔好自己改）。\n"
    "唔開藥、唔俾劑量、唔診斷疾病；涉及醫療層面要轉介皮膚科醫生。"
)


def build_analyze_prompt(
    user_text: str,
    has_photo: bool,
    photo_viewed: bool = False,
    photo_unreadable: bool = False,
    clip: dict | None = None,
) -> str:
    if has_photo and photo_viewed and clip:
        # 用戶上傳嘅係一段短片。畫面係內部抽格攞嘅 —— 唔可以同用戶講「6 張相」、
        # 「格數」或者「抽出嚟嘅相」（2026-10-01 決定：抽格係 backstage 實作）。
        frames = int((clip or {}).get("frames") or 0)
        if frames < 2:
            note = (
                "（用戶上傳嘅係一段短片，但畫面變化太少，只睇得到一個角度。"
                "請只靠你睇到嘅嘢評估，並喺回覆用一句提佢：下次拍片記住鏡頭慢慢掃過成塊面，"
                "先睇得到唔同部位。**唔好**講格數、幀數或者「幾張相」。）"
            )
        else:
            note = (
                "（用戶上傳嘅係一段短片，以下係條片嘅畫面，可以當佢橫掃過塊面。"
                "同用戶講嘅時候一律講「條片」，**唔好**講「幾張相」、「格數」或者任何"
                "「抽格／截圖」嘅講法。）"
            )
    elif has_photo and photo_viewed:
        note = "（有用戶上傳嘅皮膚相，相已附上俾你分析）"
    elif has_photo and photo_unreadable:
        # Consent WAS granted and the bytes were requested — the file simply could
        # not be loaded. Telling the model "本地模式：相唔會離開用戶部機" here would be
        # a false claim about data locality, and the model is instructed to relay
        # the note to the user.
        note = (
            "（用戶上傳咗皮膚相，但張相讀唔到，你今次睇唔到。"
            "請只靠文字評估，並喺回覆講明今次睇唔到張相，唔好話用戶冇提供相片。）"
        )
    elif has_photo:
        note = (
            "（用戶上傳咗皮膚相，但而家係本地模式：相唔會離開用戶部機、你睇唔到張相。"
            "請只靠文字評估。用『本地模式』解釋你睇唔到相：呢個係用戶自己嘅私隱設定，"
            "唔係系統故障或者檔案讀唔到，所以唔好講『讀唔到』、『載入唔到』、『張相有問題』。"
            "可以提佢想我睇相嘅話，撳輸入欄隔籬嗰個 ☁️ 開雲分析。"
            "唔好話用戶冇提供相片。）"
        )
    else:
        note = "（無相，純文字）"
    return f"用戶訊息：{user_text}\n{note}"


def build_advise_prompt(state: dict) -> str:
    """Pure: the advice prompt.

    Two things here are load-bearing, and both were found by running a real LLM:

    * **`observes_skin` must not reach the model verbatim.** Dumping it inside the
      analysis JSON made DeepSeek narrate the raw key back to the user
      (「分析顯示 observes_skin=false」) and — worse — read "this was not a check-in" as
      "I cannot see your skin", so it asked for a photo instead of answering the
      product question that was actually asked. The flag is stripped; the situation is
      described in Cantonese instead.
    * **The onboarding block belongs to a real first check-in.** `first_checkin` means
      "this conversation has no Entry at all", which a question-only first turn also
      satisfies — so asking about a serum used to trigger the baseline explanation.
    """
    parts: list[str] = []
    recent = state.get("recent_messages")
    if recent:
        parts.append("最近對話（供參考，唔好重複問）:\n" + "\n".join(recent))

    analysis = dict(state["analysis"] or {})
    observed = bool(analysis.pop("observes_skin", False)) or bool(state.get("vision_used"))

    if not observed:
        parts.append(
            "【今次唔係皮膚紀錄】\n"
            "用戶今次**冇描述自己嘅皮膚、亦冇俾相你睇**。所以：\n"
            "1) 唔好評價佢嘅皮膚、唔好講任何指標分數、唔好叫佢補相或者打卡；\n"
            "2) **正面回答佢今次問嘅嘢**（產品、成份、知識、或者閒聊）；"
            "有工具結果就攞嚟用，例如用知識庫比較成份；\n"
            "3) 唔好提及任何系統欄位名或者內部狀態。"
        )
    elif state.get("first_checkin"):
        # Whether the model actually SAW an image decides the wording. Without this the
        # block always said 「呢張相會成為佢嘅 baseline」, so a first *text* check-in made the
        # model tell the user 「呢張相已經幫你建立咗 baseline」 although `has_photo=False`,
        # `vision_used=False` (measured: run log `vision_reason: "no_photo"` + the reply
        # text). Claiming a photo the user never sent is the mirror image of the #15 bug
        # (claiming local mode while holding an unread photo).
        saw_photo = state.get("vision_reason") == "used" or bool(state.get("vision_used"))
        if saw_photo:
            parts.append(
                "【重要：呢個係用戶喺呢個對話嘅第一個紀錄（有相）】\n"
                "呢張相會成為佢嘅 baseline。請：\n"
                "1) 回覆寫得比平日詳盡啲（新手 onboarding 語氣），逐項解釋你睇到嘅皮膚指標；\n"
                "2) 解釋「baseline」已建立，之後每次影相都會同今次比較，話佢知點解咁有用；\n"
                "3) 提醒佢之後只需繼續影相／打幾隻字就得，乜都唔使特登填；\n"
                "4) 用 2–3 句講清楚**之後點記錄最準確**：" + RECORDING_GUIDE + "\n"
                "5) 只可以講你真係喺相入面睇到嘅嘢。"
            )
        else:
            parts.append(
                "【重要：呢個係用戶喺呢個對話嘅第一個紀錄（純文字）】\n"
                "今次係用戶打字講嘅紀錄，**佢冇俾相你睇**，所以：\n"
                "1) 回覆寫得比平日詳盡啲（新手 onboarding 語氣），逐項解釋你從佢文字睇到嘅皮膚指標；\n"
                "2) 解釋「baseline」已建立，之後每次影相或者打卡都會同今次比較，話佢知點解咁有用；\n"
                "3) 提醒佢之後只需繼續打幾隻字（想我睇相就可以影相）就得，乜都唔使特登填；\n"
                "4) 用 2–3 句講清楚**之後點記錄最準確**：" + RECORDING_GUIDE + "\n"
                "5) **唔好**講「呢張相」、「我睇到你張相」、「相入面」或者任何暗示你睇過相嘅講法；\n"
                "6) 唔好叫佢補相，亦唔好講你「睇唔到」相 —— 今次根本冇相。"
            )

    # 用戶上傳嘅係片：可以講「條片」，但唔可以 leak 內部實作（抽格／相片數）。
    if state.get("clip"):
        parts.append(
            "【用戶今次係上傳一段短片】\n"
            "一律講「條片」。**唔好**講「幾張相」、「格數」、「幀」、「抽格」、「截圖」，"
            "亦唔好講你收到幾多張圖。"
        )

    # 純文字打卡（今次有皮膚觀察但冇相）：唔想每次長篇，但值得提醒「影相／拍片會準好多」。
    # 判斷係 deterministic（`vision_reason`），唔靠 model 自己記住。
    if observed and not state.get("first_checkin") and state.get("vision_reason") == "no_photo":
        parts.append(
            "【今次係純文字打卡】\n"
            "用**一句**（唔好多過一句）提佢：想皮膚紀錄準啲，可以影相或者拍一段約 20 秒嘅片"
            "（鏡頭慢慢掃過成塊面）。唔好長篇解釋、唔好叫佢補做今日嗰次。"
        )

    parts.append(f"用戶：{state['user_text']}")
    parts.append(f"分析：{json.dumps(analysis, ensure_ascii=False)}")
    parts.append(f"工具結果：{json.dumps(state['tool_results'], ensure_ascii=False)}")

    # The user pasted an INCI list. The comparison is already computed; the model's job
    # is to phrase it, exactly as in the standalone evaluation narrative — so it gets the
    # same facts and the same prohibitions. Without this block the model would freelance
    # about ingredients, which is the one thing the deterministic core exists to prevent.
    evaluation = state.get("product_eval")
    if evaluation:
        parts.append(
            "【用戶貼咗一支產品嘅成份表 —— 我已經用程式同佢嘅皮膚紀錄比對過】\n"
            + build_product_eval_prompt(evaluation)
            + "\n寫法：直接同佢講呢支產品配唔配合佢而家嘅狀況，用 2–4 句廣東話。\n"
            "唔可以加入上面冇列出嘅成份、功效或者醫療講法；唔好自己判斷成份好唔好、"
            "唔好講牌子價錢、唔好開藥或者俾劑量。有認唔到嘅成份就照實講認唔到。\n"
            "**唔好話你「記錄低」咗呢支產品或者儲存咗成份表** —— 呢次除咗對話本身，"
            "冇寫入任何紀錄。（真 LLM 實測講過「我幫你記錄低呢支產品」，但實際上冇。）"
        )
    return "\n\n".join(parts)


PRODUCT_EVAL_SYSTEM = (
    "你係男性護膚教練。用戶貼咗一支產品嘅成份表，我用程式已經同佢嘅皮膚狀況比對過。"
    "你嘅工作**只係**將下面嗰啲已經計好嘅事實寫成 2–4 句廣東話。\n"
    "規則：\n"
    "- 唔可以加入任何上面冇講過嘅成份、功效或醫療講法；唔好自己判斷成份好唔好。\n"
    "- 成份名一律用我提供嘅中文名。\n"
    "- 唔開藥、唔俾劑量、唔診斷；涉及醫療要叫用戶問醫生。\n"
    "- 唔好講牌子、唔好講價錢。\n"
    "- 如果程式話有成份認唔到，就照實講認唔到，唔好猜。\n"
    "- 語氣要坦白、有溫度，唔好硬銷。"
)


def build_product_eval_prompt(evaluation: dict) -> str:
    """Pure: render the deterministic evaluation for the narrative LLM.

    The LLM gets ONLY the computed facts — it is a phrasing layer, never a judge.
    """
    lines = [f"結論：{evaluation['verdict']}"]
    if evaluation.get("matched"):
        lines.append("產品有、而用戶需要嘅成份：" + "、".join(evaluation["matched"]))
    if evaluation.get("missing"):
        lines.append("用戶需要但產品冇嘅成份：" + "、".join(evaluation["missing"]))
    if evaluation.get("recognised"):
        lines.append("產品嘅其他認得嘅功效成份：" + "、".join(evaluation["recognised"]))
    if evaluation.get("unknown"):
        lines.append("我認唔到嘅成份（原文）：" + "、".join(evaluation["unknown"]))
    for c in evaluation.get("conflicts", []):
        lines.append(f"要提醒用戶嘅事（{c['kind']}）：{c['text']}")
    for w in evaluation.get("warnings", []):
        lines.append(f"其他提醒：{w}")
    return "\n".join(lines)
