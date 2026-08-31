"""Deterministic safety guardrails (no LLM).

These are the "medical guardrail" layer from the architecture: hard rules that
run regardless of what the model produced, so safety never depends on the model
behaving.
"""
from .schemas import Advice

DEFAULT_DISCLAIMER = (
    "以上建議只供參考，唔構成醫療意見。如果情況持續或惡化，請諮詢皮膚科醫生。"
)

RED_FLAGS = [
    "大面積",
    "潰瘍",
    "流膿",
    "持續出血",
    "擴散得好快",
    "高燒",
    "劇痛",
    "呼吸困難",
    "突然爆發",
    "腫到",
]

MEDICAL_TERMS = [
    "口服",
    "劑量",
    "毫克",
    "mg",
    "抗生素",
    "類固醇",
    "處方藥",
    "isotretinoin",
    "accutane",
    "異維a酸",
    "消炎藥",
]

ESCALATION_MESSAGE = (
    "你嘅情況可能涉及醫療層面，我唔可以俾呢方面嘅建議。"
    "請盡快諮詢皮膚科醫生。"
)


def contains_any(text: str, terms: list[str]) -> bool:
    low = text.lower()
    return any(t.lower() in low for t in terms)


def apply_guardrails(advice: Advice, user_text: str) -> tuple[Advice, bool]:
    # Escalation is decided deterministically, not by the model's own flag.
    escalate = contains_any(user_text, RED_FLAGS)

    items = list(advice.items)
    if contains_any(" ".join(items), MEDICAL_TERMS):
        escalate = True
        items = [ESCALATION_MESSAGE]

    disclaimer = advice.disclaimer or DEFAULT_DISCLAIMER
    final = advice.model_copy(update={"items": items, "disclaimer": disclaimer, "escalate": escalate})
    return final, escalate
