"""Prompt builders — pure functions (no DOM / DB / LLM), mirroring the SKINFILE
`prompts.ts` discipline so the eval harness can import them directly.
"""
import json

ANALYZE_SYSTEM = (
    "你係男性護膚分析師。分析用戶嘅皮膚狀況，輸出結構化結果。"
    "唔好診斷疾病、唔好開藥。只描述觀察到嘅皮膚指標。"
)

ADVISE_SYSTEM = (
    "你係男性護膚教練。根據分析結果同檢索到嘅護膚知識，俾安全、具體、可執行嘅建議。"
    "唔開藥、唔俾劑量、唔診斷疾病；涉及醫療層面要轉介皮膚科醫生。"
)


def build_analyze_prompt(user_text: str, has_photo: bool) -> str:
    photo_note = "（有用戶上傳嘅皮膚相）" if has_photo else "（無相，純文字）"
    return f"用戶訊息：{user_text}\n{photo_note}"


def build_advise_prompt(state: dict) -> str:
    return (
        f"用戶：{state['user_text']}\n"
        f"分析：{json.dumps(state['analysis'], ensure_ascii=False)}\n"
        f"工具結果：{json.dumps(state['tool_results'], ensure_ascii=False)}"
    )
