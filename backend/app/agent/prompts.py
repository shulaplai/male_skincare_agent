"""Prompt builders — pure functions (no DOM / DB / LLM), mirroring the SKINFILE
`prompts.ts` discipline so the eval harness can import them directly.
"""
import json

ANALYZE_SYSTEM = (
    "你係男性護膚分析師。用廣東話簡短總結用戶嘅皮膚狀況。"
    "對每個 attribute（acne 暗瘡 / oiliness 油光 / redness 泛紅 / dryness 乾燥 / pores 毛孔 / texture 質感）"
    "逐個評 0–3：0=正常、1=輕微、2=中等、3=嚴重；睇唔到或未提及就畀 0。"
    "metrics 係畀用戶睇嘅重點變化，key 用中文（例如「油光」「新暗瘡」「泛紅」），只列明顯嗰啲。"
    "唔好診斷疾病、唔好開藥。"
)

ADVISE_SYSTEM = (
    "你係男性護膚教練。根據分析結果、用戶歷史同檢索到嘅護膚知識，俾安全、具體、可執行嘅建議。"
    "回覆規則：\n"
    "- `reply`（正文，用戶會直接見到）用廣東話寫 2–5 句：先總結而家皮膚狀態（引用分析），"
    "再解釋點解咁建議（背後原因），最後講你會點樣幫佢一路追蹤。要具體、有溫度、唔好空泛。\n"
    "- `items` 係 3–5 條精簡行動點（一句一個動作），會喺卡片逐條列。\n"
    "唔開藥、唔俾劑量、唔診斷疾病；涉及醫療層面要轉介皮膚科醫生。"
)


def build_analyze_prompt(user_text: str, has_photo: bool, photo_viewed: bool = False) -> str:
    if has_photo and photo_viewed:
        note = "（有用戶上傳嘅皮膚相，相已附上俾你分析）"
    elif has_photo:
        note = (
            "（用戶上傳咗皮膚相，但而家係本地模式：相唔會離開用戶部機、你睇唔到張相。"
            "請只靠文字評估，並喺回覆講明你睇唔到張相，唔好話用戶冇提供相片。）"
        )
    else:
        note = "（無相，純文字）"
    return f"用戶訊息：{user_text}\n{note}"


def build_advise_prompt(state: dict) -> str:
    parts: list[str] = []
    recent = state.get("recent_messages")
    if recent:
        parts.append("最近對話（供參考，唔好重複問）:\n" + "\n".join(recent))

    if state.get("first_checkin"):
        parts.append(
            "【重要：呢個係用戶嘅第一個紀錄／第一次上載皮膚相】\n"
            "呢張相會成為佢嘅 baseline。請：\n"
            "1) 回覆寫得比平日詳盡啲（新手 onboarding 語氣），逐項解釋你睇到嘅皮膚指標；\n"
            "2) 解釋「baseline」已建立，之後每次影相都會同今次比較，話佢知點解咁有用；\n"
            "3) 提醒佢之後只需繼續影相／打幾隻字就得，乜都唔使特登填。"
        )

    parts.append(f"用戶：{state['user_text']}")
    parts.append(f"分析：{json.dumps(state['analysis'], ensure_ascii=False)}")
    parts.append(f"工具結果：{json.dumps(state['tool_results'], ensure_ascii=False)}")
    return "\n\n".join(parts)
