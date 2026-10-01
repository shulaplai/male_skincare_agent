"""Lab 07 — Guardrail：唔靠 model 嘅安全閘

最重要嘅觀念：**唔可以叫 model「要安全啲」**。你叫佢唔好開藥，佢大機會照做，
但你唔可以保證。所以呢個 repo 將「唔准出現嘅嘢」寫成**普通 Python 規則**，
擺喺 model **後面**（graph 第 4 站），任何回覆都要過佢。

跑法：  ./backend/.venv/bin/python learn/labs/lab07_guardrail.py
"""
from _common import note, step, title, warn

from app.agent.guardrails import apply_guardrails
from app.agent.schemas import Advice

title("Lab 07 — Deterministic guardrail")

step(1, "規則放喺邊？（`app/agent/guardrails.py`）")
from app.agent import guardrails

print(f"  MEDICAL_TERMS 有 {len(guardrails.MEDICAL_TERMS)} 個詞（tretinoin、isotretinoin、口服抗生素…）")
print(f"  DOSE_RE = {guardrails.DOSE_RE.pattern!r}  ← 劑量要「數字＋單位」先算，唔可以用 bare 'mg'")
print("  contains_medical_advice() 同 advice_text() 兩個 function 就係全部規則。")

step(2, "個 bug 故事：舊版只掃 items，唔掃 reply")
print("  用戶睇到嘅係 `Advice.reply`（氣泡正文），`items` 只係卡片 bullet。")
print("  以前 guardrail 只檢查 items → 「每日口服抗生素 50mg」寫喺 reply 就會原封不動送出。")
note("教訓：**同一個規則要覆蓋所有出口**。呢啲叫做『同一類 bug 嘅兩個位』，repo 入面屢見不鮮。")

step(3, "實測：將同一句危險建議放喺唔同位置")
cases = [
    ("items 度", Advice(reply="照用就得。", items=["每日口服抗生素 50mg，連續兩星期"], disclaimer="", escalate=False)),
    ("reply 度", Advice(reply="你可以每日口服抗生素 50mg，連續兩星期。", items=["做好保濕"], disclaimer="", escalate=False)),
]
for where, advice in cases:
    out, escalate = apply_guardrails(advice, user_text="我想快啲好，用咩藥好？")
    print(f"\n  放喺 {where}：")
    print(f"    輸入 reply  = {advice.reply[:40]}")
    print(f"    輸入 items  = {advice.items}")
    print(f"    → 輸出 reply  = {out.reply[:60]}")
    print(f"    → 輸出 items  = {out.items}")
    print(f"    → escalate    = {escalate} / disclaimer = {bool(out.disclaimer)}")
warn("兩個位置都會被換成同一句轉介訊息 —— 呢個係**確定性**（deterministic），唔係靠 model 心情。")

step(4, "紅旗（red flag）：flag 同「改寫文案」係兩件事")
red = Advice(reply="睇落似普通暗瘡，買支水楊酸搽下就得。", items=["用水楊酸精華"], disclaimer="", escalate=False)
out, escalate = apply_guardrails(red, user_text="我塊面大面積潰爛流膿，仲發燒")
print(f"  用戶講「大面積潰爛流膿、發燒」→ escalate = {escalate}")
print(f"  輸出 reply = {out.reply[:70]}   ← ⚠️ 冇被改寫")
print(f"  輸出 items = {out.items}")
warn(
    "⭐ 呢個就係「保證嘅邊界」，要老實睇清楚：\n"
    "   · guardrail **一定**改寫嘅係：含醫療字眼／劑量嘅文案（確定性）\n"
    "   · 紅旗 → 只係設 `escalate=True`（UI 出轉介 banner），**唔會**自動改寫正文\n"
    "   紅旗情況嘅語氣係由 `advise` prompt 負責（叫 model 只可以建議睇醫生），\n"
    "   再加上 eval 嘅 safety scenario 守住 —— 即係「prompt + eval」而唔係 code 硬保證。\n"
    "   如果你要更硬嘅保證，正確做法係喺 guardrail 加：`if escalate: reply = ESCALATION_MESSAGE`。\n"
    "   （呢個係一個好嘅習題 —— 見 lab10 練習 3。）"
)

step(5, "商品評估（product_eval）都會硬停")
print("  貼成份表如果含處方成份（例如 tretinoin），`graph.guardrail` 會用")
print("  `product_eval.escalate` **覆寫** reply —— 就算 model 寫「呢支好溫和」都會被換走。")
print("  trace 會記 `forced_by_product_eval: true`。")

step(6, "呢堂嘅重點")
print("  1. 安全規則寫成 code，唔好寫成 prompt 願望")
print("  2. 規則要覆蓋**所有**出口（reply 同 items）")
print("  3. 唔可以用 substring 太闊嘅詞（bare 'mg' 會喺任何英文字中間命中）")
print("  4. 每次改規則都要有 test（`tests/test_guardrails*.py`）＋ eval 要過")
